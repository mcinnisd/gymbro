# GYMBro UI, Auth, Integrations & Chat Engine Remediation Design & Plan

**Date:** 2026-08-09  
**Status:** Approved  

---

## 1. Overview & Technical Requirements

Based on user feedback, this plan completely rebuilds the UI, registration flow, device integration management, data visualization graphs, and coach chat engine.

### Core Remediation Directives:
1. **Auth & Registration Fix**: Fix registration payload handling in `AuthContext.tsx` and `app/auth/routes.py` to preserve full name, handle duplicate accounts cleanly, and return actionable inline errors.
2. **Decouple Integrations from Chat**: Remove forced onboarding wizards from Coach Chat (`chat.tsx`). Move Garmin, Strava, and Apple HealthKit connection controls, live sync indicators, and a **"🔄 Re-Sync All Devices"** trigger into `profile.tsx` and developer settings.
3. **Unified Light Modern UI System**: Eliminate all dark mode gradients (`#0F172A`, `#020617`), cyan text (`#00E5FF`), and purple buttons (`#6C63FF`). Standardize ALL screens (`index.tsx`, `chat.tsx`, `training.tsx`, `stats.tsx`, `recovery.tsx`, `nutrition.tsx`, `profile.tsx`) on light mode design tokens:
   - Screen Background: Off-white `#F8FAFC`
   - Cards: White `#FFFFFF` with `#E2E8F0` borders & clean elevation
   - Typography: Headers `#0F172A`, Body `#475569`
   - Primary Buttons/Accents: `#2563EB` (Royal Blue)
   - Secondary Accents: `#059669` (Emerald)
   - Warning/Highlight: `#EA580C` (Warm Orange)
4. **Rich Interactive Garmin Data & Graphs**:
   - Upgrade `stats.tsx` and `recovery.tsx` to visualize complete Garmin health & activity metrics (Heart Rate Zones, HRV trends, Sleep Breakdown [Deep, Light, REM, Awake], Resting HR, Body Battery, Pace Distribution, Cadence, Elevation, Weekly Volume).
   - Add interactive metric filter chips, period selectors (7D, 30D, 90D), and detailed summary cards.
5. **Coach Chat Engine & Activity Tool Repair**:
   - Register `get_recent_activities` and `get_wellness_metrics` tools in `app/tools/registry.py`.
   - Update `app/context/builder.py` to inject recent workout metrics into RAG prompt context automatically.
   - Fix SSE streaming parsing in `app/chats/routes.py` and `chat.tsx` so queries like "how were my runs the last week" generate detailed, intelligent coaching analysis instead of empty fallback "Answer complete." text.

---

## 2. Implementation Tasks

### Task 1: Fix Registration & Auth Context Payload
- Modify `gymbro-frontend-expo/app/context/AuthContext.tsx` to include `name` in `body: JSON.stringify({ username: email, password, name })`.
- Modify `app/auth/routes.py` to return JSON error details on failed registrations.
- Update `gymbro-frontend-expo/app/index.tsx` to display inline error feedback and match the light modern design theme.

### Task 2: Decouple Device Integrations to Profile / Settings with Manual Re-Sync
- Update `gymbro-frontend-expo/app/(tabs)/profile.tsx` to include a full **Connected Devices & Integrations** panel (Garmin, Strava, Apple HealthKit status, email/password inputs, and a **"🔄 Sync Device Data Now"** action).
- Remove the forced onboarding step 1/2 screens from `gymbro-frontend-expo/app/(tabs)/chat.tsx` so Coach Chat opens directly to the chat interface.

### Task 3: Complete Light Modern Theme Overhaul Across Expo Screens
- Redesign `gymbro-frontend-expo/app/index.tsx`, `(tabs)/chat.tsx`, `(tabs)/training.tsx`, `(tabs)/stats.tsx`, `(tabs)/recovery.tsx`, `(tabs)/nutrition.tsx`, and `(tabs)/profile.tsx` using light-mode tokens (`#F8FAFC` background, `#FFFFFF` cards, `#0F172A` text, `#2563EB` primary blue buttons).

### Task 4: Rich Interactive Garmin Metrics & Visual Graphs Screen
- Build comprehensive interactive graph components in `gymbro-frontend-expo/app/(tabs)/stats.tsx` and `(tabs)/recovery.tsx`.
- Support metric tab switching (Heart Rate, HRV, Sleep Stages, Body Battery, Running Pace/Cadence) with period controls (7D, 30D, 90D) and metric summary badges.

### Task 5: Activity Retrieval Tools & Coach Chat Response Stream Repair
- Create `app/tools/activity_tools.py` implementing `get_recent_activities` and `get_wellness_metrics`.
- Register tools in `app/tools/registry.py` and add them to `AnalystAgent`.
- Update `app/chats/routes.py` and `chat.tsx` stream parsing to ensure natural language questions receive detailed LLM activity analysis without falling back to stub text.
