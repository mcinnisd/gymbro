# 4. First-Time Onboarding Stepper, Telemetry Pre-Population, and Interactive Setup Flow

Date: 2026-08-16

## Context

The first-run experience is the single most critical transition in GYMBro. When a new athlete registers, the system must:
1. Capture demographic biometrics (Age, Biological Sex, Height, Weight).
2. Link hardware telemetry providers (Garmin Connect, Strava, Apple HealthKit).
3. Ingest historical baselines (Resting HR, HRV, sleep architecture, acute weekly volume).
4. Establish a composite, ranked **Goal Set** (Primary, Secondary, Lifestyle constraints).
5. Perform a **Data Reality Check** comparing stated aspirations against historical workload.
6. Generate a tailored **Meso Horizon** training plan and commit it to the **Interactive Calendar**.

Previously, the app had conflicting onboarding prototypes: a rigid 10-step pure text chat interview in `chat.tsx` that created high cognitive load and typing friction, and hardcoded empty states that allowed users to bypass setup into unconfigured tabs.

## Decision

1. **Dedicated Native Stepper with Contextual AI Drawer**:
   - Implement a 5-step native onboarding flow (`gymbro-frontend-expo/app/onboarding/`) backed by a hard gate state machine (`users.coach_status = 'not_started' | 'in_onboarding' | 'active'`).
   - Un-onboarded users are routed directly to the setup flow upon login/registration. State is persisted per step to allow seamless resumption if the app is closed mid-flow.
   - Every screen features a persistent bottom chip (`"💬 Ask Coach Bro"`) that slides up a contextual AI drawer. The agent can clarify concepts, account for injuries/limitations, and dynamically adjust form parameters.

2. **Wearable-First Sequencing & Telemetry Pre-Population**:
   - **Step 1 (Hardware Linking)**: Prompt for wearable connection (Garmin / Apple Health / Strava) immediately upon entry.
   - **Step 2 (Smart Profile & Baseline Confirmation)**: Extract demographic biometrics and 14-day rolling telemetry from the connected device to auto-fill the Athlete Profile. Users with connected wearables confirm with 1 tap. Users without wearables or with failed connections use manual baseline sliders with sensible defaults.

3. **Ranked Composite Goal Modeling**:
   - **Step 3 (Goal Set & Schedule)**: Users configure a multi-objective Goal Set (Primary athletic priority + optional Secondary/Tertiary targets + days available + equipment access) using tactile quick-reply chips.

4. **Data Reality Check & Horizon Selection**:
   - **Step 4 (Calibration & Horizon Selection)**: Present an instant visual baseline audit comparing stated targets with detected weekly training load.
   - Provide a clear horizon choice:
     - **"🏆 4-Week Foundation Block"** (Default: consistency building, safe volume ramp, Week 4 deload/adaptation).
     - **"🎯 8–12 Week Goal Milestone Block"** (Extended cycle for targeted race dates or body transformation deadlines).

5. **Instant Calendar Commitment**:
   - **Step 5 (Plan Preview & Launch)**: Render a native `gymbro.widget/v1` `calendar_proposal` card with full day-by-day session splits.
   - 1-tap **"Commit to Calendar & Launch"** executes a bulk transaction to `training_events`, marks `coach_status = 'active'`, and transitions the athlete directly to `/(tabs)/training` with their new calendar populated and a Day 1 Welcome Briefing card.

## Consequences

- Reduces initial onboarding completion time from 4+ minutes of open-ended text chat down to 60–90 seconds of tactile, pre-populated taps.
- Eliminates empty-calendar states and ensures every athlete begins with a personalized, physiologically sound training plan.
- Seamlessly integrates the `gymbro.widget/v1` protocol and two-tier context engine into the very first user interaction.
- Provides robust failure isolation: hardware sync timeouts immediately fall back to manual sliders without blocking the athlete.
