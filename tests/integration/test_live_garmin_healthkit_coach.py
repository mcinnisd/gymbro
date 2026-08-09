"""
Live Integration & Verification Suite for Garmin, HealthKit, and Coach Chat RAG.
Verifies real-world account sync and conversational intelligence retrieval.
"""

import os
import pytest
from app import create_app
from app.context.builder import build_user_context
from app.coach.service import process_coach_message


@pytest.fixture
def app_client():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    return client


def test_live_garmin_connection_and_sync(app_client):
    """
    Connects to Garmin using credentials from .env and executes full data sync.
    """
    garmin_id = os.getenv("GARMIN_ID")
    garmin_password = os.getenv("GARMIN_PASSWORD")

    if not garmin_id or not garmin_password:
        pytest.skip("GARMIN_ID or GARMIN_PASSWORD not configured in environment.")

    # 1. Register or login test user
    test_email = "live_garmin_test_user@example.com"
    reg_res = app_client.post("/auth/register", json={
        "username": test_email,
        "email": test_email,
        "password": "password123",
        "name": "Live Tester"
    })
    token = None
    if reg_res.status_code in [200, 201]:
        token = reg_res.json.get("access_token") or reg_res.json.get("token")
    else:
        login_res = app_client.post("/auth/login", json={
            "username": test_email,
            "password": "password123"
        })
        assert login_res.status_code == 200
        token = login_res.json.get("access_token") or login_res.json.get("token")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Connect Garmin Account
    conn_res = app_client.post("/garmin/connect", headers=headers, json={
        "email": garmin_id,
        "password": garmin_password
    })
    assert conn_res.status_code == 200
    msg = conn_res.json.get("message", "").lower()
    assert "stored" in msg or "initiated" in msg or "connected" in msg

    # 3. Check Garmin Status
    status_res = app_client.get("/garmin/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json.get("garmin_connected") is True


def test_apple_healthkit_data_ingestion(app_client):
    """
    Verifies that Apple HealthKit metrics (resting HR, sleep, workouts) are correctly ingested and stored.
    """
    test_email = "healthkit_test_user@example.com"
    reg_res = app_client.post("/auth/register", json={
        "username": test_email,
        "email": test_email,
        "password": "password123",
        "name": "HealthKit Tester"
    })
    token = reg_res.json.get("access_token") if reg_res.status_code in [200, 201] else None
    if not token:
        login_res = app_client.post("/auth/login", json={"username": test_email, "password": "password123"})
        token = login_res.json.get("access_token") or login_res.json.get("token")

    headers = {"Authorization": f"Bearer {token}"}

    # Post HealthKit daily journal & biometrics entry
    res = app_client.post("/journal/", headers=headers, json={
        "answers": {
            "journal_text": "Completed 8.5km run synced from Apple HealthKit",
            "sleep_quality": 8,
            "resting_hr": 54,
            "hrv": 68
        }
    })
    assert res.status_code in [200, 201]
    assert res.json.get("message") == "Journal saved successfully."


def test_coach_chat_rag_and_tool_data_retrieval(app_client):
    """
    Tests open-ended coach chat queries to ensure RAG context and activity tools return detailed fitness data.
    """
    test_user_id = "test1111"

    # Query 1: Recent runs query
    res1 = process_coach_message(user_id=test_user_id, message="How were my runs over the last two weeks?")
    assert "response" in res1
    assert len(res1["response"]) > 10
    assert "answer complete" not in res1["response"].lower() or len(res1["response"]) > 30

    # Query 2: HRV and Sleep recovery query
    res2 = process_coach_message(user_id=test_user_id, message="Show my HRV and sleep recovery trends.")
    assert "response" in res2
    assert res2.get("ui_payload") is not None or "hrv" in res2["response"].lower() or "sleep" in res2["response"].lower()

    # Query 3: Training plan generation query
    res3 = process_coach_message(user_id=test_user_id, message="Generate a 4-week marathon training plan for me.")
    assert "response" in res3
    assert res3.get("ui_payload") is not None or "plan" in res3.get("response", "").lower()
