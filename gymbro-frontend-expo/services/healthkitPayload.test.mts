import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  assembleDailyBiometrics,
  buildAppleHealthIngestPayload,
  classifySleepValue,
  isGarminHealthSource,
  isIphoneHealthSource,
  mergedDurationHours,
  pickDailyQuantity,
  sleepHoursByWakeDate,
} from './healthkitPayload.ts';

const TZ = 'UTC';

test('sleep classification matches HealthKit category values', () => {
  assert.equal(classifySleepValue(0), 'inBed');
  assert.equal(classifySleepValue(1), 'asleep');
  assert.equal(classifySleepValue(2), 'awake');
  assert.equal(classifySleepValue(3), 'asleep');
  assert.equal(classifySleepValue(4), 'asleep');
  assert.equal(classifySleepValue(5), 'asleep');
  assert.equal(classifySleepValue('asleepCore'), 'asleep');
  assert.equal(classifySleepValue('HKCategoryValueSleepAnalysisInBed'), 'inBed');
  assert.equal(classifySleepValue('awake'), 'awake');
});

test('overlapping asleep samples are merged and assigned to the wake date', () => {
  const hours = sleepHoursByWakeDate(
    [
      {
        start: new Date('2026-11-08T22:00:00Z'),
        end: new Date('2026-11-08T23:30:00Z'),
        kind: 'asleep',
        sourceName: 'iPhone',
        bundleIdentifier: 'com.apple.health',
      },
      {
        start: new Date('2026-11-08T23:00:00Z'),
        end: new Date('2026-11-09T03:00:00Z'),
        kind: 'asleep',
        sourceName: 'iPhone',
        bundleIdentifier: 'com.apple.health',
      },
      {
        start: new Date('2026-11-09T03:00:00Z'),
        end: new Date('2026-11-09T07:00:00Z'),
        kind: 'asleep',
        sourceName: 'iPhone',
        bundleIdentifier: 'com.apple.health',
      },
      {
        start: new Date('2026-11-08T22:00:00Z'),
        end: new Date('2026-11-09T07:30:00Z'),
        kind: 'inBed',
        sourceName: 'iPhone',
        bundleIdentifier: 'com.apple.health',
      },
      {
        start: new Date('2026-11-09T04:00:00Z'),
        end: new Date('2026-11-09T04:20:00Z'),
        kind: 'awake',
        sourceName: 'iPhone',
        bundleIdentifier: 'com.apple.health',
      },
    ],
    TZ,
  );

  assert.deepEqual(hours, { '2026-11-09': 9 });
});

test('in-bed duration is used only when a night has no asleep samples', () => {
  const hours = sleepHoursByWakeDate(
    [
      {
        start: new Date('2026-11-09T00:00:00Z'),
        end: new Date('2026-11-09T08:00:00Z'),
        kind: 'inBed',
        sourceName: 'iPhone',
      },
    ],
    TZ,
  );
  assert.deepEqual(hours, { '2026-11-09': 8 });
});

test('Garmin sleep echoed into HealthKit is not reposted', () => {
  const hours = sleepHoursByWakeDate(
    [
      {
        start: new Date('2026-11-09T00:00:00Z'),
        end: new Date('2026-11-09T07:30:00Z'),
        kind: 'asleep',
        sourceName: 'Garmin Connect',
        bundleIdentifier: 'com.garmin.connect.mobile',
      },
    ],
    TZ,
  );
  assert.deepEqual(hours, {});
});

test('merged intervals do not double count overlap', () => {
  const hours = mergedDurationHours([
    { start: new Date('2026-11-09T00:00:00Z'), end: new Date('2026-11-09T04:00:00Z') },
    { start: new Date('2026-11-09T03:00:00Z'), end: new Date('2026-11-09T07:00:00Z') },
  ]);
  assert.equal(hours, 7);
});

