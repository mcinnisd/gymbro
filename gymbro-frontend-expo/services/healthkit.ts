import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants, { ExecutionEnvironment } from 'expo-constants';
import { Platform } from 'react-native';
import {
  APPLE_HEALTH_SOURCE,
  assembleDailyBiometrics,
  buildAppleHealthIngestPayload,
  classifySleepValue,
  HEALTHKIT_READ_IDENTIFIERS,
  localDateKey,
  pickDailyQuantity,
  sleepHoursByWakeDate,
  summarizeSyncedDays,
  type AppleHealthDailyBiometrics,
  type AppleHealthIngestPayload,
  type SleepKind,
  type SourcedQuantityInput,
} from './healthkitPayload';

export type {
  AppleHealthDailyBiometrics,
  AppleHealthIngestPayload,
} from './healthkitPayload';
export { APPLE_HEALTH_SOURCE, HEALTHKIT_READ_IDENTIFIERS };

const ENABLED_KEY = 'gymbro.apple_health.enabled';
const LAST_SYNC_KEY = 'gymbro.apple_health.last_sync_ms';
const FOREGROUND_MIN_INTERVAL_MS = 15 * 60 * 1000;
const DEFAULT_LOOKBACK_DAYS = 14;

export type HealthKitFailureReason =
  | 'not_ios'
  | 'expo_go'
  | 'unavailable'
  | 'no_data'
  | 'read_failed'
  | 'post_failed';

export type HealthKitSyncResult =
  | {
      ok: true;
      posted: boolean;
      days: AppleHealthDailyBiometrics[];
      payload: AppleHealthIngestPayload;
      message: string;
    }
  | {
      ok: false;
      reason: HealthKitFailureReason;
      message: string;
    };

export interface HealthKitSyncOptions {
  apiUrl?: string;
  authToken?: string | null;
  days?: number;
}

function failure(reason: HealthKitFailureReason, message: string): HealthKitSyncResult {
  return { ok: false, reason, message };
}

function deviceTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

function asDate(value: Date | string | number | null | undefined): Date | null {
  if (value == null) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function lookbackWindow(days: number): { start: Date; end: Date } {
  const end = new Date();
  const start = new Date(end);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - (Math.max(days, 1) - 1));
  return { start, end };
}

export async function rememberAppleHealthConnected(): Promise<void> {
  await AsyncStorage.multiSet([
    [ENABLED_KEY, '1'],
    [LAST_SYNC_KEY, String(Date.now())],
  ]);
}

