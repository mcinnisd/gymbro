# Dynamic Archetype Coach Interview & Plan Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the coach interview system from a static 10-step running checklist into a dynamic, 6-archetype goal-driven interview engine with specialized plan generation.

**Architecture:** 
- `app/coach/interview_service.py`: Defines `ARCHETYPE_MISSIONS` map and manages archetype-specific step advancement.
- `app/coach/plan_service.py`: Generates specialized routine schemas (`muscle_strength`, `fat_loss`, `endurance_running`, `longevity_energy`, `hybrid_fitness`, `custom_open_ended`).
- `tests/unit/test_interview_service.py`: Unit tests for archetype step resolution and advancement.
- `tests/unit/test_plan_service.py`: Unit tests for archetype baseline plan generation.
- `tests/integration/test_api_flow.py`: Integration testing for end-to-end multi-archetype coach interviews.

## Global Constraints

- **Python Unit Test Check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.
- **Python Integration Test Check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/integration/ -v` must pass cleanly.

---

### Task 1: `ARCHETYPE_MISSIONS` Registry & Dynamic Step Engine (`app/coach/interview_service.py`)

**Files:**
- Modify: `app/coach/interview_service.py`
- Test: `tests/unit/test_interview_service.py`

**Interfaces:**
- Consumes: `user.archetype` from Supabase `users` table (defaults to `"endurance_running"` if unset).
- Produces: `ARCHETYPE_MISSIONS` dictionary mapping 6 archetypes to step missions; dynamic `start_interview` and `get_next_question` step resolution.

- [ ] **Step 1: Write failing unit test for `ARCHETYPE_MISSIONS` resolution**

Create or update `tests/unit/test_interview_service.py`:

```python
import pytest
from app.coach.interview_service import ARCHETYPE_MISSIONS, get_current_step

def test_archetype_missions_registry_structure():
    expected_archetypes = [
        "muscle_strength", "fat_loss", "endurance_running",
        "longevity_energy", "hybrid_fitness", "custom_open_ended"
    ]
    for key in expected_archetypes:
        assert key in ARCHETYPE_MISSIONS
        assert "total_steps" in ARCHETYPE_MISSIONS[key]
        assert "missions" in ARCHETYPE_MISSIONS[key]
        assert len(ARCHETYPE_MISSIONS[key]["missions"]) == ARCHETYPE_MISSIONS[key]["total_steps"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_interview_service.py -v`
Expected: FAIL with `NameError: cannot import name 'ARCHETYPE_MISSIONS'`

- [ ] **Step 3: Implement `ARCHETYPE_MISSIONS` & update `interview_service.py`**

In `app/coach/interview_service.py`:
1. Add `ARCHETYPE_MISSIONS` registry containing missions for `muscle_strength`, `fat_loss`, `endurance_running`, `longevity_energy`, `hybrid_fitness`, and `custom_open_ended`.
2. Update `_generate_dynamic_response` and `get_next_question` to read `user.get("archetype", "endurance_running")` and resolve the active step mission from `ARCHETYPE_MISSIONS[user_archetype]["missions"][step]`.
3. Check `current_step == ARCHETYPE_MISSIONS[user_archetype]["total_steps"] - 1` to trigger `generate_baseline_plan(user_id, archetype=user_archetype)`.

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_interview_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/coach/interview_service.py tests/unit/test_interview_service.py
git commit -m "feat: implement ARCHETYPE_MISSIONS registry and dynamic step engine"
```

---

### Task 2: Archetype-Aware Plan Generation (`app/coach/plan_service.py`)

**Files:**
- Modify: `app/coach/plan_service.py`
- Test: `tests/unit/test_plan_service.py`

**Interfaces:**
- Consumes: `user_id` and optional `archetype` string parameter in `generate_baseline_plan`.
- Produces: Tailored JSON structure saved to `users.training_plan` based on fitness goal.

- [ ] **Step 1: Write failing unit test for archetype-aware plan generation**

Create or update `tests/unit/test_plan_service.py`:

```python
import pytest
from app.coach.plan_service import generate_baseline_plan

def test_generate_baseline_plan_muscle_strength(mocker):
    mocker.patch("app.coach.plan_service.supabase")
    mocker.patch("app.coach.plan_service.generate_chat_response", return_value='{"plan_type": "strength", "split": "Push/Pull/Legs", "weeks": []}')
    
    plan = generate_baseline_plan("user_123", archetype="muscle_strength")
    assert plan is not None
    assert plan.get("plan_type") == "strength" or "split" in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_plan_service.py -v`
Expected: FAIL (argument mismatch or prompt not archetype-aware)

- [ ] **Step 3: Update `generate_baseline_plan` in `plan_service.py`**

Modify `app/coach/plan_service.py`:
1. Update `generate_baseline_plan(user_id: str, archetype: str = "endurance_running")`.
2. Construct specialized prompt instructions per `archetype` (`muscle_strength`, `fat_loss`, `endurance_running`, `longevity_energy`, `hybrid_fitness`, `custom_open_ended`).
3. Store the generated JSON structure in `users.training_plan`.

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_plan_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/coach/plan_service.py tests/unit/test_plan_service.py
git commit -m "feat: implement archetype-aware baseline plan generation"
```

---

### Task 3: Integration Testing for Multi-Archetype Onboarding

**Files:**
- Modify: `tests/integration/test_api_flow.py`

**Interfaces:**
- Consumes: `/coach/start_interview` and `/chats/<id>/messages` endpoints.
- Produces: Verified end-to-end archetype interview execution.

- [ ] **Step 1: Add integration test for Strength & Hybrid archetype interviews**

In `tests/integration/test_api_flow.py`, add `test_strength_interview_flow`:
1. Start coach interview for a user with `archetype="muscle_strength"`.
2. Send message responses through steps 1-5.
3. Verify that the final response completes the interview (`is_complete == True`).

- [ ] **Step 2: Run integration tests to verify they pass**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/integration/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_api_flow.py
git commit -m "test: add integration test for dynamic archetype coach interview"
```
