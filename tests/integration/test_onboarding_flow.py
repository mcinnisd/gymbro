import pytest
import requests
import uuid
import time
from app.supabase_client import supabase

BASE_URL = "http://127.0.0.1:5001"


@pytest.fixture
def new_athlete():
    uid = uuid.uuid4().hex[:6]
    user_data = {
        "username": f"onboard_athlete_{int(time.time())}_{uid}",
        "password": "Password123!",
        "email": f"athlete_{uid}@example.com",
        "name": f"Onboarding Athlete {uid}"
    }

    # Register
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json=user_data)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    reg_json = reg_resp.json()
    token = reg_json.get("token") or reg_json.get("access_token")
    user_id = reg_json["user"]["id"]

    return {
        "user_id": user_id,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "username": user_data["username"]
    }


def test_unauthenticated_onboarding_access_rejected():
    resp = requests.get(f"{BASE_URL}/onboarding/state")
    assert resp.status_code in [401, 422]

    resp_step = requests.post(f"{BASE_URL}/onboarding/step", json={"step": 1})
    assert resp_step.status_code in [401, 422]

    resp_prepop = requests.post(f"{BASE_URL}/onboarding/prepopulate", json={})
    assert resp_prepop.status_code in [401, 422]

    resp_commit = requests.post(f"{BASE_URL}/onboarding/commit", json={})
    assert resp_commit.status_code in [401, 422]


