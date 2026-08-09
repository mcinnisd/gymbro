import pytest
import requests
import time
import uuid
from app.supabase_client import supabase

BASE_URL = "http://127.0.0.1:5001"

@pytest.fixture(scope="module")
def auth_info():
    username = f"nut_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
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

def test_nutrition_endpoints(auth_info):
    headers, user_id = auth_info
    
    # 1. Log Meal
    meal_data = {
        "meal_name": "Chicken Salad",
        "calories": 450,
        "protein": 35,
        "carbs": 15,
        "fat": 20,
        "date": "2026-06-14"
    }
    
    resp = requests.post(f"{BASE_URL}/nutrition/log", json=meal_data, headers=headers)
    assert resp.status_code == 201, f"Failed to log meal: {resp.text}"
    log = resp.json()["log"]
    assert log["meal_name"] == "Chicken Salad"
    assert float(log["calories"]) == 450.0
    
    # 2. Get Nutrition History
    resp = requests.get(f"{BASE_URL}/nutrition/history?start_date=2026-06-14&end_date=2026-06-14", headers=headers)
    assert resp.status_code == 200, f"Failed to get history: {resp.text}"
    history = resp.json()
    assert len(history["logs"]) >= 1
    assert "2026-06-14" in history["daily_summaries"]
    assert history["daily_summaries"]["2026-06-14"]["calories"] == 450.0
    assert history["daily_summaries"]["2026-06-14"]["protein"] == 35.0

def test_journal_endpoints(auth_info):
    headers, user_id = auth_info
    
    # 1. Save Journal
    journal_data = {
        "date": "2026-06-14",
        "answers": {
            "soreness": "legs",
            "energy_level": 7,
            "notes": "Good session, slightly tight calves."
        }
    }
    
    resp = requests.post(f"{BASE_URL}/journal", json=journal_data, headers=headers)
    assert resp.status_code == 200, f"Failed to save journal: {resp.text}"
    assert resp.json()["message"] == "Journal saved successfully."
    
    # 2. Get Journal
    resp = requests.get(f"{BASE_URL}/journal/2026-06-14", headers=headers)
    assert resp.status_code == 200, f"Failed to get journal: {resp.text}"
    journal = resp.json()["journal"]
    assert journal["answers"]["soreness"] == "legs"
    assert journal["answers"]["energy_level"] == 7
