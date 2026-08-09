# Dynamic Archetype Coach Interview & Plan Engine Design Specification

## Overview
This specification details the redesign of the GYMBro AI Coach Interview system from a rigid 10-step running-centric checklist into a dynamic, goal-driven interview engine. Users select from 6 distinct goal archetypes (or provide open-ended input), triggering a specialized 4-5 step mission workflow that generates an archetype-tailored workout, nutrition, or wellness routine.

---

## 1. Goal Archetype Registries & Backend State

### 1.1 Archetype Classifications (`users` table)
The Supabase `users` table stores:
- `archetype` (text): One of `muscle_strength`, `fat_loss`, `endurance_running`, `longevity_energy`, `hybrid_fitness`, or `custom_open_ended`.
- `interview_step` (int): Active step number within the user's specific archetype mission sequence (1 to N).
- `coach_status` (text): `"not_started"` | `"interview_in_progress"` | `"interview_completed"`.

### 1.2 `ARCHETYPE_MISSIONS` Registry (`app/coach/interview_service.py`)
Replaces the monolithic static `STEP_MISSIONS` dictionary with specialized mission flows tailored to each fitness goal:

```python
ARCHETYPE_MISSIONS = {
    "muscle_strength": {
        "total_steps": 5,
        "missions": {
            1: "Goal & Target Lifts: Confirm specific hypertrophy or strength targets (e.g., bench/squat/deadlift PRs or target muscle groups).",
            2: "Equipment & Location: Audit available gear (commercial gym, dumbbells-only, home rack, bodyweight).",
            3: "Split & Schedule: Confirm weekly lifting frequency (e.g., 3-5 days/week PPL, Upper/Lower, or Full Body).",
            4: "Plan Preview: Generate tailored strength workout routine and preview split.",
            5: "Calendar & Commit: Confirm writing routine to calendar and initial workout launch."
        }
    },
    "fat_loss": {
        "total_steps": 5,
        "missions": {
            1: "Goal & Rate: Confirm recomposition vs weight loss target and weekly target rate.",
            2: "Nutrition & Deficit: Audit key nutrition habits and macro tracking preferences.",
            3: "Cardio & Daily Movement: Determine daily step goal and preferred cardio modality (Zone 2 incline walk, cycling, running).",
            4: "Plan Preview: Generate caloric deficit targets, macro splits, and movement routine.",
            5: "Calendar & Commit: Confirm schedule and launch."
        }
    },
    "endurance_running": {
        "total_steps": 5,
        "missions": {
            1: "Goal & Race: Confirm race distance, target date, and time PR.",
            2: "Data Reality Check: CITE recent Garmin/Strava weekly volume & resting HR baselines.",
            3: "Schedule & Long Run: Determine weekly running days and preferred long run day.",
            4: "Plan Preview: Generate base building/phased running plan.",
            5: "Calendar & Commit: Confirm writing plan to calendar."
        }
    },
    "longevity_energy": {
        "total_steps": 4,
        "missions": {
            1: "Goal & Health Priorities: Focus on sleep quality, daily energy, stress management, or metabolic health.",
            2: "Health Sync Audit: CITE Garmin sleep scores, HRV, and RHR trends.",
            3: "Daily Protocol: Confirm daily movement, bedtime routine, and recovery habits.",
            4: "Protocol Launch: Finalize daily wellness checklist and calendar reminders."
        }
    },
    "hybrid_fitness": {
        "total_steps": 5,
        "missions": {
            1: "Goal Balance: Confirm strength vs running/cardio priority weighting.",
            2: "Multi-Modal Audit: Audit lifting experience and running volume together.",
            3: "Hybrid Schedule: Determine combined weekly split (e.g., 3 lifts + 2 runs) to manage fatigue.",
            4: "Plan Preview: Generate integrated strength + running plan.",
            5: "Calendar & Commit: Write hybrid schedule to calendar."
        }
    },
    "custom_open_ended": {
        "total_steps": 4,
        "missions": {
            1: "Free Goal Intake: Explore user's custom free-form goal input.",
            2: "Constraint Discovery: Adaptive slot-filling for schedule, equipment, and medical/injury constraints.",
            3: "Tailored Plan Preview: Generate custom routine based on free-form intake.",
            4: "Calendar & Commit: Confirm routine launch."
        }
    }
}
```

---

## 2. Archetype-Aware Plan Generation (`app/coach/plan_service.py`)

### 2.1 Triggering Plan Generation
When advancing to the **Plan Preview** step in any archetype mission chain (Step 4 for 5-step chains, Step 3 for 4-step chains), `get_next_question` automatically executes `generate_baseline_plan(user_id, archetype=user_archetype)`.

### 2.2 Plan Structure Generators
`generate_baseline_plan` constructs distinct schema formats per archetype:
- **`muscle_strength`**: 4-week block specifying exercise choices, set/rep ranges, rest intervals, and progressive overload rules.
- **`fat_loss`**: Estimated TDEE, caloric deficit target, protein/macro breakdown, daily step count, and scheduled cardio sessions.
- **`endurance_running`**: Weekly mileage build, easy run target paces, long run day, and structured workout session (tempo/intervals).
- **`longevity_energy`**: Daily recovery targets (bedtime window, 8k+ step goal, Zone 2 sessions, mobility routine).
- **`hybrid_fitness`**: Integrated weekly matrix balancing lifting sessions and running days with fatigue management rules.
- **`custom_open_ended`**: Dynamic LLM-generated plan derived from stored user context during intake.

---

## 3. Execution Engine & Edge Cases

### 3.1 Restarting / Switching Archetypes
If a user restarts the interview or changes their goal selection, `start_interview` resets `interview_step = 1`, assigns the new `archetype`, and initiates the new mission flow.

### 3.2 Non-Wearable / Missing Data Fallback
If an athlete in `endurance_running` or `longevity_energy` lacks connected wearable data (Garmin/Strava/HealthKit), Coach Bro falls back gracefully to asking self-reported baselines instead of blocking.

---

## 4. Verification & Testing Plan

### 4.1 Unit Testing (`tests/unit/test_interview_service.py`)
- Verify correct mission resolution and step boundary checks for all 6 archetypes.
- Verify `plan_service.py` plan generation for each archetype string.

### 4.2 Integration Testing (`tests/integration/test_api_flow.py`)
- Test complete API interaction from `POST /coach/start_interview` through multi-step responses to plan completion (`coach_status = "interview_completed"`).
