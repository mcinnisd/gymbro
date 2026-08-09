# GYMBro System Overhaul & Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the full 6-phase overhaul of GYMBro based on feedback.txt, establishing an E2E testing suite, data sync & multi-hop RAG optimization, chat MCP tool-calling engine, light modern UI system, interactive recovery dashboards, and enhanced nutrition/calendar features.

**Architecture:** The plan decomposes the work into 6 sequential phases, each with bite-sized, independently testable tasks. Backend tasks focus on Flask services, mock & Supabase databases, Gemini LLM tool calling, and RAG context building. Frontend tasks focus on Expo React Native UI components, custom chart visualizations, and light mode theme tokens.

**Tech Stack:** Python 3.10+, Flask, Pytest, Google GenAI SDK (`google.genai`), React Native / Expo, TypeScript.

## Global Constraints

- Preserve all existing REST endpoints (`/auth`, `/coach`, `/chats`, `/activities`, `/nutrition`, `/journal`, `/analytics`, `/strava`, `/garmin`).
- Maintain mock database fallbacks (`MOCK_DB=true`) for offline development while supporting Supabase production mode.
- Use clean light-mode modern theme styling on the Expo frontend.
- Provide unit & integration test coverage for all new services and API endpoints.

---

### Task 1: Deep E2E Synthetic User Testing Suite (Phase 1)

**Files:**
- Create: `tests/e2e/test_synthetic_user_workflows.py`
- Modify: `app/mock_supabase.py`
- Test: `tests/e2e/test_synthetic_user_workflows.py`

**Interfaces:**
- Consumes: `app.create_app`, `app.mock_supabase`
- Produces: Synthetic user profile generator & E2E integration test suite validating account registration, bloodwork PDF ingestion, Garmin activity logging, and training plan generation.

- [ ] **Step 1: Write the failing E2E synthetic user test**

```python
import pytest
from app import create_app
from app.mock_supabase import MockSupabaseClient

def test_synthetic_user_full_journey():
    app = create_app()
    client = app.test_client()
    
    # 1. Register synthetic user
    res = client.post('/auth/register', json={
        'email': 'synthetic_runner@example.com',
        'password': 'password123',
        'name': 'Runner Alex'
    })
    assert res.status_code in [200, 201]
    token = res.json.get('access_token') or res.json.get('token')
    
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    
    # 2. Verify initial data state
    res_journal = client.get('/journal', headers=headers)
    assert res_journal.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails or exposes gaps**

Run: `PYTHONPATH=. pytest tests/e2e/test_synthetic_user_workflows.py -v`
Expected: Test runs and validates initial registration & journal fetch endpoints.

- [ ] **Step 3: Implement synthetic data seeding helpers in test harness**

Add user workflow helper methods to `tests/e2e/test_synthetic_user_workflows.py` for bloodwork PDF upload simulation, manual workout entry, Strava activity payload posting, and workout plan generation assertion.

- [ ] **Step 4: Run synthetic E2E tests to verify pass**

Run: `PYTHONPATH=. pytest tests/e2e/test_synthetic_user_workflows.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_synthetic_user_workflows.py
git commit -m "test: add synthetic user workflow E2E test suite"
```

---

### Task 2: Fix Strava OAuth Callback & Data Auto-Sync Pipeline (Phase 2)

**Files:**
- Modify: `app/strava/routes.py`
- Modify: `app/strava/service.py`
- Test: `tests/unit/test_strava_routes.py`

**Interfaces:**
- Consumes: Flask request query parameters (`code`, `state`)
- Produces: Correct HTTP redirect URI targeting Expo mobile app scheme (`gymbro://strava-callback`) and reliable background sync payload ingest.

- [ ] **Step 1: Write failing test for Strava OAuth deep-link redirect**

```python
def test_strava_oauth_callback_redirect(client):
    res = client.get('/strava/callback?code=mock_code_123&state=mock_user_id')
    assert res.status_code == 302
    assert res.headers['Location'].startswith('gymbro://') or 'strava-callback' in res.headers['Location']
```

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=. pytest tests/unit/test_strava_routes.py -v`
Expected: FAIL due to missing mobile scheme redirect URL handling.

- [ ] **Step 3: Update `app/strava/routes.py` callback route to construct mobile app redirect URL**

Update callback endpoint logic to return a `302 Redirect` to `gymbro://strava-callback?status=success` or render HTML with standard mobile fallback.

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=. pytest tests/unit/test_strava_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/strava/routes.py app/strava/service.py tests/unit/test_strava_routes.py
git commit -m "fix(strava): handle mobile app deep link redirect on OAuth callback"
```

---

### Task 3: Optimize Multi-Hop RAG Context Building Engine (Phase 2)

**Files:**
- Modify: `app/context/builder.py`
- Modify: `app/memory/rag.py`
- Test: `tests/unit/test_multihop_rag.py`

**Interfaces:**
- Consumes: `user_id`, query string, historical date bounds.
- Produces: Assembled contextual bundle with user metrics (sleep, HRV), recent activities, notes, and vector similarity search results.

- [ ] **Step 1: Write failing test for context question multihop retrieval**

```python
def test_multihop_context_builder_includes_notes_and_activities():
    from app.context.builder import build_user_context
    context = build_user_context(user_id="synthetic_user_1", query="How has my sleep affected my running pace?")
    assert "sleep" in context.lower() or "activities" in context.lower()
    assert "notes" in context.lower() or "journal" in context.lower()
