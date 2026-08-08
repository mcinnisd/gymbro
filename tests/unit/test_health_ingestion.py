import pytest
from app.mock_supabase import MockSupabaseClient
import app.health_hub.ingestion_service as ingestion_service

def test_record_daily_biometrics(monkeypatch):
    monkeypatch.setattr(ingestion_service, 'supabase', MockSupabaseClient())
    data = {
        'date': '2026-08-08',
        'resting_hr': 52,
        'hrv_ms': 74,
        'sleep_hours': 8.0,
        'recovery_score': 88,
        'raw_source': 'garmin'
    }
    result = ingestion_service.record_daily_biometrics(user_id=1, payload=data)
    assert result['user_id'] == 1
    assert result['resting_hr'] == 52
    assert result['raw_source'] == 'garmin'