test('steps prefer the iPhone and do not sum Garmin or a second source', () => {
  const steps = pickDailyQuantity(
    [
      {
        start: new Date('2026-11-09T15:00:00Z'),
        quantity: 6400,
        sourceName: 'iPhone',
        bundleIdentifier: 'com.apple.health',
      },
      {
        start: new Date('2026-11-09T15:00:00Z'),
        quantity: 12000,
        sourceName: 'Garmin',
        bundleIdentifier: 'com.garmin.connect.mobile',
      },
      {
        start: new Date('2026-11-09T15:00:00Z'),
        quantity: 6100,
        sourceName: 'Apple Watch',
        bundleIdentifier: 'com.apple.health.watch',
      },
      {
        start: new Date('2026-11-08T15:00:00Z'),
        quantity: 9000,
        sourceName: 'Garmin Forerunner',
        bundleIdentifier: 'com.garmin.connect.mobile',
      },
    ],
    TZ,
    'max',
  );
  assert.deepEqual(steps, { '2026-11-09': 6400 });
});

test('source helpers distinguish iPhone from Garmin and Apple Watch', () => {
  assert.equal(isGarminHealthSource('Garmin Connect', 'com.garmin.connect.mobile'), true);
  assert.equal(isIphoneHealthSource('iPhone', 'com.apple.health'), true);
  assert.equal(isIphoneHealthSource('Apple Watch', 'com.apple.health.watch'), false);
  assert.equal(isGarminHealthSource('iPhone', 'com.apple.health'), false);
});

test('ingest payload omits empty metrics and never emits null', () => {
  const days = assembleDailyBiometrics(
    {
      restingHrByDate: { '2026-11-09': 0 },
      hrvByDate: {},
      sleepHoursByDate: { '2026-11-09': 7.833 },
      stepsByDate: { '2026-11-09': 8420.4, '2026-11-08': 0 },
      activeCaloriesByDate: { '2026-11-08': Number.NaN },
    },
    { startDate: '2026-11-08', endDate: '2026-11-09' },
  );
  const payload = buildAppleHealthIngestPayload(days);
  assert.ok(payload);
  assert.equal(payload.source, 'apple_health');
  assert.equal(payload.raw_source, 'apple_health');
  assert.equal(payload.biometrics.length, 1);
  assert.deepEqual(payload.biometrics[0], {
    date: '2026-11-09',
    source: 'apple_health',
    raw_source: 'apple_health',
    sleep_hours: 7.83,
    steps: 8420,
  });
  assert.equal(JSON.stringify(payload).includes('null'), false);
  assert.equal('resting_hr' in payload.biometrics[0], false);
  assert.equal('hrv_ms' in payload.biometrics[0], false);
  assert.equal('calories_burned' in payload.biometrics[0], false);
});

test('no samples produce no ingest payload', () => {
  const days = assembleDailyBiometrics({
    restingHrByDate: {},
    hrvByDate: {},
    sleepHoursByDate: {},
    stepsByDate: {},
    activeCaloriesByDate: {},
  });
  assert.equal(buildAppleHealthIngestPayload(days), null);
});

test('the HealthKit client no longer hardcodes the old fake biometrics', () => {
  const healthkit = readFileSync(new URL('./healthkit.ts', import.meta.url), 'utf8');
  const onboarding = readFileSync(new URL('../components/onboarding/Step1WearableConnect.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(healthkit, /resting_hr:\s*58/);
  assert.doesNotMatch(healthkit, /sleep_hours:\s*7\.8/);
  assert.doesNotMatch(healthkit, /daily_steps:\s*9420/);
  assert.doesNotMatch(healthkit, /active_calories:\s*540/);
  assert.doesNotMatch(onboarding, /resting_heart_rate:\s*56/);
  assert.doesNotMatch(onboarding, /simulatedHealthKitPayload/);
  assert.doesNotMatch(onboarding, /weight_kg:\s*76\.5/);
});