```

- [ ] **Step 2: Run test to verify failure/coverage gap**

Run: `PYTHONPATH=. pytest tests/unit/test_multihop_rag.py -v`

- [ ] **Step 3: Enhance `app/context/builder.py` to aggregate user notes, activities, and journal entries concurrently**

Ensure vector search results are merged with SQL health metrics before sending prompt context to Gemini.

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=. pytest tests/unit/test_multihop_rag.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/context/builder.py app/memory/rag.py tests/unit/test_multihop_rag.py
git commit -m "feat(rag): optimize multi-hop context aggregation for coach queries"
```

---

### Task 4: Overhaul Chat MCP / Tool Calling & UI Payload Generation (Phase 3)

**Files:**
- Modify: `app/coach/service.py`
- Modify: `app/agent/tools.py`
- Test: `tests/unit/test_agent_tools.py`

**Interfaces:**
- Consumes: LLM tool call definitions (`generate_training_plan`, `render_chart`, `update_user_goals`)
- Produces: Structured response object containing both text message and `ui_payload` dictionary for frontend rendering.

- [ ] **Step 1: Write failing test for structured tool output generation**

```python
def test_coach_service_returns_ui_payload():
    from app.coach.service import process_coach_message
    res = process_coach_message(user_id="user_123", message="Generate a 4-day marathon plan")
    assert "response" in res
    assert "ui_payload" in res or "plan" in res
```

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=. pytest tests/unit/test_agent_tools.py -v`

- [ ] **Step 3: Update `app/coach/service.py` tool dispatch handling**

Ensure tool outputs format structured JSON payloads (`{ type: "WORKOUT_PLAN", data: ... }` or `{ type: "CHART", data: ... }`).

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=. pytest tests/unit/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/coach/service.py app/agent/tools.py tests/unit/test_agent_tools.py
git commit -m "feat(coach): implement structured tool outputs with UI payloads"
```

---

### Task 5: Mobile UI Light Modern Design Tokens & Theme Setup (Phase 4)

**Files:**
- Modify: `gymbro-frontend-expo/constants/Colors.ts`
- Modify: `gymbro-frontend-expo/app/_layout.tsx`
- Test: Verify styles compilation via Expo dev tooling.

**Interfaces:**
- Consumes: Theme provider context
- Produces: Modern light-mode color palette (Off-white backgrounds `#F8FAFC`, slate text `#0F172A`, primary accent `#2563EB`, success `#059669`, warm orange `#EA580C`).

- [ ] **Step 1: Update `gymbro-frontend-expo/constants/Colors.ts` with modern light theme tokens**

Define light mode scheme replacing dark purple values with clean, high-contrast modern fitness aesthetic.

- [ ] **Step 2: Update `_layout.tsx` theme context wrapper**

Ensure light theme is enforced as default across navigation stack and tab bar.

- [ ] **Step 3: Commit UI theme changes**

```bash
git add gymbro-frontend-expo/constants/Colors.ts gymbro-frontend-expo/app/_layout.tsx
git commit -m "style(ui): transition expo app design system to light modern palette"
```

---

### Task 6: Interactive Recovery & Layered Trends Analytics Screen (Phase 5)

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/recovery.tsx`
- Modify: `gymbro-frontend-expo/components/RecoveryChart.tsx` (or new component)

**Interfaces:**
- Consumes: `/analytics/summary` REST API endpoint
- Produces: Interactive layered chart toggle (HRV vs Sleep vs Heart Rate vs Training Load) with inline coach chat trigger.

- [ ] **Step 1: Implement layered chart visualization component**

Add stateful metric selection buttons (Sleep, HRV, Heart Rate) allowing multi-line visualization overlay.

- [ ] **Step 2: Wire screen to backend analytics API**

Fetch real-time metric trends from `/analytics/summary` and populate chart dataset.

- [ ] **Step 3: Commit recovery screen updates**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/recovery.tsx gymbro-frontend-expo/components/
git commit -m "feat(ui): implement interactive layered recovery trends dashboard"
```

---

### Task 7: Nutrition Item Editing & Calorie/Macro Re-evaluation (Phase 6)

**Files:**
- Modify: `app/nutrition/routes.py`
- Modify: `gymbro-frontend-expo/app/(tabs)/nutrition.tsx`
- Test: `tests/unit/test_nutrition_routes.py`

**Interfaces:**
- Consumes: `PUT /nutrition/logs/<id>` with updated item name/weight
- Produces: Recalculated calories, protein, carbs, and fats payload.

- [ ] **Step 1: Write test for food log item update and macro re-calculation**

```python
def test_update_food_log_item_recalculates_macros(client):
    res = client.put('/nutrition/logs/log_123', json={
        'item_name': '200g Grilled Chicken Breast',
    })
    assert res.status_code == 200
    assert res.json['calories'] > 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=. pytest tests/unit/test_nutrition_routes.py -v`

- [ ] **Step 3: Implement item update endpoint in `app/nutrition/routes.py`**

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=. pytest tests/unit/test_nutrition_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/nutrition/routes.py gymbro-frontend-expo/app/\(tabs\)/nutrition.tsx tests/unit/test_nutrition_routes.py
git commit -m "feat(nutrition): add item editing with dynamic macro re-evaluation"
```

---

## Verification & Final Review

1. Execute full Pytest test suite: `PYTHONPATH=. pytest`
2. Verify all 7 tasks completed cleanly with passing assertions.
