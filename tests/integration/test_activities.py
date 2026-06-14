import pytest
import requests
import time
import uuid
import os
from app.supabase_client import supabase

BASE_URL = "http://127.0.0.1:5001"

@pytest.fixture(scope="module")
def auth_info():
    username = f"act_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
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
def seed_data(auth_info):
    headers, user_id = auth_info
    
    # Seed Garmin Activity
    activity_id = f"test_act_{uuid.uuid4().hex[:8]}"
    dummy_activity = {
        "user_id": user_id,
        "activity_id": activity_id,
        "activity_name": "Test Run",
        "start_time_local": "2026-06-14T08:00:00",
        "distance": 8000.0,
        "duration": 2400.0,
        "calories": 600.0,
        "activity_type": "running",
        "details": {}
    }
    supabase.table("garmin_activities").insert(dummy_activity).execute()
    
    # Seed Garmin Daily Metrics
    dummy_daily = {
        "user_id": user_id,
        "date": "2026-06-14",
        "steps": {"totalSteps": 12000},
        "resting_hr": 58,
        "heartrate": {"minHeartRate": 55, "maxHeartRate": 150}
    }
    supabase.table("garmin_daily").insert(dummy_daily).execute()
    
    # Seed Garmin Sleep
    dummy_sleep = {
        "user_id": user_id,
        "date": "2026-06-14",
        "sleep_data": {
            "dailySleepDTO": {
                "sleepTimeSeconds": 27000 # 7.5 hours
            }
        }
    }
    supabase.table("garmin_sleep").insert(dummy_sleep).execute()
    
    yield activity_id
    
    # Cleanup (Cascades delete due to foreign key constraints if user is deleted, 
    # but we can also just leave it since it's a test db).

def test_get_activities(auth_info, seed_data):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/activities", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    activities = resp.json()["activities"]
    assert len(activities) >= 1
    assert any(a["activity_id"] == seed_data for a in activities)

def test_get_activity_details(auth_info, seed_data):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/activities/{seed_data}", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    activity = resp.json()
    assert activity["activity_name"] == "Test Run"
    assert activity["distance"] == 8000.0

def test_get_activity_stats(auth_info, seed_data):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/activities/stats", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    stats = resp.json()
    assert stats["total_activities"] >= 1
    assert stats["total_distance_km"] >= 8.0

def test_get_activities_summary(auth_info, seed_data):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/activities/summary", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    summary = resp.json()
    assert summary["workouts"] >= 1
    assert summary["calories_burned"] >= 600

def test_get_daily_stats(auth_info, seed_data):
    headers, user_id = auth_info
    
    resp = requests.get(f"{BASE_URL}/activities/daily_stats", headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    stats = resp.json()
    assert len(stats) >= 1
    assert stats[0]["date"] == "2026-06-14"
    assert stats[0]["steps"] == 12000
    assert stats[0]["resting_hr"] == 58
    assert stats[0]["sleep_hours"] == 7.5
