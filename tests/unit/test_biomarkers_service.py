import pytest
from app.mock_supabase import MockSupabaseClient
import app.biomarkers.service as service

def test_save_lab_panel_and_flagging(monkeypatch):
    monkeypatch.setattr(service, 'supabase', MockSupabaseClient())
    biomarkers = [
        {'marker_name': 'Ferritin', 'value': 12.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 200.0},
        {'marker_name': 'Vitamin D', 'value': 45.0, 'unit': 'ng/mL', 'ref_range_min': 30.0, 'ref_range_max': 100.0},
        {'marker_name': 'CRP', 'value': 4.5, 'unit': 'mg/L', 'ref_range_min': 0.0, 'ref_range_max': 1.0}
    ]
    
    panel = service.save_lab_panel(user_id=1, provider_name='Superpower', test_date='2026-08-01', biomarkers=biomarkers)
    assert panel is not None
    
    flagged = service.get_flagged_biomarkers(user_id=1)
    marker_names = [f['marker_name'] for f in flagged]
    assert 'Ferritin' in marker_names
    assert 'CRP' in marker_names
    assert 'Vitamin D' not in marker_names
