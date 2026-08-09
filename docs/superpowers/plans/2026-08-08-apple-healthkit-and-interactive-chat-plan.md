# Apple HealthKit Integration, Rich Markdown Chat & Interactive Onboarding Widgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Apple HealthKit auto-sync with manual baseline entry fallbacks, replace raw text chat bubbles with a styled React Native Markdown renderer, eliminate blank speech bubbles with a floating status bar, enable SSE token streaming, and build interactive day-selector buckets & training volume charts.

**Architecture:** 
- `gymbro-frontend-expo/app/services/healthkit.ts`: Apple HealthKit sync module.
- `gymbro-frontend-expo/app/components/MarkdownText.tsx`: Custom React Native Markdown text component.
- `gymbro-frontend-expo/app/components/DaySelectorWidget.tsx`: Interactive day selection widget.
- `gymbro-frontend-expo/app/components/TrainingVolumeChart.tsx`: Dynamic visual training volume bar chart.
- `gymbro-frontend-expo/app/(tabs)/chat.tsx`: Streamlining chat UI, floating status bar, token streaming, and onboarding widgets.

---

## Global Constraints

- **TypeScript check**: `cd gymbro-frontend-expo && npx tsc --noEmit` must pass with 0 errors.
- **Python Unit test check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.

---

### Task 1: Apple HealthKit Integration & Non-Wearable Baseline Experience

**Files:**
- Create: `gymbro-frontend-expo/app/services/healthkit.ts`
- Modify: `gymbro-frontend-expo/app/(tabs)/chat.tsx`
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`

- [ ] **Step 1: Create Apple HealthKit Service (`healthkit.ts`)**

Implement `syncAppleHealthKitData` to fetch Resting HR, Sleep, HRV, Steps, and Active Calories, falling back gracefully if HealthKit is not available on non-iOS environments.

- [ ] **Step 2: Add HealthKit & Manual Baseline cards to Onboarding Step 1 (`chat.tsx`)**

Add 3 integration cards: **Apple Health**, **Garmin / Strava**, and **Manual Baseline Entry**.

- [ ] **Step 3: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add gymbro-frontend-expo/app/services/healthkit.ts gymbro-frontend-expo/app/\(tabs\)/chat.tsx gymbro-frontend-expo/app/\(tabs\)/recovery.tsx
git commit -m "feat(expo): add Apple HealthKit integration and non-wearable baseline entry fallback"
```

---

### Task 2: Rich Markdown Message Renderer & Chat UI Fixes

**Files:**
- Create: `gymbro-frontend-expo/app/components/MarkdownText.tsx`
- Modify: `gymbro-frontend-expo/app/(tabs)/chat.tsx`

- [ ] **Step 1: Create `MarkdownText.tsx` component**

Build regex-based parser converting `**bold**`, `*italic*`, `### headings`, and `- bullet points` into styled React Native `<Text>` and `<View>` elements.

- [ ] **Step 2: Remove blank speech bubble & add floating status bar**

In `chat.tsx`, remove `content: ''` `botPlaceholder` and render a floating status badge (`⚡ Coach Bro is thinking...`) above input bar. Stream tokens word-by-word.

- [ ] **Step 3: Run TypeScript typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add gymbro-frontend-expo/app/components/MarkdownText.tsx gymbro-frontend-expo/app/\(tabs\)/chat.tsx
git commit -m "fix(expo): add rich Markdown message renderer, floating thinking status bar, and streaming tokens"
```

---

### Task 3: Interactive Interview Widgets & Visual Volume Bar Chart

**Files:**
- Create: `gymbro-frontend-expo/app/components/DaySelectorWidget.tsx`
- Create: `gymbro-frontend-expo/app/components/TrainingVolumeChart.tsx`
- Modify: `gymbro-frontend-expo/app/(tabs)/chat.tsx`

- [ ] **Step 1: Create `DaySelectorWidget.tsx` component**

Build interactive day selection bucket component (`[Mon] [Tue] [Wed] [Thu] [Fri] [Sat] [Sun]`) that formats user choices into chat messages.

- [ ] **Step 2: Create `TrainingVolumeChart.tsx` component**

Build visual bar chart rendering projected weekly workout volume and intensity breakdown.

- [ ] **Step 3: Embed widgets into `chat.tsx` interview flow**

Render `DaySelectorWidget` inside schedule questions and `TrainingVolumeChart` inside the interview completed summary card.

- [ ] **Step 4: Run TypeScript typecheck & pytest**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v`  
Run: `cd gymbro-frontend-expo && npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add gymbro-frontend-expo/app/components/ gymbro-frontend-expo/app/\(tabs\)/chat.tsx
git commit -m "feat(expo): add interactive day selector widget and dynamic training volume bar chart"
```