export async function postAppleHealthIngest(
  apiUrl: string,
  authToken: string,
  payload: AppleHealthIngestPayload,
): Promise<void> {
  const response = await fetch(`${apiUrl.replace(/\/+$/, '')}/telemetry/sync`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
      'Bypass-Tunnel-Reminder': 'true',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Apple Health ingest failed (${response.status})`);
  }
}

type QuantityStat = {
  startDate?: Date;
  sumQuantity?: { quantity?: number };
  averageQuantity?: { quantity?: number };
  source?: { name?: string; bundleIdentifier?: string };
};

type CategoryStat = {
  startDate: Date;
  endDate: Date;
  value: number | string;
  sourceRevision?: { source?: { name?: string; bundleIdentifier?: string } };
};

function rowsFromStats(stats: readonly QuantityStat[], field: 'sumQuantity' | 'averageQuantity'): SourcedQuantityInput[] {
  const rows: SourcedQuantityInput[] = [];
  for (const stat of stats) {
    const start = asDate(stat.startDate);
    const quantity = stat[field]?.quantity;
    if (!start || quantity == null) continue;
    rows.push({
      start,
      quantity,
      sourceName: stat.source?.name ?? '',
      bundleIdentifier: stat.source?.bundleIdentifier ?? '',
    });
  }
  return rows;
}

function sleepFromSamples(samples: readonly CategoryStat[]): Array<{
  start: Date;
  end: Date;
  kind: SleepKind;
  sourceName: string;
  bundleIdentifier: string;
}> {
  const rows = [];
  for (const sample of samples) {
    const start = asDate(sample.startDate);
    const end = asDate(sample.endDate);
    if (!start || !end) continue;
    rows.push({
      start,
      end,
      kind: classifySleepValue(sample.value),
      sourceName: sample.sourceRevision?.source?.name ?? '',
      bundleIdentifier: sample.sourceRevision?.source?.bundleIdentifier ?? '',
    });
  }
  return rows;
}

/**
 * Read resting HR, sleep, HRV (SDNN), steps, and active energy from HealthKit.
 * Returns no payload when nothing real was read. Never substitutes sample numbers.
 */
export async function readAppleHealthDaily(options: { days?: number } = {}): Promise<HealthKitSyncResult> {
  if (Platform.OS !== 'ios') {
    return failure('not_ios', 'Apple Health is only available on iPhone.');
  }
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) {
    return failure(
      'expo_go',
      'Apple Health needs a Gymbro development build or TestFlight install. Expo Go cannot read HealthKit.',
    );
  }

  const days = options.days ?? DEFAULT_LOOKBACK_DAYS;
  const { start, end } = lookbackWindow(days);
  const timeZone = deviceTimeZone();
  const sleepStart = new Date(start.getTime() - 18 * 60 * 60 * 1000);

  try {
    const healthKit = await import('@kingstinct/react-native-healthkit');
    if (!healthKit.isHealthDataAvailable()) {
      return failure('unavailable', 'HealthKit is not available on this device.');
    }

    await healthKit.requestAuthorization({ toRead: [...HEALTHKIT_READ_IDENTIFIERS] });

    const quantityFilter = { filter: { date: { startDate: start, endDate: end } } };
    const [steps, energy, restingHr, hrv, sleep] = await Promise.all([
      healthKit.queryStatisticsCollectionForQuantitySeparateBySource(
        'HKQuantityTypeIdentifierStepCount',
        ['cumulativeSum'],
        start,
        { day: 1 },
        { ...quantityFilter, unit: 'count' },
      ),
      healthKit.queryStatisticsCollectionForQuantitySeparateBySource(
        'HKQuantityTypeIdentifierActiveEnergyBurned',
        ['cumulativeSum'],
        start,
        { day: 1 },
        { ...quantityFilter, unit: 'kcal' },
      ),
      healthKit.queryStatisticsCollectionForQuantitySeparateBySource(
        'HKQuantityTypeIdentifierRestingHeartRate',
        ['discreteAverage'],
        start,
        { day: 1 },
        { ...quantityFilter, unit: 'count/min' },
      ),
      healthKit.queryStatisticsCollectionForQuantitySeparateBySource(
        'HKQuantityTypeIdentifierHeartRateVariabilitySDNN',
        ['discreteAverage'],
        start,
        { day: 1 },
        { ...quantityFilter, unit: 'ms' },
      ),
      healthKit.queryCategorySamples('HKCategoryTypeIdentifierSleepAnalysis', {
        limit: 0,
        filter: { date: { startDate: sleepStart, endDate: end } },
      }),
    ]);

    const daily = assembleDailyBiometrics(
      {
        restingHrByDate: pickDailyQuantity(rowsFromStats(restingHr, 'averageQuantity'), timeZone, 'mean'),
        hrvByDate: pickDailyQuantity(rowsFromStats(hrv, 'averageQuantity'), timeZone, 'mean'),
        sleepHoursByDate: sleepHoursByWakeDate(sleepFromSamples(sleep), timeZone),
        stepsByDate: pickDailyQuantity(rowsFromStats(steps, 'sumQuantity'), timeZone, 'max'),
        activeCaloriesByDate: pickDailyQuantity(rowsFromStats(energy, 'sumQuantity'), timeZone, 'max'),
      },
      { startDate: localDateKey(start, timeZone), endDate: localDateKey(end, timeZone) },
    );
    const payload = buildAppleHealthIngestPayload(daily);
    if (!payload) {
      return failure(
        'no_data',
        'Apple Health returned no resting heart rate, sleep, heart rate variability, steps, or active energy. Allow Gymbro to read those categories in the Health app, then sync again.',
      );
    }

    return {
      ok: true,
      posted: false,
      days: daily,
      payload,
      message: summarizeSyncedDays(daily),
    };
  } catch (error) {
    console.error('[HealthKit] read failed', error);
    return failure(
      'read_failed',
      'Could not read Apple Health. If access was denied, enable Resting Heart Rate, Sleep, Heart Rate Variability, Steps, and Active Energy in Settings → Health → Data Access & Devices → Gymbro.',
    );
  }
}

export async function syncAppleHealthKitData(options: HealthKitSyncOptions = {}): Promise<HealthKitSyncResult> {
  const read = await readAppleHealthDaily({ days: options.days });
  if (!read.ok) return read;
  if (!options.apiUrl || !options.authToken) return read;

  try {
    await postAppleHealthIngest(options.apiUrl, options.authToken, read.payload);
    try {
      await rememberAppleHealthConnected();
    } catch (error) {
      console.warn('[HealthKit] Could not persist Apple Health sync preference', error);
    }
    return { ...read, posted: true };
  } catch (error) {
    console.error('[HealthKit] ingest failed', error);
    return failure(
      'post_failed',
      'Apple Health data was read, but Gymbro could not save it. Check the connection and try again.',
    );
  }
}

/**
 * Foreground backup sync. Runs only after the athlete has connected Apple Health,
 * and skips when the last successful post was within the debounce window.
 */
export async function syncAppleHealthOnForeground(options: { apiUrl: string; authToken: string }): Promise<void> {
  if (Platform.OS !== 'ios' || !options.authToken) return;
  try {
    const enabled = await AsyncStorage.getItem(ENABLED_KEY);
    if (enabled !== '1') return;
    const lastSync = Number(await AsyncStorage.getItem(LAST_SYNC_KEY) || '0');
    if (Number.isFinite(lastSync) && Date.now() - lastSync < FOREGROUND_MIN_INTERVAL_MS) return;
  } catch (error) {
    console.warn('[HealthKit] Could not read Apple Health sync preference', error);
    return;
  }

  const result = await syncAppleHealthKitData(options);
  if (!result.ok && result.reason !== 'no_data') {
    console.warn(`[HealthKit] foreground sync skipped: ${result.reason}`);
  }
}
