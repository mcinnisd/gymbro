/**
 * Pure Apple Health daily aggregation and ingest payload shaping.
 * No native modules: unit tests run this without HealthKit or a device.
 */

export const APPLE_HEALTH_SOURCE = 'apple_health' as const;

export const HEALTHKIT_READ_IDENTIFIERS = [
  'HKQuantityTypeIdentifierRestingHeartRate',
  'HKCategoryTypeIdentifierSleepAnalysis',
  'HKQuantityTypeIdentifierHeartRateVariabilitySDNN',
  'HKQuantityTypeIdentifierStepCount',
  'HKQuantityTypeIdentifierActiveEnergyBurned',
] as const;

export type HealthKitReadIdentifier = (typeof HEALTHKIT_READ_IDENTIFIERS)[number];

export type SleepKind = 'asleep' | 'inBed' | 'awake' | 'unknown';

export interface SleepSampleInput {
  start: Date;
  end: Date;
  kind: SleepKind;
  sourceName?: string;
  bundleIdentifier?: string;
}

export interface SourcedQuantityInput {
  start: Date;
  quantity: number;
  sourceName?: string;
  bundleIdentifier?: string;
}

export interface AppleHealthDailyBiometrics {
  date: string;
  resting_hr?: number;
  hrv_ms?: number;
  sleep_hours?: number;
  steps?: number;
  calories_burned?: number;
}

export interface AppleHealthIngestBiometric extends AppleHealthDailyBiometrics {
  date: string;
  source: typeof APPLE_HEALTH_SOURCE;
  raw_source: typeof APPLE_HEALTH_SOURCE;
}

export interface AppleHealthIngestPayload {
  source: typeof APPLE_HEALTH_SOURCE;
  raw_source: typeof APPLE_HEALTH_SOURCE;
  biometrics: AppleHealthIngestBiometric[];
}

const METRIC_KEYS = ['resting_hr', 'hrv_ms', 'sleep_hours', 'steps', 'calories_burned'] as const;
const SESSION_GAP_MS = 2 * 60 * 60 * 1000;

export function localDateKey(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const year = parts.find((part) => part.type === 'year')?.value;
  const month = parts.find((part) => part.type === 'month')?.value;
  const day = parts.find((part) => part.type === 'day')?.value;
  if (!year || !month || !day) {
    throw new Error('Could not format a HealthKit sample date');
  }
  return `${year}-${month}-${day}`;
}

export function classifySleepValue(value: number | string): SleepKind {
  if (typeof value === 'number') {
    if (value === 0) return 'inBed';
    if (value === 2) return 'awake';
    if (value === 1 || value === 3 || value === 4 || value === 5) return 'asleep';
    return 'unknown';
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === '0' || normalized === 'inbed' || normalized.endsWith('inbed')) return 'inBed';
  if (normalized === '2' || normalized === 'awake' || normalized.endsWith('awake')) return 'awake';
  if (
    normalized === '1' ||
    normalized === '3' ||
    normalized === '4' ||
    normalized === '5' ||
    normalized.includes('asleep')
  ) {
    return 'asleep';
  }
  return 'unknown';
}

export function isGarminHealthSource(sourceName?: string, bundleIdentifier?: string): boolean {
  const blob = `${sourceName ?? ''} ${bundleIdentifier ?? ''}`.toLowerCase();
  return blob.includes('garmin');
}

export function isIphoneHealthSource(sourceName?: string, bundleIdentifier?: string): boolean {
  const name = (sourceName ?? '').toLowerCase();
  const bundle = (bundleIdentifier ?? '').toLowerCase();
  if (name.includes('watch')) return false;
  if (name.includes('iphone') || name.includes('phone')) return true;
  return bundle === 'com.apple.health' || bundle.startsWith('com.apple.health.');
}

export function mergedDurationHours(intervals: Array<{ start: Date; end: Date }>): number {
  const valid = intervals
    .map((interval) => ({ start: interval.start.getTime(), end: interval.end.getTime() }))
    .filter((interval) => Number.isFinite(interval.start) && Number.isFinite(interval.end) && interval.end > interval.start)
    .sort((a, b) => a.start - b.start);
  if (valid.length === 0) return 0;

  let totalMs = 0;
  let currentStart = valid[0].start;
  let currentEnd = valid[0].end;
  for (let index = 1; index < valid.length; index += 1) {
    const next = valid[index];
    if (next.start <= currentEnd) {
      currentEnd = Math.max(currentEnd, next.end);
    } else {
      totalMs += currentEnd - currentStart;
      currentStart = next.start;
      currentEnd = next.end;
    }
  }
  totalMs += currentEnd - currentStart;
  return totalMs / 3_600_000;
}

/**
 * Cluster sleep samples into sessions and assign each session to the local
 * wake date (the session end). Asleep stages win; in-bed is used only when a
 * session has no asleep samples. Awake time is excluded. Garmin-sourced
 * samples are dropped so a HealthKit echo of Garmin sleep is not re-posted.
 */
