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
