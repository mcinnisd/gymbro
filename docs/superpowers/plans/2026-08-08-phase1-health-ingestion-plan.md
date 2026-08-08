# Phase 1: Database Refactoring & Unified Health Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the database layer and build the unified health ingestion service (`app/health_hub/` and `app/biomarkers/`) for continuous biometrics, activities, and lab PDF reports with reference ranges.

**Architecture:** Create modular domain services `app/health_hub/` and `app/biomarkers/` to decouple raw data ingestion from route definitions. Support Supabase PostgreSQL and Mock Supabase fallback for offline development.

**Tech Stack:** Python 3.12, Flask, Supabase Client / Mock Client, PyPDF / OCR, Pytest.

## Global Constraints

- **Python Version**: Python 3.10+
- **Mock Fallback**: `MOCK_DB=true` must continue working without throwing exceptions when Supabase is disconnected.
- **Test Command**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/ -v`

---

### Task 1: Supabase Migrations & Mock Schema Models

**Files:**
- Create: `migrations/20260808_unified_health_schema.sql`
- Modify: `app/mock_supabase.py`
- Test: `tests/unit/test_mock_health_schema.py`

**Interfaces:**
- Consumes: Existing `MockSupabaseClient` in `app/mock_supabase.py`.
- Produces: Tables `biometrics_daily`, `activities`, `lab_panels`, `biomarkers`, `meals`, `athlete_memories`, `health_graph` in both SQL migration and mock memory state.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_mock_health_schema.py`:
```python
import pytest
from app.mock_supabase import MockSupabaseClient

def test_mock_supabase_has_new_health_tables():
    client = MockSupabaseClient()
    
    # Insert daily biometrics
    bio_res = client.table('biometrics_daily').insert({
        'user_id': 1,
        'date': '2026-08-08',
        'resting_hr': 55,
        'hrv_ms': 68,
        'sleep_hours': 7.5,
        'raw_source': 'garmin'
    }).execute()
    assert len(bio_res.data) == 1
    
    # Insert lab panel and biomarker
    panel_res = client.table('lab_panels').insert({
        'id': 101,
        'user_id': 1,
        'test_date': '2026-08-01',
        'provider_name': 'Superpower'
    }).execute()
    assert len(panel_res.data) == 1
    
    marker_res = client.table('biomarkers').insert({
        'panel_id': 101,
        'user_id': 1,
        'marker_name': 'Ferritin',
        'value': 18.5,
        'unit': 'ng/mL',
        'status': 'flagged_low'
    }).execute()
    assert len(marker_res.data) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_mock_health_schema.py -v`  
Expected: FAIL with missing table errors on `MockSupabaseClient`.

- [ ] **Step 3: Write minimal implementation**

Create `migrations/20260808_unified_health_schema.sql`:
```sql
-- Migration for Unified Health Intelligence Schema
CREATE TABLE IF NOT EXISTS biometrics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    date DATE NOT NULL,
    resting_hr INT,
    hrv_ms INT,
    sleep_hours NUMERIC(4,2),
    sleep_score INT,
    recovery_score INT,
    steps INT,
    calories_burned INT,
    raw_source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lab_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    test_date DATE NOT NULL,
    provider_name VARCHAR(100),
    pdf_storage_path TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS biomarkers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id UUID REFERENCES lab_panels(id) ON DELETE CASCADE,
    user_id INT NOT NULL,
    marker_name VARCHAR(100) NOT NULL,
    value NUMERIC(10,2) NOT NULL,
    unit VARCHAR(30),
    ref_range_min NUMERIC(10,2),
    ref_range_max NUMERIC(10,2),
    status VARCHAR(30) DEFAULT 'optimal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

Modify `app/mock_supabase.py` to initialize tables `biometrics_daily`, `lab_panels`, `biomarkers`, `meals`, `athlete_memories`, `health_graph` in `self.tables`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_mock_health_schema.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add migrations/20260808_unified_health_schema.sql app/mock_supabase.py tests/unit/test_mock_health_schema.py
git commit -m "feat(schema): add unified health database tables and mock supabase support"
```

---

### Task 2: Health Hub Ingestion Handler for Wearables

**Files:**
- Create: `app/health_hub/__init__.py`
- Create: `app/health_hub/ingestion_service.py`
- Test: `tests/unit/test_health_ingestion.py`

**Interfaces:**
- Consumes: Database client (`app/supabase_client.py`).
- Produces: `record_daily_biometrics(user_id, metric_dict)` returning stored record dict.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_health_ingestion.py`:
```python
import pytest
from app.health_hub.ingestion_service import record_daily_biometrics

