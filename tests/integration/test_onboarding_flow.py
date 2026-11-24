import time
import uuid

import pytest
import requests

from app.supabase_client import supabase

BASE_URL = "http://127.0.0.1:5001"


@pytest.fixture
def new_athlete():
    uid = uuid.uuid4().hex[:6]
    reg = requests.post(f"{BASE_URL}/auth/register", json={
        "username": f"onboard_{int(time.time())}_{uid}", "password": "Password123!",
        "email": f"athlete_{uid}@example.com", "name": f"Athlete {uid}",
    })
    assert reg.status_code == 201, reg.text
    body = reg.json()
    token = body.get("token") or body.get("access_token")
    return {"user_id": body["user"]["id"], "headers": {"Authorization": f"Bearer {token}"}}


def _step(headers, step, data):
    res = requests.post(f"{BASE_URL}/onboarding/step", json={"step": step, "data": data}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_unauthenticated_onboarding_is_rejected():
    for method, path, body in (
        ("get", "/onboarding/state", None),
        ("post", "/onboarding/step", {"step": 1}),
        ("post", "/onboarding/prepopulate", {}),
        ("post", "/onboarding/commit", {}),
    ):
        res = getattr(requests, method)(f"{BASE_URL}{path}", json=body)
        assert res.status_code in (401, 422)


def test_complete_5_step_onboarding_lifecycle(new_athlete):
    headers, user_id = new_athlete["headers"], new_athlete["user_id"]
    state = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state["step"] == 1 and state["is_completed"] is False
    pre = requests.post(f"{BASE_URL}/onboarding/prepopulate", headers=headers, json={
        "source": "apple_health",
        "biometrics": [{"date": "2026-08-14", "resting_hr": 52, "hrv": 70, "sleep_hours": 8.0, "steps": 11500}],
        "activities": [{"activity_id": "hk_run_step1", "activity_type": "running", "name": "Base Run", "distance": 7000, "duration": 2100, "start_time_local": "2026-08-14T07:30:00Z"}],
    })
    assert pre.status_code == 200 and pre.json()["resting_hr"] == 52 and pre.json()["hrv"] == 70
    assert _step(headers, 1, {"connected_providers": ["apple_health"], "skipped_hardware": False})["current_step"] == 2
    assert _step(headers, 2, {"age": 31, "weight": 77.0, "height": 182.0, "biological_sex": "male", "sport_history": "Running", "running_experience": "Intermediate", "resting_hr": 52, "hrv": 70})["current_step"] == 3
    assert supabase.table("users").select("age,weight").eq("id", user_id).execute().data[0]["age"] == 31
    assert _step(headers, 3, {"primary_goal": "marathon_endurance", "days_available": ["Monday"], "target_date": "2026-11-15"})["current_step"] == 4
    assert _step(headers, 4, {"horizon": "4_week_foundation", "calibration_confirmed": True})["current_step"] == 5
    prop = requests.post(f"{BASE_URL}/onboarding/generate-proposal", json={"horizon": "4_week_foundation"}, headers=headers)
    assert prop.status_code == 200
    widget = prop.json()["widget"]
    assert widget["protocol"] == "gymbro.widget/v1" and widget["widget_type"] == "calendar_proposal"
    commit = requests.post(f"{BASE_URL}/onboarding/commit", json={"proposal": prop.json()["proposal"]}, headers=headers)
    assert commit.status_code == 200 and commit.json()["events_created"] > 0 and commit.json()["coach_status"] == "active"
    done = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert done["is_completed"] is True and done["coach_status"] == "active"


def test_onboarding_multi_tenant_isolation(new_athlete):
    uid = uuid.uuid4().hex[:6]
    reg = requests.post(f"{BASE_URL}/auth/register", json={"username": f"b_{uid}", "password": "PasswordB123!", "email": f"b_{uid}@example.com"}).json()
    headers_b = {"Authorization": f"Bearer {reg.get('token') or reg.get('access_token')}"}
    _step(new_athlete["headers"], 2, {"age": 45, "primary_goal": "fat_loss"})
    state_b = requests.get(f"{BASE_URL}/onboarding/state", headers=headers_b).json()
    assert state_b["step"] == 1 and state_b["athlete_profile"]["age"] is None
