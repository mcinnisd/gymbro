import pytest
import requests
import uuid
import time

BASE_URL = "http://127.0.0.1:5001"


@pytest.fixture
def new_athlete():
    uid = uuid.uuid4().hex[:6]
    user_data = {
        "username": f"athlete_step_{int(time.time())}_{uid}",
        "password": "Password123!",
        "email": f"athlete_step_{uid}@example.com",
        "name": f"Step Athlete {uid}"
    }
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json=user_data)
    assert reg_resp.status_code == 201
    reg_json = reg_resp.json()
    token = reg_json.get("token") or reg_json.get("access_token")
    return {
        "user_id": reg_json["user"]["id"],
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user": reg_json["user"]
    }


def test_step_1_wearable_connect_and_prepopulate_trigger(new_athlete):
    headers = new_athlete["headers"]

    # 1. Trigger prepopulate with raw telemetry (HealthKit simulated payload)
    prepop_payload = {
        "source": "apple_health",
        "biometrics": {
            "resting_heart_rate": 56,
            "hrv_sdnn": 68.5,
            "sleep_hours": 8.0,
            "weight_kg": 76.5,
            "height_cm": 182.0,
            "age": 29,
            "biological_sex": "male"
        },
        "activities": [
            {
                "type": "running",
                "distance_km": 10.0,
                "duration_min": 50.0,
                "timestamp": "2026-08-15T08:00:00Z"
            },
            {
                "type": "running",
                "distance_km": 15.0,
                "duration_min": 75.0,
                "timestamp": "2026-08-12T08:00:00Z"
            }
        ]
    }
    prepop_resp = requests.post(f"{BASE_URL}/onboarding/prepopulate", json=prepop_payload, headers=headers)
    assert prepop_resp.status_code == 200
    prepop_data = prepop_resp.json()
    assert prepop_data["data_available"] is True
    assert prepop_data["resting_hr"] == 56
    assert prepop_data["age"] == 29
    assert prepop_data["acute_weekly_volume_km"] > 0

    # 2. Persist Step 1 completion
    step1_resp = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 1,
        "data": {
            "connected_providers": ["apple_health"],
            "skipped_hardware": False
        }
    }, headers=headers)
    assert step1_resp.status_code == 200
    assert step1_resp.json()["current_step"] == 2


def test_step_2_smart_profile_confirmation_and_manual_overrides(new_athlete):
    headers = new_athlete["headers"]

    # Save Step 2 with verified metrics
    step2_payload = {
        "step": 2,
        "data": {
            "age": 29,
            "weight": 77.0,
            "height": 182.0,
            "biological_sex": "male",
            "sport_history": "Distance Running & Calisthenics",
            "running_experience": "Intermediate",
            "resting_hr": 55,
            "hrv": 70,
            "sleep_hours": 8.2
        }
    }
    step2_resp = requests.post(f"{BASE_URL}/onboarding/step", json=step2_payload, headers=headers)
    assert step2_resp.status_code == 200
    assert step2_resp.json()["current_step"] == 3

    # Check state persistence
    state = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state["step"] == 3
    assert state["athlete_profile"]["age"] == 29
    assert state["athlete_profile"]["weight"] == 77.0
    assert state["athlete_profile"]["sport_history"] == "Distance Running & Calisthenics"


def test_step_3_ranked_goal_set_and_availability(new_athlete):
    headers = new_athlete["headers"]

    # Save Step 3 multi-goal ranking
    step3_payload = {
        "step": 3,
        "data": {
            "primary_goal": "marathon_endurance",
            "secondary_goals": ["muscle_strength", "longevity_aerobic"],
            "days_available": ["Monday", "Wednesday", "Friday", "Sunday"],
            "equipment": "Full Gym + Outdoor Trails"
        }
    }
    step3_resp = requests.post(f"{BASE_URL}/onboarding/step", json=step3_payload, headers=headers)
    assert step3_resp.status_code == 200
    assert step3_resp.json()["current_step"] == 4

    # Verify state reflects Step 4 with complete Goal Set
    state = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state["step"] == 4
    assert state["goal_set"]["primary_goal"] == "marathon_endurance"
    assert "muscle_strength" in state["goal_set"]["secondary_goals"]
    assert len(state["goal_set"]["days_available"]) == 4
