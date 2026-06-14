import pytest
import requests
import time
import uuid
from app.supabase_client import supabase

BASE_URL = "http://127.0.0.1:5001"

@pytest.fixture(scope="module")
def auth_info():
    username = f"an_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    password = "password123"
    
    # Register
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    user_id = resp.json()["user_id"]
    
    # Login
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["token"]
    
    return {"Authorization": f"Bearer {token}"}, user_id

@pytest.fixture(scope="module")
def seed_analytics(auth_info):
    headers, user_id = auth_info
    
    # Seed User Baselines
    dummy_baselines = {
        "user_id": user_id,
        "metric_category": "running",
        "baselines": {
            "pbs": {
                "5k": {
                    "time_seconds": 1200.0,
                    "formatted_time": "20:00",
                    "date": "2026-06-14"
                }
            },
            "volume": {
                "avg_weekly_dist_4w": 35.0,
                "avg_weekly_dist_12w": 30.0,
                "max_volume_week": 42.0,
                "current_streak_weeks": 3
            },
            "longest_run": {
                "distance_km": 15.0,
                "date": "2026-06-14"
            }
        }
    }
    supabase.table("user_baselines").insert(dummy_baselines).execute()
    
    # Seed Garmin Activity for 90 days query
    dummy_act = {
        "user_id": user_id,
        "activity_id": f"an_act_{uuid.uuid4().hex[:8]}",
        "activity_name": "Morning Run",
        "start_time_local": "2026-06-14T07:00:00",
        "distance": 10000.0,
        "duration": 3000.0,
        "calories": 700.0,
        "activity_type": "running",
        "average_hr": 145.0
    }
    supabase.table("garmin_activities").insert(dummy_act).execute()
    
    # Seed Daily for Wellness RHR/Stress
    dummy_daily = {
        "user_id": user_id,
        "date": "2026-06-14",
        "steps": {"totalSteps": 15000},
        "resting_hr": 52,
        "stress": 22
    }
    supabase.table("garmin_daily").insert(dummy_daily).execute()

def test_get_baselines(auth_info, seed_analytics):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/analytics/baselines", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    baselines = resp.json()
    assert "pbs" in baselines
    assert baselines["pbs"]["5k"]["formatted_time"] == "20:00"

def test_get_analytics_summary(auth_info, seed_analytics):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/analytics/summary", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    summary = resp.json()
    
    # Verify breakdown
    assert "breakdown" in summary
    assert "running" in summary["breakdown"]
    assert summary["breakdown"]["running"]["count"] >= 1
    
    # Verify sports
    assert "sports" in summary
    assert "running" in summary["sports"]
    assert summary["sports"]["running"]["count"] >= 1
    
    # Verify wellness
    assert "wellness" in summary
    assert len(summary["wellness"]["rhr_trend"]) >= 1
    assert summary["wellness"]["rhr_trend"][0]["val"] == 52
