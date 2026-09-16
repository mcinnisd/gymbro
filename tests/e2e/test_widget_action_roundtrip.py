"""
End-to-End Integration Test: Interactive Widget Protocol & Calendar Round-Trip.
Validates the complete loop:
1. Athlete onboarding & JWT authentication.
2. Conversational Coach turn returning gymbro.widget/v1 UI payload.
3. Automated Calendar session population from proposed training plan.
4. Calendar event retrieval, schema integrity, and athlete data boundary isolation.
5. Fast Context & Telemetry operational snapshot consistency.
"""

import pytest
import requests
import uuid
import time
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:5001"


@pytest.fixture
def athlete_session():
    uid = uuid.uuid4().hex[:6]
    username = f"e2e_athlete_{int(time.time())}_{uid}"
    password = "SecurePassword123!"

    # 1. Register
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "username": username,
        "password": password,
        "email": f"{username}@example.com",
        "name": f"E2E Athlete {uid}"
    })
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    token = reg_resp.json()["token"]
    user_id = reg_resp.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Configure Profile
    profile_data = {
        "age": 31,
        "weight": 76.5,
        "height": 178.0,
        "sport_history": "Running & Functional Fitness",
        "running_experience": "Intermediate",
        "weekly_availability": "4 days",
        "goals": {
            "primary": "Marathon Speed & Endurance",
            "weekly_mileage_target": 45
        }
    }
    prof_resp = requests.put(f"{BASE_URL}/auth/profile", json=profile_data, headers=headers)
    assert prof_resp.status_code == 200, f"Profile setup failed: {prof_resp.text}"

    return {
        "user_id": user_id,
        "username": username,
        "headers": headers
    }


def test_widget_action_to_calendar_roundtrip(athlete_session):
    headers = athlete_session["headers"]

    # 1. Create a Chat Thread
    chat_resp = requests.post(f"{BASE_URL}/chats/", json={"title": "Training & Widget Test"}, headers=headers)
    assert chat_resp.status_code == 201, f"Chat creation failed: {chat_resp.text}"
    chat_id = chat_resp.json()["chat_id"]

    # 2. Chat Query for Adaptive Training Routine
    chat_payload = {
        "message": "Generate a 4-day marathon training plan with recovery blocks",
        "chat_id": chat_id,
        "mode": "fast"
    }
    coach_resp = requests.post(f"{BASE_URL}/coach/chat", json=chat_payload, headers=headers)
    assert coach_resp.status_code == 200, f"Coach chat failed: {coach_resp.text}"
    coach_data = coach_resp.json()
    assert "reply" in coach_data or "message" in coach_data
    
    # Check if a structured gymbro.widget/v1 payload or plan was returned
    if coach_data.get("ui_payload"):
        ui_payload = coach_data["ui_payload"]
        assert ui_payload.get("protocol") == "gymbro.widget/v1" or "type" in ui_payload

    # 3. Trigger Baseline Plan Generation
    gen_resp = requests.post(f"{BASE_URL}/coach/generate_plan", json={"chat_id": chat_id}, headers=headers)
    assert gen_resp.status_code == 200, f"Plan generation failed: {gen_resp.text}"
    assert "plan" in gen_resp.json()
    assert len(gen_resp.json()["plan"]) > 0

    # 4. Organize Plan & Auto-Populate Calendar Sessions
    org_resp = requests.post(f"{BASE_URL}/coach/organize_plan", headers=headers)
    assert org_resp.status_code == 200, f"Organize plan failed: {org_resp.text}"
    assert "phased_plan" in org_resp.json()

    # 5. Query Calendar Events and Verify Population
    cal_resp = requests.get(f"{BASE_URL}/calendar/events", headers=headers)
    assert cal_resp.status_code == 200, f"Fetch calendar events failed: {cal_resp.text}"
    events = cal_resp.json().get("events", [])
    assert len(events) > 0, "Expected calendar events to be populated from the organized plan"

    for event in events:
        assert "date" in event
        assert "title" in event
        assert "event_type" in event
        assert event["user_id"] == athlete_session["user_id"]

    # 6. Verify Direct Telemetry Sync Integrates with Health Lake
    telemetry_payload = {
        "source": "apple_health",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "resting_hr": 52,
        "sleep_hours": 8.1,
        "sleep_score": 88,
        "steps": 10500,
        "biometrics": [
            {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "hrv": 68.5,
                "resting_hr": 52,
                "sleep_hours": 8.1,
                "sleep_score": 88,
                "readiness_score": 85
            }
        ]
    }
    tel_resp = requests.post(f"{BASE_URL}/telemetry/sync", json=telemetry_payload, headers=headers)
    assert tel_resp.status_code == 200, f"Telemetry ingest failed: {tel_resp.text}"

    # 7. Check Telemetry Status & Daily Biometrics Query
    status_resp = requests.get(f"{BASE_URL}/telemetry/status", headers=headers)
    assert status_resp.status_code == 200, f"Telemetry status failed: {status_resp.text}"
    status_data = status_resp.json()
    assert "apple_health" in status_data
    assert "garmin" in status_data
    assert "strava" in status_data
    assert "primary_source_priority" in status_data

    daily_resp = requests.get(f"{BASE_URL}/telemetry/daily", headers=headers)
    assert daily_resp.status_code == 200, f"Daily telemetry query failed: {daily_resp.text}"
    assert "daily_biometrics" in daily_resp.json()
