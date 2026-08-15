# GYMBro: Product Vision, Feature Roadmap & System Specification

## 1. High-Level Product Vision

**GYMBro** is a centralized personal health data lake and autonomous AI athletic intelligence platform. It aggregates biometric telemetry, GPS activities, nutritional intake, subjective daily journals, and clinical laboratory bloodwork into a unified health repository. 

An intelligent **Agent Engine** analyzes this multimodal health stream to provide:
- Instant daily recovery & readiness insights via **Fast Context** (sub-50ms).
- Longitudinal trend analysis, fatigue detection, and health recommendations via **Two-Tier Context & Vector Memory**.
- Dynamic, multi-horizon training and lifestyle calendar planning (Years/Months/Weeks/Days).
- Interactive, native in-chat data visualizations, action cards, and plan adjustments.
- Multi-persona coaching tailored to beginners, intermediate athletes, bodybuilders/strength athletes, runners/marathoners, and longevity/wellness optimizers.
- A clean, modern, light UI built natively in **React Native Expo** for mobile with local-first and privacy-focused architecture.

---

## 2. Target User Personas & Archetypes

GYMBro supports multi-goal composite objectives without rigid archetype lock-in:

1. **The Fitness Beginner / Couch-to-5K**:
   - Needs frictionless onboarding, non-intimidating explanations, habit-building reminders, and safe progressive volume ramping.
2. **The Active Intermediate**:
   - Balances busy work/life schedules with 3–5 workouts a week; needs flexible rescheduling when missed sessions occur.
3. **The Strength / Hypertrophy Athlete**:
   - Focuses on progressive overload, lifting volume, PR tracking, target muscle splits (PPL, Upper/Lower), and high-protein nutrition targets.
4. **The Endurance & Marathon Runner**:
   - Analyzes weekly mileage, long run pacing, HR zones, elevation, acute-to-chronic workload ratios (ACWR), and tapering schedules.
5. **The Body Recomposition / Fat Loss User**:
   - Tracks caloric deficits, macro splits (protein/carbs/fat), daily step goals, Zone 2 cardio, and weight/measurement trends over time.
6. **The Longevity & Health Optimizer**:
   - Prioritizes sleep architecture (Deep/REM), resting heart rate, HRV trends, biological age, and blood biomarker panels (ApoB, hs-CRP, Vitamin D, metabolic panels).

---

## 3. Core Architectural Pillars

### Pillar A: Centralized Health Ingestion & Deduplication
- **Tier 1 (Core Anchor)**: Garmin Connect (sleep stages, overnight HRV, resting HR, activities, telemetry streams).
- **Tier 2 (Ecosystem Wearables)**: Apple HealthKit (`HKQuantityTypeIdentifier...`), Strava (OAuth REST v3), Manual Entry.
- **Tier 3 (Clinical Lab Biomarkers)**: Multimodal PDF lab parser extracting analyte values, reference ranges, and clinical flags.
- **Tier 4 (Nutrition & Vision)**: Photo meal recognition with automatic macro/calorie estimation and user-editable item names.
- **Deduplication Engine**: $\pm 5\text{ min} / \pm 5\%$ distance tolerance with deterministic priority (**Garmin FIT > Strava > HealthKit > Manual**).

### Pillar B: Two-Tier Agent Reasoning & Memory
- **Tier 1: Fast Context (<50ms)**: Rolling 7-to-14 day operational context (sleep scores, HRV status, acute training load, recent workouts, macro adherence, soreness journals) injected directly into prompt turns.
- **Tier 2: Semantic Vector Memory**: Vector index (`athlete_memories`, `user_intelligence`) capturing historical PRs, food allergies, past injuries, coaching feedback, and user preferences.
- **Future Tier 3: Hybrid Graph RAG**: Knowledge graph ontology linking nutrition $\to$ sleep $\to$ biomarkers $\to$ athletic performance.

### Pillar C: Dynamic Multi-Horizon Calendar
- **Macro Horizon**: Seasonal/annual trajectory (e.g. Fall Half-Marathon, Winter Hypertrophy Block).
- **Meso Horizon**: 4–8 week structured training blocks (Base building, Build, Deload).
- **Micro Horizon**: Weekly training schedule balanced across availability, fatigue, and recovery.
- **Daily Horizon**: Daily adaptive adjustments based on morning HRV readiness (e.g. automatically swap high-intensity intervals for recovery when HRV drops significantly).
- **Interactive Calendar UI**: Native mobile calendar with tap-in session inspection, manual drag-and-drop editing, and agent-negotiated adjustments.

### Pillar D: Interactive Chat & Native Widgets
- **Structured Tool Call UI Payloads**: Agent returns typed JSON payloads rendered natively on the client:
  - Interactive scrubbing charts (HRV trends, pace distributions, sleep stage breakdowns).
  - Plan Preview & "Approve & Add to Calendar" commitment cards.
  - Interactive Goal / Preference chips & questionnaires.
  - Meal macro re-evaluation sliders.
- **Customizable Persona**: User can rename their agent and configure conversational tone.

### Pillar E: Privacy, Security & Local-First Evolution
- **Local Database & Sandbox Support**: Full offline development mode with mock database support (`MOCK_DB=true`).
- **Encrypted Biomarker Vault**: Client-side encrypted lab results and sensitive health data.
- **Local-First LLM Roadmap**: Future support for on-device or local network LLMs (Ollama, Apple Silicon MLX).
- **Voice Intelligence**: Future real-time conversational voice agent for hands-free workout coaching.

---

## 4. Feature Release Roadmap

### Phase 1: MVP Core (Active Focus)
- [x] Consolidate frontend to `gymbro-frontend-expo` with modern light theme (ADR-0001).
- [x] Define canonical domain model in `CONTEXT.md` and ADR-0001.
- [x] Research and document normalized telemetry schema across Garmin & HealthKit (Ticket #3).
- [ ] Squash database migrations and align table schemas with `mock_supabase.py` (Ticket #5).
- [x] Implement native in-chat interactive chart and action widget protocol (Ticket #4, ADR-0002).
- [ ] Multi-goal onboarding interview and calendar batch-commit generator (Ticket #6).
- [x] Agent Tool registry, mutation policy, and MCP interface design (Ticket #7, ADR-0003).

### Phase 2: Deep Analytics & Multi-Horizon Planning
- [ ] Biometric correlation engine (HRV vs Sleep vs Load multi-axis comparison).
- [ ] Long-term statistical trending (12-month VO2 Max progression, volume distribution).
- [ ] Morning readiness check-in with automatic daily workout rescheduling.
- [ ] External calendar integration (Google / Apple / iCal) for smart schedule conflict detection (Ticket #24).
- [ ] Food log history and dynamic macro goal adjustments based on body weight/age.

### Phase 3: Wearable Expansion & Graph RAG
- [ ] Whoop & Oura API integrations.
- [ ] Direct clinical lab FHIR integrations (Quest Diagnostics, LabCorp).
- [ ] Knowledge graph ontology linking nutrition, biomarkers, and performance.

### Phase 4: Local-First, Voice & End-to-End Encryption
- [ ] On-device / local network LLM backend mode (Ollama / MLX).
- [ ] Real-time conversational voice coaching over WebSockets.
- [ ] Client-side encrypted biometric vault.
