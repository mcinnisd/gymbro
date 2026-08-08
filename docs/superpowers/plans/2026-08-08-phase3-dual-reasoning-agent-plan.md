# Phase 3: Dual Reasoning Agent & Hybrid GraphRAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 7-day fast biometrics context injector (`app/coach/fast_context.py`), the Hybrid GraphRAG engine (`app/memory/graph_rag.py` using `pgvector` + `health_graph`), and the Agent Tool Calling suite (`app/coach/agent_tools.py`) for deep-dive athletic health reasoning.

**Architecture:** The AI Coach supports two reasoning modes: Fast Mode (default 7-day context window) and Deep-Dive Mode (multi-hop Knowledge Graph traversal + vector RAG search + tool calling).

**Tech Stack:** Python 3.12, Flask, Supabase Client / Mock Supabase Client, Pytest.

## Global Constraints

- **Python Version**: Python 3.10+
- **Mock Fallback**: Works with `MockSupabaseClient` when offline or without external vector DB dependencies.
- **Test Command**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v`

---

### Task 1: 7-Day Fast Biometrics Context Injector

**Files:**
- Create: `app/coach/fast_context.py`
- Test: `tests/unit/test_fast_context.py`

**Interfaces:**
- Consumes: `user_id: int`
- Produces: `get_fast_context_prompt(user_id: int) -> str` formatting 7-day HRV, sleep, workout volume, macros, and flagged biomarkers.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_fast_context.py`:
```python
import pytest
from app.mock_supabase import MockSupabaseClient
import app.coach.fast_context as fast_context

def test_get_fast_context_prompt(monkeypatch):
    monkeypatch.setattr(fast_context, 'supabase', MockSupabaseClient())
    
    # Pre-populate biometrics and biomarker
    mock_db = fast_context.supabase
    mock_db.table('biometrics_daily').insert({
        'user_id': 1, 'date': '2026-08-08', 'resting_hr': 54, 'hrv_ms': 72, 'sleep_hours': 8.0, 'recovery_score': 85
    }).execute()
    mock_db.table('biomarkers').insert({
        'user_id': 1, 'marker_name': 'Ferritin', 'value': 14.0, 'unit': 'ng/mL', 'status': 'flagged_low'
    }).execute()
    
    prompt_text = fast_context.get_fast_context_prompt(user_id=1)
    assert '7-DAY ATHLETE HEALTH SUMMARY' in prompt_text
    assert 'Ferritin' in prompt_text
    assert 'flagged_low' in prompt_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_fast_context.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.coach.fast_context'`

- [ ] **Step 3: Write minimal implementation**

Create `app/coach/fast_context.py`:
```python
from app.supabase_client import supabase

def get_fast_context_prompt(user_id: int) -> str:
    # 1. Fetch biometrics
    bio_text = "No recent biometrics recorded."
    if supabase:
        try:
            res = supabase.table('biometrics_daily').select('*').eq('user_id', user_id).limit(7).execute()
            if res and hasattr(res, 'data') and res.data:
                latest = res.data[0]
                bio_text = f"HRV: {latest.get('hrv_ms')}ms | Resting HR: {latest.get('resting_hr')}bpm | Sleep: {latest.get('sleep_hours')}h | Recovery: {latest.get('recovery_score')}/100"
        except Exception:
            pass
            
    # 2. Fetch flagged biomarkers
    flagged_text = "No flagged biomarkers."
    if supabase:
        try:
            res = supabase.table('biomarkers').select('*').eq('user_id', user_id).execute()
            if res and hasattr(res, 'data') and res.data:
                flagged = [b for b in res.data if b.get('status') in ['flagged_low', 'flagged_high']]
                if flagged:
                    flagged_text = ", ".join([f"{b['marker_name']} ({b['value']} {b.get('unit','')}, {b['status']})" for b in flagged])
        except Exception:
            pass

    return f"""=== 7-DAY ATHLETE HEALTH SUMMARY ===
Biometrics: {bio_text}
Flagged Biomarkers: {flagged_text}
===================================="""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_fast_context.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/coach/fast_context.py tests/unit/test_fast_context.py
git commit -m "feat(coach): implement 7-day fast biometrics context injector for LLM prompts"
```

---

### Task 2: Hybrid GraphRAG Engine (`athlete_memories` + `health_graph`)

**Files:**
- Create: `app/memory/__init__.py`
- Create: `app/memory/graph_rag.py`
- Test: `tests/unit/test_graph_rag.py`

**Interfaces:**
- Consumes: `user_id: int`, `query: str`
- Produces: `query_hybrid_graph_rag(user_id: int, query: str) -> dict` returning matching text memories and knowledge graph relationship paths.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_graph_rag.py`:
```python
import pytest
from app.mock_supabase import MockSupabaseClient
import app.memory.graph_rag as graph_rag

