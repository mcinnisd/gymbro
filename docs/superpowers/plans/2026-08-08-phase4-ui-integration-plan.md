# Phase 4: Full iPhone App & Web UI Dashboard Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the "Deep Analysis" mode toggle switch into the Mobile AI Coach chat screen, add the Lab Biomarkers & Health Hub status cards to the Recovery tab, and verify frontend typecheck and web build.

**Architecture:** Connect the React Native Expo app screens (`chat.tsx` and `recovery.tsx`) to the newly built backend services (`app/biomarkers`, `app/coach`, `app/memory`).

**Tech Stack:** React Native, Expo Router, TypeScript, React Web.

## Global Constraints

- **TypeScript check**: `cd gymbro-frontend-expo && npx tsc --noEmit` must pass with 0 errors.
- **Python Unit test check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.

---

### Task 1: Mobile App Chat "Deep Analysis" Mode Toggle (`chat.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/chat.tsx`

**Interfaces:**
- Consumes: Chat API endpoint (`${apiUrl}/chats/` or `${apiUrl}/coach/chat`).
- Produces: UI toggle switch between "⚡ Fast" and "🧠 Deep Analysis" mode, sending `reasoning_mode` in chat requests.

- [ ] **Step 1: Update `chat.tsx` with reasoning mode state and header toggle**

Add `reasoningMode` (`'fast' | 'deep_dive'`) toggle pill in header bar and append to message payload.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/chat.tsx
git commit -m "feat(expo): add Fast vs Deep Analysis mode toggle switch to AI Coach chat"
```

---

### Task 2: Lab Biomarkers & Health Hub Status Card (`recovery.tsx`)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`

**Interfaces:**
- Consumes: `GET /biomarkers/flagged` or `biomarkers` data from backend.
- Produces: Visual Health Hub card in Recovery screen displaying resting HR, HRV, sleep, and flagged blood test status badges (`flagged_low`, `flagged_high`, `optimal`).

- [ ] **Step 1: Update `recovery.tsx` with Lab Biomarkers Card**

Add Biomarkers card with indicator badges for flagged lab markers.

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/recovery.tsx
git commit -m "feat(expo): add Lab Biomarkers and Health Hub status cards to Recovery screen"
```
