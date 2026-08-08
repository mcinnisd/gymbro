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
