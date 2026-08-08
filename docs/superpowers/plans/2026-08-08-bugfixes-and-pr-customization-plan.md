# Bugfixes & Custom PR Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the AI Meal Scanner, wire up real PDF document picking for blood tests, build customizable activity PRs on Stats tab, fix Strava OAuth redirect, and fix onboarding scroll cutoff.

**Architecture:** 
- `app/nutrition/vision_service.py`: Upgrade vision model call to `xAI grok-4.3` / vision API.
- `gymbro-frontend-expo/app/(tabs)/recovery.tsx`: Integrate `expo-document-picker` for PDF uploads and navigate to chat on device sync.
- `gymbro-frontend-expo/app/(tabs)/stats.tsx`: Purge hardcoded PRs, allow custom activity PR creation and selective category display.
- `app/strava/routes.py`: Return deep-link success HTML page after token exchange.
- `gymbro-frontend-expo/app/(tabs)/chat.tsx`: Fix `ScrollView` `paddingBottom: 140` for full scrolling.

---

## Global Constraints

- **TypeScript check**: `cd gymbro-frontend-expo && npx tsc --noEmit` must pass with 0 errors.
- **Python Unit test check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.

---

### Task 1: AI Vision Meal Scanner Fix (`app/nutrition/vision_service.py`)

**Files:**
- Modify: `app/nutrition/vision_service.py`
- Test: `tests/unit/test_vision_service.py`

- [ ] **Step 1: Update `vision_service.py` with xAI grok-4.3 / Vision provider API**

Implement live vision call using xAI `grok-4.3` / OpenAI / Gemini provider chain so actual image analysis returns live meal nutrition.

- [ ] **Step 2: Run pytest**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_vision_service.py -v`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/nutrition/vision_service.py tests/unit/test_vision_service.py
git commit -m "fix(nutrition): replace deprecated vision API call with live xAI grok-4.3 vision parser"
```

---

### Task 2: Real PDF Document Picker & Navigation in Recovery (`recovery.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`

- [ ] **Step 1: Wire up `expo-document-picker` and navigation**

Use `DocumentPicker.getDocumentAsync` for PDF upload and `router.push('/(tabs)/chat')` for device sync.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/recovery.tsx
git commit -m "feat(expo): add real PDF document picker for lab blood tests and navigation for device sync"
```

---

### Task 3: Customizable Activity PRs on Stats Tab (`stats.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/stats.tsx`

- [ ] **Step 1: Purge dummy PR defaults & add custom PR management**

Initialize PR states to empty, allow adding custom PR items (Lifting, Running, Cycling, etc.) and hiding unused categories.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/stats.tsx
git commit -m "feat(expo): purge hardcoded PRs and add customizable personal records engine"
```

---

### Task 4: Strava OAuth Redirect Fix & Onboarding Scroll Fix (`app/strava/routes.py`, `chat.tsx`)

**Files:**
- Modify: `app/strava/routes.py`
- Modify: `gymbro-frontend-expo/app/(tabs)/chat.tsx`

- [ ] **Step 1: Update `app/strava/routes.py` `exchange_token` to render auto-redirect HTML**

Return HTML page with `gymbro://` deep-link callback script so mobile OAuth flow completes cleanly.

- [ ] **Step 2: Add `paddingBottom: 140` to onboarding `ScrollView` in `chat.tsx`**

Ensure profile confirmation button and all fields scroll completely into view.

- [ ] **Step 3: Run TypeScript typecheck & pytest**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v`  
Run: `cd gymbro-frontend-expo && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add app/strava/routes.py gymbro-frontend-expo/app/\(tabs\)/chat.tsx
git commit -m "fix(strava,expo): fix Strava OAuth redirect deep-linking and onboarding scroll cutoff"
```
