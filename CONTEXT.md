# GYMBro Domain Model Glossary (CONTEXT.md)

This document defines the canonical domain vocabulary for GYMBro. All codebase symbols, routes, issues, and agent interactions must adhere to these terms.

---

### Core Entities

- **Athlete Profile**: The user's physiological and lifestyle identity, containing age, weight, height, resting metrics, equipment availability, and historical baseline context.
- **Goal Set**: A structured set of active athletic, nutritional, and longevity objectives (e.g., Primary: Marathon Endurance; Secondary: Body Recomposition; Tertiary: Biomarker Optimization). Replaces single-archetype locks with multi-objective prioritization.
- **Telemetry Sample**: A normalized, timestamped biometric or activity measurement (e.g., HRV, Resting Heart Rate, Sleep Architecture, Training Load, VO2 Max, Pace, Cadence, Power) ingested from hardware providers.
- **Biomarker Panel**: A structured clinical laboratory blood test containing analyte names (e.g., ApoB, hs-CRP, Vitamin D, Testosterone), measured values, reference ranges, and abnormal flags.
- **Nutrition Log**: A timestamped dietary entry capturing meal items, caloric content, macronutrient breakdown (protein, carbs, fats), and micronutrient data derived via photo vision or manual logging.
- **Daily Journal**: An athlete's subjective recovery log capturing sleep quality feel, muscle soreness, energy rating, and free-form notes.
- **Calendar Session**: A discrete scheduled athletic, recovery, or lifestyle event on the athlete's timeline. Each session has a target modality, intensity, duration, structural exercises/intervals, and completion state.

---

### Intelligence & Context Engine

- **Agent Engine**: The autonomous athletic intelligence layer responsible for intent detection, multi-hop context retrieval, tool execution, and proactive coaching dialog. Replaces legacy coach heuristics with tool-driven agent reasoning.
- **Fast Context**: A deterministic rolling 7-to-14 day operational snapshot (sleep, HRV trend, acute training load, recent workouts, macro adherence, daily journals) assembled sub-50ms for prompt injection.
- **Long-Term Memory**: A semantic vector store indexing user intelligence facts, injury histories, dietary restrictions, personal records (PRs), and conversational feedback.
- **Plan Horizon**: The temporal scope of training programming:
  - **Macro Horizon**: Multi-month or seasonal trajectory (e.g., 16-week marathon cycle, 6-month body recomp).
  - **Meso Horizon**: 3–6 week focused training block (e.g., Base aerobic building, Peak volume, Deload block).
  - **Micro Horizon**: Weekly training schedule balanced across availability, fatigue, and recovery.
  - **Daily Horizon**: Specific session execution adapted to morning HRV/sleep readiness.
  Plan horizons are dynamic and responsive to queries rather than static profile properties.

---

### Interface & Interaction

- **Interactive Chat Widget**: A structured JSON payload returned by Agent tools that renders native client-side interactive UI components (dynamic interactive charts, plan approval modals, macro calculators, session editors) directly in the conversation stream.
- **Health Lake**: The centralized, deduplicated repository of raw and normalized telemetry spanning all hardware and lab sources.
