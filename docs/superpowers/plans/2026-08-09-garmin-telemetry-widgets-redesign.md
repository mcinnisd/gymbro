# Garmin Telemetry Widgets & Customizable Stats/Recovery UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deep Garmin telemetry extraction pipeline (VO2 Max, Fitness Age, Body Battery, Sleep Stages, Training Status, Stress, SpO2), add a widget customization modal with conditional data rendering, extend trend filtering up to 1 Year (7D/30D/90D/6M/1Y), and fix all mobile UI bounding issues.

**Architecture:** Extend backend Garmin sync (`app/garmin/sync.py`) to extract deep telemetry into `biometrics_daily`, upgrade analytics service (`app/analytics/analytics_service.py`) for 365-day range queries, and overhaul Expo frontend screens (`stats.tsx` and `recovery.tsx`) with customizable widget modules and horizontal scrolling containers.

**Tech Stack:** Python 3.12, Flask, Supabase PostgreSQL, React Native (Expo Go), TypeScript, AsyncStorage.

## Global Constraints

- **Single Source of Truth**: All daily telemetry metrics MUST be upserted into `biometrics_daily`.
- **Conditional Rendering**: Cards MUST auto-hide if telemetry is missing or disabled by the user.
- **Zero Dummy Data**: All graphs MUST render 100% real database telemetry.
- **TypeScript Strictness**: `npx tsc --noEmit` MUST pass with 0 errors.

---

### Task 1: Deep Telemetry Ingestion & Extended Analytics Endpoint

**Files:**
- Modify: `app/garmin/sync.py:400-470`
- Modify: `app/analytics/analytics_service.py:480-620`
- Modify: `app/analytics/routes.py:25-40`
- Test: `tests/integration/test_garmin_sync.py`
- Test: `tests/unit/test_analytics.py`

**Interfaces:**
- Consumes: GarminConnect API (`get_max_metrics`, `get_training_status`, `get_body_battery`, `get_sleep_data`, `get_hrv_data`, `get_spo2_data`).
- Produces: `GET /analytics/summary?days=N` (supports `days=365`) returning `wellness` with `vo2_max`, `body_battery`, `sleep_stages`, `training_status`, `spo2`.

- [ ] **Step 1: Write failing integration test for deep telemetry extraction**

```python
def test_garmin_deep_telemetry_sync(auth_info):
    headers, user_id = auth_info
    # Test that biometrics_daily contains vo2_max, body_battery, and hrv_status after sync
    res = supabase.table("biometrics_daily").select("*").eq("user_id", user_id).execute()
    assert res.data is not None
```

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=. MOCK_DB=true pytest tests/integration/test_garmin_sync.py -v`

- [ ] **Step 3: Update `app/garmin/sync.py` to extract deep metrics into `biometrics_daily`**

Extract `vo2Max`, `fitnessAge`, `bodyBattery`, `trainingStatusKey`, `sleepScores`, `deepSleepSeconds`, `remSleepSeconds`, `lightSleepSeconds`, `spo2`, `respiration` and upsert into `biometrics_daily`.

- [ ] **Step 4: Update `app/analytics/analytics_service.py` to aggregate deep telemetry and support 365-day range**

Support `days=365` query param and return `vo2_max_trend`, `body_battery_trend`, `sleep_stage_trend`, `training_status_summary`, `spo2_trend` in `_analyze_wellness`.

- [ ] **Step 5: Run tests to verify pass**

Run: `PYTHONPATH=. MOCK_DB=true pytest tests/unit/test_analytics.py tests/integration/test_garmin_sync.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/garmin/sync.py app/analytics/analytics_service.py app/analytics/routes.py tests/
git commit -m "feat(telemetry-backend): extract deep Garmin metrics and support 1-year analytics queries"
```

---

### Task 2: Widget Preference Customization Modal Component

**Files:**
- Create: `gymbro-frontend-expo/components/WidgetCustomizeModal.tsx`
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`
- Modify: `gymbro-frontend-expo/app/(tabs)/stats.tsx`

**Interfaces:**
- Consumes: `@gymbro_widget_prefs` from `AsyncStorage`.
- Produces: `WidgetCustomizeModal` component with toggle switches for `hrv`, `sleep_stages`, `body_battery`, `training_status`, `spo2`, `vo2_max`.

- [ ] **Step 1: Create `WidgetCustomizeModal.tsx`**

Implement a modal with `Modal`, `Switch`, `AsyncStorage` persistence, and callback props (`onClose`, `onSave`).

- [ ] **Step 2: Typecheck frontend**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/components/WidgetCustomizeModal.tsx
git commit -m "feat(widgets-modal): add WidgetCustomizeModal component with AsyncStorage persistence"
```

---

### Task 3: Recovery Screen Readiness & Telemetry Overhaul

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`

**Interfaces:**
- Consumes: `GET /analytics/summary?days=N` with deep wellness payload.
- Produces: Daily Readiness Meter (0-100), 1-Year Range Filter (`7D`, `30D`, `90D`, `6M`, `1Y`), Sleep Architecture stacked bar, and Body Battery energy meter.

- [ ] **Step 1: Update `recovery.tsx` with 1-Year Range Selector and Readiness Cards**

Add range filter buttons (`7D`, `30D`, `90D`, `6M`, `1Y`) that trigger `fetchAnalyticsData(days)`. Render Daily Readiness Meter, Sleep Stages, Body Battery, and SpO2 cards conditionally.

- [ ] **Step 2: Typecheck frontend**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/recovery.tsx
git commit -m "feat(recovery-overhaul): add 1-Year range filter, Daily Readiness Meter, and Sleep Architecture card"
```

---

### Task 4: Stats Screen Performance & Training Status Overhaul

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/stats.tsx`

**Interfaces:**
- Consumes: `GET /analytics/summary?days=N`.
- Produces: Garmin Training Status & Acute Load Widget, VO2 Max & Fitness Age Badges, 1-Year Range Selector (`7D`, `30D`, `90D`, `6M`, `1Y`), and zero-clipping horizontal scrollable graphs.

- [ ] **Step 1: Update `stats.tsx` with 1-Year Range Selector, Training Status Widget, and Layout Fixes**

Add `6M` and `1Y` range filter options, Garmin Training Status & Acute Load widget, VO2 Max badge, and adjust flex containers to eliminate label clipping.

- [ ] **Step 2: Typecheck frontend**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`
Expected: PASS with 0 errors.

- [ ] **Step 3: Run full backend test suite**

Run: `PYTHONPATH=. MOCK_DB=true pytest`
Expected: 62 / 62 PASS.

- [ ] **Step 4: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/stats.tsx
git commit -m "feat(stats-overhaul): add Garmin Training Status widget, 1-Year range filter, and mobile bounding fixes"
```