export function sleepHoursByWakeDate(samples: SleepSampleInput[], timeZone: string): Record<string, number> {
  const usable = samples
    .filter((sample) => sample.kind === 'asleep' || sample.kind === 'inBed')
    .filter((sample) => !isGarminHealthSource(sample.sourceName, sample.bundleIdentifier))
    .filter((sample) => sample.end.getTime() > sample.start.getTime())
    .sort((a, b) => a.start.getTime() - b.start.getTime());

  const sessions: SleepSampleInput[][] = [];
  for (const sample of usable) {
    const current = sessions[sessions.length - 1];
    if (!current) {
      sessions.push([sample]);
      continue;
    }
    const sessionEnd = Math.max(...current.map((item) => item.end.getTime()));
    if (sample.start.getTime() - sessionEnd <= SESSION_GAP_MS) {
      current.push(sample);
    } else {
      sessions.push([sample]);
    }
  }

  const byDate: Record<string, number> = {};
  for (const session of sessions) {
    const asleep = session.filter((sample) => sample.kind === 'asleep');
    const hours = asleep.length > 0 ? mergedDurationHours(asleep) : mergedDurationHours(session);
    if (!(hours > 0)) continue;
    const wake = new Date(Math.max(...session.map((sample) => sample.end.getTime())));
    const date = localDateKey(wake, timeZone);
    byDate[date] = (byDate[date] ?? 0) + hours;
  }
  return byDate;
}

/**
 * Pick one value per local day. Garmin sources are ignored. An iPhone source
 * wins when one exists; otherwise the remaining non-Garmin sources are used.
 * `max` avoids summing phone + watch step duplicates. `mean` is for discrete
 * metrics such as resting HR and HRV.
 */
export function pickDailyQuantity(
  rows: SourcedQuantityInput[],
  timeZone: string,
  mode: 'max' | 'mean',
): Record<string, number> {
  const grouped = new Map<string, SourcedQuantityInput[]>();
  for (const row of rows) {
    if (!Number.isFinite(row.quantity) || row.quantity <= 0) continue;
    if (isGarminHealthSource(row.sourceName, row.bundleIdentifier)) continue;
    const date = localDateKey(row.start, timeZone);
    const list = grouped.get(date) ?? [];
    list.push(row);
    grouped.set(date, list);
  }

  const out: Record<string, number> = {};
  for (const [date, list] of grouped) {
    const phone = list.filter((row) => isIphoneHealthSource(row.sourceName, row.bundleIdentifier));
    const pool = phone.length > 0 ? phone : list;
    const values = pool.map((row) => row.quantity);
    out[date] = mode === 'max' ? Math.max(...values) : values.reduce((sum, value) => sum + value, 0) / values.length;
  }
  return out;
}

export interface AppleHealthDailyMaps {
  restingHrByDate: Record<string, number>;
  hrvByDate: Record<string, number>;
  sleepHoursByDate: Record<string, number>;
  stepsByDate: Record<string, number>;
  activeCaloriesByDate: Record<string, number>;
}

function positiveRounded(value: number | undefined, digits: number): number | undefined {
  if (value == null || !Number.isFinite(value) || value <= 0) return undefined;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

export function assembleDailyBiometrics(
  maps: AppleHealthDailyMaps,
  window?: { startDate: string; endDate: string },
): AppleHealthDailyBiometrics[] {
  const dates = new Set<string>([
    ...Object.keys(maps.restingHrByDate),
    ...Object.keys(maps.hrvByDate),
    ...Object.keys(maps.sleepHoursByDate),
    ...Object.keys(maps.stepsByDate),
    ...Object.keys(maps.activeCaloriesByDate),
  ]);

  const days: AppleHealthDailyBiometrics[] = [];
  for (const date of [...dates].sort()) {
    if (window && (date < window.startDate || date > window.endDate)) continue;
    const day: AppleHealthDailyBiometrics = { date };
    const restingHr = positiveRounded(maps.restingHrByDate[date], 0);
    const hrv = positiveRounded(maps.hrvByDate[date], 1);
    const sleep = positiveRounded(maps.sleepHoursByDate[date], 2);
    const steps = positiveRounded(maps.stepsByDate[date], 0);
    const calories = positiveRounded(maps.activeCaloriesByDate[date], 0);
    if (restingHr != null) day.resting_hr = restingHr;
    if (hrv != null) day.hrv_ms = hrv;
    if (sleep != null) day.sleep_hours = sleep;
    if (steps != null) day.steps = steps;
    if (calories != null) day.calories_burned = calories;
    if (METRIC_KEYS.some((key) => day[key] != null)) days.push(day);
  }
  return days;
}

export function buildAppleHealthIngestPayload(days: AppleHealthDailyBiometrics[]): AppleHealthIngestPayload | null {
  const biometrics: AppleHealthIngestBiometric[] = [];
  for (const day of days) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day.date)) continue;
    const row: AppleHealthIngestBiometric = {
      date: day.date,
      source: APPLE_HEALTH_SOURCE,
      raw_source: APPLE_HEALTH_SOURCE,
    };
    for (const key of METRIC_KEYS) {
      const value = day[key];
      if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
        row[key] = value;
      }
    }
    if (METRIC_KEYS.some((key) => row[key] != null)) biometrics.push(row);
  }
  if (biometrics.length === 0) return null;
  return {
    source: APPLE_HEALTH_SOURCE,
    raw_source: APPLE_HEALTH_SOURCE,
    biometrics,
  };
}

export function summarizeSyncedDays(days: AppleHealthDailyBiometrics[]): string {
  const labels: string[] = [];
  if (days.some((day) => day.resting_hr != null)) labels.push('resting heart rate');
  if (days.some((day) => day.sleep_hours != null)) labels.push('sleep');
  if (days.some((day) => day.hrv_ms != null)) labels.push('HRV');
  if (days.some((day) => day.steps != null)) labels.push('steps');
  if (days.some((day) => day.calories_burned != null)) labels.push('active energy');
  const what = labels.length > 0 ? labels.join(', ') : 'metrics';
  const noun = days.length === 1 ? 'day' : 'days';
  return `Synced ${days.length} ${noun} from Apple Health (${what}).`;
}
