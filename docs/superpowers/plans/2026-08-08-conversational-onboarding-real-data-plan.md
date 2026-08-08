# Conversational Onboarding & Real-Data Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all hardcoded dummy data across the app, replace empty states with actionable 1-tap sync/upload buttons, and upgrade the AI Coach onboarding to support broad goal archetypes (Strength, Fat Loss, Endurance, Longevity, Custom Free Response).

**Architecture:** Refactor Expo mobile app screens (`recovery.tsx`, `nutrition.tsx`, `training.tsx`, `chat.tsx`) to pull authentic backend state and render actionable empty-state cards, while updating Flask backend coach routes (`app/coach/`) to parse broad goal archetypes.

**Tech Stack:** React Native, Expo Router, TypeScript, Python Flask, Supabase.

---

## Global Constraints

- **TypeScript check**: `cd gymbro-frontend-expo && npx tsc --noEmit` must pass with 0 errors.
- **Python Unit test check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.

---

### Task 1: Dummy Data Purge & Actionable Empty States in Recovery Screen (`recovery.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`

**Interfaces:**
- Consumes: Real biometrics and flagged lab biomarkers from backend (`GET /journal`, `GET /biomarkers/flagged`).
- Produces: Clean empty state cards when no data exists (*"No Wearable Synced"*, *"No Bloodwork Uploaded"*).

- [ ] **Step 1: Update `recovery.tsx` to remove hardcoded sleep/RHR defaults and add conditional empty-state cards**

Remove static `sleepScore = 82` and `rhrHistory` array. Replace with authentic state variables and render actionable upload/sync prompt cards when data is missing.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/recovery.tsx
git commit -m "feat(expo): purge dummy data from Recovery screen and add actionable empty-state cards"
```

---

### Task 2: Actionable Empty States in Nutrition Screen (`nutrition.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/nutrition.tsx`

**Interfaces:**
- Consumes: Today's logged meals from backend.
- Produces: Actionable *"No Meals Logged Today"* empty-state card with a **"📸 Scan Meal Photo"** button when no meals exist.

- [ ] **Step 1: Update `nutrition.tsx` with zero-state prompt banner**

Show clean 0 macro counters and a prominent photo scan CTA button when meal array is empty.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/nutrition.tsx
git commit -m "feat(expo): add actionable empty-state photo scan banner to Nutrition screen"
```

---

### Task 3: Conversational Onboarding & Broad Goal Engine (`app/coach/` & `chat.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/chat.tsx`
- Modify: `app/coach/routes.py`
- Test: `tests/unit/test_coach_broad_goals.py`

**Interfaces:**
- Consumes: Goal archetype (Strength, Fat Loss, Endurance, Longevity, Custom).
- Produces: Chat onboarding with quick-reply goal chips and custom free-response input, generating tailored plans for any goal type.

- [ ] **Step 1: Write unit test for broad goal plan generation**

Create `tests/unit/test_coach_broad_goals.py` testing plan generation for strength, fat loss, longevity, and custom goals.

- [ ] **Step 2: Run test to verify failure/pass**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_coach_broad_goals.py -v`

- [ ] **Step 3: Update `app/coach/routes.py` and `chat.tsx`**

Add quick-reply chips for goal archetypes (Strength, Fat Loss, Endurance, Longevity, Custom) and handle custom free-response goal input.

- [ ] **Step 4: Run tests and TypeScript typecheck**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v`  
Run: `cd gymbro-frontend-expo && npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add app/coach/routes.py gymbro-frontend-expo/app/\(tabs\)/chat.tsx tests/unit/test_coach_broad_goals.py
git commit -m "feat(coach): implement broad goal archetype intake and chat onboarding"
```
