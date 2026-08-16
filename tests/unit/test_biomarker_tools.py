import pytest
from app.mock_supabase import MockSupabaseClient
import app.biomarkers.service as service
from app.tools.biomarker_tools import get_biomarkers, get_biomarker_trends_tool
from app.tools.registry import get_tool_definitions, get_tool_implementation

def test_tool_registry_contains_biomarkers():
    defs = get_tool_definitions()
    names = [d['function']['name'] for d in defs]
    assert 'get_biomarkers' in names
    assert 'get_biomarker_trends' in names

    assert get_tool_implementation('get_biomarkers') is get_biomarkers
    assert get_tool_implementation('get_biomarker_trends') is get_biomarker_trends_tool


def test_get_biomarkers_tool_empty(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    res = get_biomarkers(user_id='99')
    assert res['status'] == 'success'
    assert res['count'] == 0


def test_get_biomarkers_tool_with_data(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 18.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 2.5, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0},
        {'marker_name': 'Vitamin D 25-OH', 'value': 62.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0}
    ]
    service.save_lab_panel(user_id=1, provider_name='Superpower', test_date='2026-08-01', biomarkers=biomarkers)

    # 1. Fetch all
    res_all = get_biomarkers(user_id='1')
    assert res_all['status'] == 'success'
    assert res_all['count'] == 3

    # 2. Flagged only
    res_flagged = get_biomarkers(user_id='1', flagged_only=True)
    assert res_flagged['status'] == 'success'
    assert res_flagged['count'] == 2

    # 3. Filter by marker
    res_ferritin = get_biomarkers(user_id='1', marker_name='Ferritin')
    assert res_ferritin['count'] == 1
    assert res_ferritin['biomarkers'][0]['marker_name'] == 'Ferritin'


def test_get_biomarker_trends_tool_generates_widget(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    panel1 = [
        {'marker_name': 'Ferritin', 'value': 22.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0}
    ]
    panel2 = [
        {'marker_name': 'Ferritin', 'value': 54.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0}
    ]
    service.save_lab_panel(user_id=1, provider_name='Quest', test_date='2025-08-01', biomarkers=panel1)
    service.save_lab_panel(user_id=1, provider_name='LabCorp', test_date='2026-08-01', biomarkers=panel2)

    res = get_biomarker_trends_tool(user_id='1', marker_name='Ferritin')
    assert res['status'] == 'success'
    assert res['count'] >= 1
    assert 'widget' in res

    widget = res['widget']
    assert widget['protocol'] == 'gymbro.widget/v1'
    assert widget['widget_type'] == 'interactive_chart'
    assert 'Ferritin' in widget['title']
    assert len(widget['payload']['points']) == 2
    assert widget['payload']['interactive_scrubbing'] is True
