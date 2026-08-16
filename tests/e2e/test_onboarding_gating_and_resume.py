import pytest
import requests
import uuid
import time

BASE_URL = "http://127.0.0.1:5001"


@pytest.fixture
def athlete_factory():
    def _create(name="Athlete"):
        uid = uuid.uuid4().hex[:6]
        user_data = {
            "username": f"resume_{int(time.time())}_{uid}",
            "password": "Password123!",
            "email": f"resume_{uid}@example.com",
            "name": f"{name} {uid}"
        }
        reg_resp = requests.post(f"{BASE_URL}/auth/register", json=user_data)
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        reg_json = reg_resp.json()
        token = reg_json.get("token") or reg_json.get("access_token")
        return {
            "user_id": reg_json["user"]["id"],
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
            "user": reg_json["user"]
        }
    return _create


def test_new_user_starts_at_step_1_unonboarded(athlete_factory):
    athlete = athlete_factory("Newbie")
    headers = athlete["headers"]

    state_resp = requests.get(f"{BASE_URL}/onboarding/state", headers=headers)
    assert state_resp.status_code == 200
    state = state_resp.json()

    assert state["step"] == 1
    assert state["coach_status"] in ["not_started", "initial"]
    assert state["is_completed"] is False


def test_resume_state_machine_after_interrupted_session(athlete_factory):
    athlete = athlete_factory("Interruptible")
    headers = athlete["headers"]

    # 1. Advance to Step 2
    step1_resp = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 1,
        "data": {"connected_providers": [], "skipped_hardware": True}
    }, headers=headers)
    assert step1_resp.status_code == 200
    assert step1_resp.json()["current_step"] == 2

    # 2. Advance to Step 3 with draft biometrics
    step2_resp = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 2,
        "data": {
            "age": 28,
            "weight": 72.0,
            "height": 178.0,
            "running_experience": "Intermediate"
        }
    }, headers=headers)
    assert step2_resp.status_code == 200
    assert step2_resp.json()["current_step"] == 3

    # 3. Simulate App Restart (re-fetch state)
    state_after_restart = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state_after_restart["step"] == 3
    assert state_after_restart["coach_status"] == "in_onboarding"
    assert state_after_restart["athlete_profile"]["age"] == 28
    assert state_after_restart["athlete_profile"]["weight"] == 72.0

    # 4. Advance to Step 4 from resumed position
    step3_resp = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 3,
        "data": {
            "primary_goal": "muscle_strength",
            "days_available": ["Tuesday", "Thursday", "Saturday"]
        }
    }, headers=headers)
    assert step3_resp.status_code == 200
    assert step3_resp.json()["current_step"] == 4

    # 5. Verify resumed state accurately reports Step 4
    state_step_4 = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state_step_4["step"] == 4
    assert state_step_4["goal_set"]["primary_goal"] == "muscle_strength"
    assert state_step_4["goal_set"]["days_available"] == ["Tuesday", "Thursday", "Saturday"]


def test_complete_onboarding_transitions_to_active(athlete_factory):
    athlete = athlete_factory("Finisher")
    headers = athlete["headers"]

    # Generate proposal
    prop_resp = requests.post(f"{BASE_URL}/onboarding/generate-proposal", json={
        "horizon": "4_week_foundation"
    }, headers=headers)
    assert prop_resp.status_code == 200
    proposal = prop_resp.json()["proposal"]

    # Commit proposal
    commit_resp = requests.post(f"{BASE_URL}/onboarding/commit", json={
        "proposal": proposal
    }, headers=headers)
    assert commit_resp.status_code == 200
    commit_json = commit_resp.json()
    assert commit_json["coach_status"] == "active"
    assert commit_json["events_created"] > 0

    # Verify state reports completed
    state_final = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state_final["coach_status"] == "active"
    assert state_final["is_completed"] is True
