import pytest
from datetime import datetime, timedelta, timezone
from app.analytics.analytics_service import AnalyticsService
from app.supabase_client import supabase

def test_analyze_wellness_deep_telemetry():
    user_id = "test_analytics_user"
    today = datetime.now(timezone.utc).date()
    
    # Insert test data into biometrics_daily
    test_rows = []
    for i in range(10):
        d_str = (today - timedelta(days=i)).isoformat()
        test_rows.append({
            "user_id": user_id,
            "date": d_str,
            "resting_hr": 55 + i,
            "hrv": 65 - i,
            "sleep_score": 80 + i,
            "sleep_hours": 7.5,
            "stress_level": 25 + i,
            "vo2_max": 52.0 + (i * 0.1),
            "fitness_age": 28,
            "body_battery": 85 - i,
            "sleep_stages": {"deep": 5400, "rem": 6000, "light": 14400, "awake": 1200},
            "training_status": "PRODUCTIVE" if i % 2 == 0 else "MAINTAINING",
            "spo2": 98 - (i % 2),
            "respiration": 14.5,
            "source": "garmin"
        })
    
    for row in test_rows:
        supabase.table("biometrics_daily").upsert(row, on_conflict="user_id, date").execute()
        
    start_date = (today - timedelta(days=365)).isoformat()
    wellness = AnalyticsService._analyze_wellness(user_id, start_date)
    
    assert "vo2_max_trend" in wellness
    assert len(wellness["vo2_max_trend"]) > 0
    assert "body_battery_trend" in wellness
    assert len(wellness["body_battery_trend"]) > 0
    assert "sleep_stage_trend" in wellness
    assert len(wellness["sleep_stage_trend"]) > 0
    assert "spo2_trend" in wellness
    assert len(wellness["spo2_trend"]) > 0
    assert "training_status_summary" in wellness
    assert wellness["training_status_summary"] in ["PRODUCTIVE", "MAINTAINING"]


def test_get_analytics_summary_365_days(client, auth_headers):
    # Test GET /analytics/summary?days=365 endpoint
    res = client.get("/analytics/summary?days=365", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "wellness" in data
    wellness = data["wellness"]
    assert "rhr_trend" in wellness
    assert "vo2_max_trend" in wellness
    assert "body_battery_trend" in wellness
    assert "sleep_stage_trend" in wellness
    assert "spo2_trend" in wellness
    assert "training_status_summary" in wellness