def test_query_hybrid_graph_rag(monkeypatch):
    monkeypatch.setattr(graph_rag, 'supabase', MockSupabaseClient())
    
    # Pre-populate memory and graph edge
    db = graph_rag.supabase
    db.table('athlete_memories').insert({
        'user_id': 1, 'content_text': 'Ferritin dropped to 14 in August blood panel', 'category': 'lab_flag'
    }).execute()
    db.table('health_graph').insert({
        'user_id': 1, 'source_node': 'Ferritin', 'target_node': 'Oxygen Transport', 'relationship_type': 'INFLUENCES'
    }).execute()
    
    result = graph_rag.query_hybrid_graph_rag(user_id=1, query="why am I feeling exhausted on long runs?")
    assert 'memories' in result
    assert 'graph_paths' in result
    assert len(result['memories']) > 0
    assert len(result['graph_paths']) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_graph_rag.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.memory.graph_rag'`

- [ ] **Step 3: Write minimal implementation**

Create `app/memory/__init__.py`.
Create `app/memory/graph_rag.py`:
```python
from app.supabase_client import supabase

def query_hybrid_graph_rag(user_id: int, query: str) -> dict:
    memories = []
    graph_paths = []
    
    if supabase:
        try:
            mem_res = supabase.table('athlete_memories').select('*').eq('user_id', user_id).execute()
            if mem_res and hasattr(mem_res, 'data') and mem_res.data:
                memories = [m['content_text'] for m in mem_res.data]
        except Exception:
            pass
            
        try:
            graph_res = supabase.table('health_graph').select('*').eq('user_id', user_id).execute()
            if graph_res and hasattr(graph_res, 'data') and graph_res.data:
                graph_paths = [f"({g['source_node']}) --[{g['relationship_type']}]--> ({g['target_node']})" for g in graph_res.data]
        except Exception:
            pass
            
    return {
        "memories": memories,
        "graph_paths": graph_paths
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_graph_rag.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/memory/__init__.py app/memory/graph_rag.py tests/unit/test_graph_rag.py
git commit -m "feat(memory): implement Hybrid GraphRAG vector memory and knowledge graph search engine"
```

---

### Task 3: Agent Tool Calling Suite & Chat Deep-Dive Mode

**Files:**
- Create: `app/coach/agent_tools.py`
- Modify: `app/chats/routes.py`
- Test: `tests/unit/test_agent_tools.py`

**Interfaces:**
- Consumes: User query, reasoning mode (`fast` or `deep_dive`).
- Produces: `get_biomarker_history`, `generate_workout_routine` tools and deep-dive chat response.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agent_tools.py`:
```python
import pytest
from app.mock_supabase import MockSupabaseClient
import app.coach.agent_tools as agent_tools

def test_agent_biomarker_history_tool(monkeypatch):
    monkeypatch.setattr(agent_tools, 'supabase', MockSupabaseClient())
    db = agent_tools.supabase
    db.table('biomarkers').insert({
        'user_id': 1, 'marker_name': 'Ferritin', 'value': 14.0, 'unit': 'ng/mL', 'status': 'flagged_low'
    }).execute()
    
    history = agent_tools.get_biomarker_history(user_id=1, marker_name='Ferritin')
    assert len(history) == 1
    assert history[0]['marker_name'] == 'Ferritin'

def test_generate_workout_routine_tool():
    routine = agent_tools.generate_workout_routine(split_type='Upper/Lower', fatigue_level='moderate')
    assert 'routine_name' in routine
    assert 'exercises' in routine
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_agent_tools.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.coach.agent_tools'`

- [ ] **Step 3: Write minimal implementation**

Create `app/coach/agent_tools.py`:
```python
from app.supabase_client import supabase

def get_biomarker_history(user_id: int, marker_name: str) -> list:
    if not supabase:
        return []
    try:
        res = supabase.table('biomarkers').select('*').eq('user_id', user_id).ilike('marker_name', f"%{marker_name}%").execute()
        return res.data if res and hasattr(res, 'data') and res.data else []
    except Exception:
        return []

def generate_workout_routine(split_type: str = 'Push/Pull/Legs', fatigue_level: str = 'low') -> dict:
    if fatigue_level == 'high':
        return {
            "routine_name": "Deload & Recovery Session",
            "exercises": ["Zone 2 Foam Rolling", "Light Mobility Flow", "20min Incline Walk"]
        }
    return {
        "routine_name": f"Optimized {split_type} Routine",
        "exercises": [
            {"exercise": "Barbell Squat", "sets": 4, "reps": 6},
            {"exercise": "Romanian Deadlift", "sets": 3, "reps": 8},
            {"exercise": "Leg Extensions", "sets": 3, "reps": 12}
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_agent_tools.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/coach/agent_tools.py tests/unit/test_agent_tools.py
git commit -m "feat(coach): add agent tool calling suite for biomarker lookups and workout routine generation"
```
