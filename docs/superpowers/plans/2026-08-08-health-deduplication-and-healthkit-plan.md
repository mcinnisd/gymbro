# Multi-Source Health Data Deduplication & HealthKit Entitlements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure native iOS Apple HealthKit entitlements in Expo app, implement a multi-source data deduplication engine for workouts and biometrics, and render visual source badges on dashboard cards.

**Architecture:** 
- `gymbro-frontend-expo/app.json`: iOS Info.plist usage descriptions.
- `app/health_hub/deduplication_service.py`: Backend deduplication & source priority hierarchy.
- `gymbro-frontend-expo/app/(tabs)/recovery.tsx`: Source badges on recovery cards.
- `gymbro-frontend-expo/app/(tabs)/stats.tsx`: Source badges on workout cards.

---

## Global Constraints

- **Python Unit test check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.
- **TypeScript check**: `cd gymbro-frontend-expo && npx tsc --noEmit` must pass with 0 errors.

---

### Task 1: iOS Apple HealthKit Info.plist Entitlements (`app.json`)

**Files:**
- Modify: `gymbro-frontend-expo/app.json`

- [ ] **Step 1: Add HealthKit usage descriptions to `app.json`**

Configure `NSHealthShareUsageDescription` and `NSHealthUpdateUsageDescription` under `expo.ios.infoPlist`.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app.json
git commit -m "feat(expo): add iOS HealthKit usage descriptions and entitlements to app.json"
```

---

### Task 2: Multi-Source Data Deduplication Engine (`app/health_hub/deduplication_service.py`)

**Files:**
- Create: `app/health_hub/deduplication_service.py`
- Test: `tests/unit/test_health_deduplication.py`

- [ ] **Step 1: Write unit test for deduplication engine**

Create `tests/unit/test_health_deduplication.py` testing activity deduplication and biometrics source priority logic.

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_health_deduplication.py -v`

- [ ] **Step 3: Implement deduplication engine**

Create `app/health_hub/deduplication_service.py` with `deduplicate_activities` and `deduplicate_biometrics`.

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_health_deduplication.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/health_hub/deduplication_service.py tests/unit/test_health_deduplication.py
git commit -m "feat(health): implement multi-source data deduplication engine and source priority hierarchy"
```

---

### Task 3: Visual Source Badging on Dashboard Cards (`recovery.tsx`, `stats.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`
- Modify: `gymbro-frontend-expo/app/(tabs)/stats.tsx`

- [ ] **Step 1: Add source badges to recovery and activity cards**

Render `⌚ Garmin (Primary)`, `🍎 Apple Health`, or `🔥 Strava` badges on recovery and workout cards.

- [ ] **Step 2: Run TypeScript typecheck & pytest**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v`  
Run: `cd gymbro-frontend-expo && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/recovery.tsx gymbro-frontend-expo/app/\(tabs\)/stats.tsx
git commit -m "feat(expo): add visual data source badges to activity and recovery cards"
```