def test_record_daily_biometrics():
    data = {
        'date': '2026-08-08',
        'resting_hr': 52,
        'hrv_ms': 74,
        'sleep_hours': 8.0,
        'recovery_score': 88,
        'raw_source': 'garmin'
    }
    result = record_daily_biometrics(user_id=1, payload=data)
    assert result['user_id'] == 1
    assert result['resting_hr'] == 52
    assert result['raw_source'] == 'garmin'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_health_ingestion.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.health_hub'`

- [ ] **Step 3: Write minimal implementation**

Create `app/health_hub/__init__.py`.
Create `app/health_hub/ingestion_service.py`:
```python
from app.supabase_client import supabase

def record_daily_biometrics(user_id: int, payload: dict) -> dict:
    record = {
        'user_id': user_id,
        'date': payload.get('date'),
        'resting_hr': payload.get('resting_hr'),
        'hrv_ms': payload.get('hrv_ms'),
        'sleep_hours': payload.get('sleep_hours'),
        'sleep_score': payload.get('sleep_score'),
        'recovery_score': payload.get('recovery_score'),
        'steps': payload.get('steps'),
        'calories_burned': payload.get('calories_burned'),
        'raw_source': payload.get('raw_source', 'manual')
    }
    
    res = supabase.table('biometrics_daily').insert(record).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return record
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_health_ingestion.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/health_hub/__init__.py app/health_hub/ingestion_service.py tests/unit/test_health_ingestion.py
git commit -m "feat(health_hub): implement record_daily_biometrics ingestion handler"
```

---

### Task 3: Biomarkers Domain Service & Flagging Logic

**Files:**
- Create: `app/biomarkers/__init__.py`
- Create: `app/biomarkers/service.py`
- Test: `tests/unit/test_biomarkers_service.py`

**Interfaces:**
- Consumes: Supabase / Mock Supabase client.
- Produces: `save_lab_panel(user_id, provider_name, test_date, biomarkers_list)` with automatic reference-range evaluation (`optimal`, `flagged_low`, `flagged_high`).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_biomarkers_service.py`:
```python
import pytest
from app.biomarkers.service import save_lab_panel, get_flagged_biomarkers

def test_save_lab_panel_and_flagging():
    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 12.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'Vitamin D', 'value': 45.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0},
        {'marker_name': 'CRP', 'value': 4.5, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0}
    ]
    
    panel = save_lab_panel(user_id=1, provider_name='Superpower', test_date='2026-08-01', biomarkers=biomarkers)
    assert panel is not None
    
    flagged = get_flagged_biomarkers(user_id=1)
    marker_names = [f['marker_name'] for f in flagged]
    assert 'Ferritin' in marker_names
    assert 'CRP' in marker_names
    assert 'Vitamin D' not in marker_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_biomarkers_service.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.biomarkers'`

- [ ] **Step 3: Write minimal implementation**

Create `app/biomarkers/__init__.py`.
Create `app/biomarkers/service.py`:
```python
from app.supabase_client import supabase

def evaluate_status(value: float, min_val: float = None, max_val: float = None) -> str:
    if min_val is not None and value < min_val:
        return 'flagged_low'
    if max_val is not None and value > max_val:
        return 'flagged_high'
    return 'optimal'

def save_lab_panel(user_id: int, provider_name: str, test_date: str, biomarkers: list) -> dict:
    panel_data = {
        'user_id': user_id,
        'provider_name': provider_name,
        'test_date': test_date
    }
    panel_res = supabase.table('lab_panels').insert(panel_data).execute()
    panel_id = panel_res.data[0]['id'] if panel_res.data else 1
    
    saved_biomarkers = []
    for b in biomarkers:
        status = evaluate_status(b['value'], b.get('ref_range_min'), b.get('ref_range_max'))
        b_record = {
            'panel_id': panel_id,
            'user_id': user_id,
            'marker_name': b['marker_name'],
            'value': b['value'],
            'unit': b.get('unit', ''),
            'ref_range_min': b.get('ref_range_min'),
            'ref_range_max': b.get('ref_range_max'),
            'status': status
        }
        res = supabase.table('biomarkers').insert(b_record).execute()
        if res.data:
            saved_biomarkers.append(res.data[0])
            
    return {'panel_id': panel_id, 'biomarkers': saved_biomarkers}

def get_flagged_biomarkers(user_id: int) -> list:
    res = supabase.table('biomarkers').select('*').eq('user_id', user_id).execute()
    if not res.data:
        return []
    return [b for b in res.data if b.get('status') in ['flagged_low', 'flagged_high']]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_biomarkers_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/biomarkers/__init__.py app/biomarkers/service.py tests/unit/test_biomarkers_service.py
git commit -m "feat(biomarkers): implement lab panel saving and biomarker reference-range evaluation"
```
