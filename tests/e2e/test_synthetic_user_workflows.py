import io

import pytest

from app import create_app
from app.supabase_client import supabase


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _token(client, email, name="Runner Alex"):
    reg = client.post("/auth/register", json={"email": email, "password": "password123", "name": name})
    data = reg.get_json() or {}
    token = data.get("access_token") or data.get("token")
    if token:
        return token
    login = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    data = login.get_json() or {}
    return data.get("access_token") or data.get("token")


def _headers(client, email):
    return {"Authorization": f"Bearer {_token(client, email)}"}


def test_synthetic_user_registration_and_login(client):
    email = "synthetic_runner_reg@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "password123", "name": "Runner Alex"})
    assert res.status_code in (200, 201) and ("token" in res.get_json() or "access_token" in res.get_json())
    login = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200 and login.get_json()["user"]["email"] == email


def test_synthetic_user_profile_journal_and_bloodwork(client):
    headers = _headers(client, "synthetic_profile@example.com")
    profile = {"age": 32, "weight": 74.5, "sport_history": "Marathoner 4 years"}
    assert client.put("/auth/profile", headers=headers, json=profile).status_code == 200
    assert client.get("/auth/profile", headers=headers).get_json()["profile"]["age"] == 32
    assert client.post("/journal/", headers=headers, json={"date": "2026-08-09", "answers": {"energy_level": 8}}).status_code == 200
    entry = client.get("/journal/2026-08-09", headers=headers).get_json()["journal"]
    assert entry["answers"]["energy_level"] == 8
    upload = client.post("/biomarkers/upload-pdf", headers=headers, data={"file": (io.BytesIO(b"%PDF-1.4 lab"), "lab.pdf")}, content_type="multipart/form-data")
    assert upload.status_code == 200 and upload.get_json()["extracted_biomarkers"]
    assert client.get("/biomarkers/flagged", headers=headers).status_code == 200


def test_synthetic_user_garmin_data_sync(client):
    headers = _headers(client, "synthetic_garmin@example.com")
    assert client.post("/garmin/connect", headers=headers, json={"email": "synthetic_runner@garmin.com", "password": "garminpassword123"}).status_code == 200
    assert client.get("/garmin/status", headers=headers).status_code == 200
    user_id = client.post("/auth/login", json={"email": "synthetic_garmin@example.com", "password": "password123"}).get_json()["user"]["id"]
    supabase.table("garmin_daily").insert({"user_id": user_id, "date": "2026-08-09", "hrv_avg": 68, "resting_heart_rate": 48, "steps": 12500}).execute()
    supabase.table("garmin_sleep").insert({"user_id": user_id, "date": "2026-08-09", "total_sleep_seconds": 28800, "sleep_score": 85}).execute()
    assert client.get("/garmin/daily/2026-08-09", headers=headers).get_json()["hrv_avg"] == 68
    assert client.get("/garmin/sleep/2026-08-09", headers=headers).get_json()["sleep_score"] == 85


def test_synthetic_user_coach_and_training_plan_generation(client):
    headers = _headers(client, "synthetic_coach@example.com")
    started = client.post("/coach/start_interview", headers=headers)
    assert started.status_code == 200 and started.get_json().get("chat_id")
    plan = client.post("/coach/generate_plan", headers=headers, json={"chat_id": started.get_json()["chat_id"]})
    assert plan.status_code == 200 and "plan" in plan.get_json()
    assert client.get("/calendar/events", headers=headers).status_code == 200
