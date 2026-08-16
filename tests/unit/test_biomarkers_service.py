import pytest
from app.mock_supabase import MockSupabaseClient
import app.biomarkers.service as service

def test_save_lab_panel_and_flagging(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)
    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 12.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'Vitamin D', 'value': 45.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0},
        {'marker_name': 'CRP', 'value': 4.5, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0}
    ]
    
    panel = service.save_lab_panel(user_id=1, provider_name='Superpower', test_date='2026-08-01', biomarkers=biomarkers)
    assert panel is not None
    assert panel.get('panel_id') is not None
    
    flagged = service.get_flagged_biomarkers(user_id=1)
    marker_names = [f['marker_name'] for f in flagged]
    assert 'Ferritin' in marker_names
    assert any('CRP' in m or 'hs-CRP' in m for m in marker_names)
    assert 'Vitamin D 25-OH' not in marker_names and 'Vitamin D' not in marker_names


def test_get_user_panels(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    biomarkers1 = [
        {'marker_name': 'Ferritin', 'value': 25.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 0.6, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0}
    ]
    biomarkers2 = [
        {'marker_name': 'Ferritin', 'value': 55.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 0.4, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0}
    ]

    service.save_lab_panel(user_id=10, provider_name='Quest', test_date='2025-08-01', biomarkers=biomarkers1)
    service.save_lab_panel(user_id=10, provider_name='LabCorp', test_date='2026-08-01', biomarkers=biomarkers2)

    panels = service.get_user_panels(user_id=10)
    assert len(panels) == 2
    # Check that panels are returned with metadata and biomarker counts
    assert panels[0]['total_biomarkers'] == 2
    assert 'flagged_count' in panels[0]


def test_get_panel_details(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 25.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'Vitamin D 25-OH', 'value': 60.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0}
    ]
    res = service.save_lab_panel(user_id=11, provider_name='InsideTracker', test_date='2026-08-01', biomarkers=biomarkers)
    panel_id = res['panel_id']

    details = service.get_panel_details(user_id=11, panel_id=panel_id)
    assert details is not None
    assert details['provider_name'] == 'InsideTracker'
    assert len(details['biomarkers']) == 2
    assert 'categories' in details


def test_longitudinal_biomarker_trends(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    # Panel 1: August 2025 (Ferritin low at 20, hs-CRP high at 3.0)
    panel1 = [
        {'marker_name': 'Ferritin', 'value': 20.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 3.0, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0},
        {'marker_name': 'Vitamin D 25-OH', 'value': 32.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0}
    ]
    service.save_lab_panel(user_id=12, provider_name='Quest', test_date='2025-08-01', biomarkers=panel1)

    # Panel 2: February 2026 (Ferritin 35, hs-CRP 1.8, Vitamin D 45)
    panel2 = [
        {'marker_name': 'Ferritin', 'value': 35.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 1.8, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0},
        {'marker_name': 'Vitamin D 25-OH', 'value': 45.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0}
    ]
    service.save_lab_panel(user_id=12, provider_name='LabCorp', test_date='2026-02-01', biomarkers=panel2)

    # Panel 3: August 2026 (Ferritin 60, hs-CRP 0.6, Vitamin D 58)
    panel3 = [
        {'marker_name': 'Ferritin', 'value': 60.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 0.6, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0},
        {'marker_name': 'Vitamin D 25-OH', 'value': 58.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0}
    ]
    service.save_lab_panel(user_id=12, provider_name='Superpower', test_date='2026-08-01', biomarkers=panel3)

    trends = service.get_biomarker_trends(user_id=12)
    assert len(trends) >= 3

    ferritin_trend = next((t for t in trends if t['marker_name'] == 'Ferritin'), None)
    assert ferritin_trend is not None
    assert ferritin_trend['baseline_value'] == 20.0
    assert ferritin_trend['latest_value'] == 60.0
    assert ferritin_trend['delta'] == 40.0
    assert ferritin_trend['percent_change'] == 200.0
    assert ferritin_trend['trend_direction'] == 'improving'
    assert len(ferritin_trend['data_points']) == 3

    crp_trend = next((t for t in trends if t['marker_name'] == 'hs-CRP'), None)
    assert crp_trend is not None
    assert crp_trend['baseline_value'] == 3.0
    assert crp_trend['latest_value'] == 0.6
    assert crp_trend['delta'] == -2.4
    assert crp_trend['trend_direction'] == 'improving'


def test_get_biomarker_summary(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 22.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'hs-CRP', 'value': 0.5, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0},
        {'marker_name': 'Vitamin D 25-OH', 'value': 55.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0}
    ]
    service.save_lab_panel(user_id=13, provider_name='Function Health', test_date='2026-08-01', biomarkers=biomarkers)

    summary = service.get_biomarker_summary(user_id=13)
    assert summary is not None
    assert summary['latest_panel_date'] == '2026-08-01'
    assert summary['provider_name'] == 'Function Health'
    assert summary['optimal_count'] == 2
    assert summary['flagged_low_count'] == 1
    assert summary['flagged_high_count'] == 0
    assert len(summary['flagged_biomarkers']) == 1


def test_delete_lab_panel(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)

    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 50.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0}
    ]
    res = service.save_lab_panel(user_id=14, provider_name='Quest', test_date='2026-08-01', biomarkers=biomarkers)
    panel_id = res['panel_id']

    assert len(service.get_user_panels(user_id=14)) == 1

    del_res = service.delete_lab_panel(user_id=14, panel_id=panel_id)
    assert del_res is True
    assert len(service.get_user_panels(user_id=14)) == 0