def test_complete_5_step_onboarding_lifecycle(new_athlete):
    headers = new_athlete["headers"]
    user_id = new_athlete["user_id"]

    # -------------------------------------------------------------
    # 0. Initial State Check
    # -------------------------------------------------------------
    state_res = requests.get(f"{BASE_URL}/onboarding/state", headers=headers)
    assert state_res.status_code == 200, f"Get state failed: {state_res.text}"
    state = state_res.json()

    assert state["step"] == 1
    assert state["coach_status"] in ["not_started", "initial"]
    assert "athlete_profile" in state
    assert "prepopulated_biometrics" in state
    assert "goal_set" in state
    assert state["is_completed"] is False

    # -------------------------------------------------------------
    # 1. Step 1: Wearable Linking / Skip & Prepopulation
    # -------------------------------------------------------------
    # Athlete links Apple Health payload
    health_payload = {
        "source": "apple_health",
        "biometrics": [
            {
                "date": "2026-08-14",
                "resting_hr": 52,
                "hrv": 70,
                "sleep_hours": 8.0,
                "steps": 11500
            }
        ],
        "activities": [
            {
                "activity_id": "hk_run_step1",
                "activity_type": "running",
                "name": "Base Run",
                "distance": 7000.0,
                "duration": 2100.0,
                "start_time_local": "2026-08-14T07:30:00Z"
            }
        ]
    }

    prepop_res = requests.post(f"{BASE_URL}/onboarding/prepopulate", json=health_payload, headers=headers)
    assert prepop_res.status_code == 200, f"Prepopulate failed: {prepop_res.text}"
    prepop_data = prepop_res.json()
    assert prepop_data["data_available"] is True
    assert prepop_data["resting_hr"] == 52
    assert prepop_data["hrv"] == 70
    assert prepop_data["sleep_hours"] == 8.0

    # Save Step 1
    step1_res = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 1,
        "data": {
            "connected_providers": ["apple_health"],
            "skipped_hardware": False
        }
    }, headers=headers)
    assert step1_res.status_code == 200
    assert step1_res.json()["current_step"] == 2
    assert step1_res.json()["coach_status"] == "in_onboarding"

    # -------------------------------------------------------------
    # 2. Step 2: Smart Profile & Baseline Confirmation
    # -------------------------------------------------------------
    step2_res = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 2,
        "data": {
            "age": 31,
            "weight": 77.0,
            "height": 182.0,
            "biological_sex": "male",
            "sport_history": "Running & Functional Strength",
            "running_experience": "Intermediate",
            "past_injuries": "Minor left knee soreness 6 months ago",
            "resting_hr": 52,
            "hrv": 70
        }
    }, headers=headers)
    assert step2_res.status_code == 200
    assert step2_res.json()["current_step"] == 3

    # Verify user record updated in Supabase
    u_chk = supabase.table("users").select("*").eq("id", user_id).execute()
    assert u_chk.data[0]["age"] == 31
    assert float(u_chk.data[0]["weight"]) == 77.0

    # -------------------------------------------------------------
    # 3. Step 3: Ranked Goal Set & Availability
    # -------------------------------------------------------------
    step3_res = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 3,
        "data": {
            "primary_goal": "marathon_endurance",
            "secondary_goals": ["muscle_strength", "longevity_energy"],
            "days_available": ["Monday", "Wednesday", "Friday", "Saturday"],
            "weekly_availability": "4 days per week (Mon, Wed, Fri, Sat)",
            "equipment": "Full Commercial Gym + GPS Watch",
            "target_date": "2026-11-15",
            "target_race": "Autumn Marathon"
        }
    }, headers=headers)
    assert step3_res.status_code == 200
    assert step3_res.json()["current_step"] == 4

    # -------------------------------------------------------------
    # 4. Step 4: Data Reality Check & Horizon Selection
    # -------------------------------------------------------------
    step4_res = requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 4,
        "data": {
            "horizon": "4_week_foundation",
            "calibration_confirmed": True
        }
    }, headers=headers)
    assert step4_res.status_code == 200
    assert step4_res.json()["current_step"] == 5

    # -------------------------------------------------------------
    # 5. Step 5: Proposal Generation & Review
    # -------------------------------------------------------------
    prop_res = requests.post(f"{BASE_URL}/onboarding/generate-proposal", json={
        "horizon": "4_week_foundation"
    }, headers=headers)
    assert prop_res.status_code == 200, f"Generate proposal failed: {prop_res.text}"
    prop_json = prop_res.json()

    assert "proposal" in prop_json
    assert "widget" in prop_json
    assert "reality_check" in prop_json

    # Validate widget conforms to gymbro.widget/v1
    widget = prop_json["widget"]
    assert widget["protocol"] == "gymbro.widget/v1"
    assert widget["widget_type"] == "calendar_proposal"
    assert widget["state"] == "proposed"
    assert len(widget["actions"]) >= 1
    assert any(a["id"] == "commit_calendar" for a in widget["actions"])

    # -------------------------------------------------------------
    # 6. Commit to Calendar & Launch
    # -------------------------------------------------------------
    commit_res = requests.post(f"{BASE_URL}/onboarding/commit", json={
        "proposal": prop_json["proposal"]
    }, headers=headers)
    assert commit_res.status_code == 200, f"Commit failed: {commit_res.text}"
    commit_data = commit_res.json()

    assert commit_data["success"] is True
    assert commit_data["coach_status"] == "active"
    assert commit_data["events_created"] > 0
    assert "welcome_briefing" in commit_data
    assert "Day 1" in commit_data["welcome_briefing"] or "Welcome" in commit_data["welcome_briefing"]

    # -------------------------------------------------------------
    # 7. Post-Commit Verification
    # -------------------------------------------------------------
    # Verify user state in DB is now active
    state_after = requests.get(f"{BASE_URL}/onboarding/state", headers=headers).json()
    assert state_after["coach_status"] == "active"
    assert state_after["is_completed"] is True

    # Verify calendar events populated in training_events
    cal_res = requests.get(f"{BASE_URL}/calendar/events", headers=headers)
    assert cal_res.status_code == 200
    events = cal_res.json().get("events", [])
    assert len(events) >= commit_data["events_created"]


def test_onboarding_multi_tenant_isolation(new_athlete):
    headers_a = new_athlete["headers"]

    # Create athlete B
    uid_b = uuid.uuid4().hex[:6]
    reg_b = requests.post(f"{BASE_URL}/auth/register", json={
        "username": f"tenant_b_{uid_b}",
        "password": "PasswordB123!",
        "email": f"tenant_b_{uid_b}@example.com"
    }).json()
    token_b = reg_b.get("token") or reg_b.get("access_token")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Athlete A advances to Step 3 with specific goal
    requests.post(f"{BASE_URL}/onboarding/step", json={
        "step": 2,
        "data": {"age": 45, "primary_goal": "fat_loss"}
    }, headers=headers_a)

    # Athlete B should still be at Step 1 with default state
    state_b = requests.get(f"{BASE_URL}/onboarding/state", headers=headers_b).json()
    assert state_b["step"] == 1
    assert state_b["coach_status"] in ["not_started", "initial"]
    assert state_b["athlete_profile"]["age"] is None
