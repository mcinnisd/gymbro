# tests/unit/test_auto_sync_and_backfill.py
import pytest
from datetime import datetime, timezone, timedelta, date
from app.supabase_client import supabase
from app.garmin.sync import sync_all_garmin_data_for_user
from app.telemetry.routes import telemetry_bp
from app.health_hub.ingestion_service import record_daily_biometrics

def test_sleep_architecture_and_hrv_normalization_into_biometrics_daily():
    """
    Test that sleep architecture (deep, rem, light, awake stages in seconds and hours)
    and HRV metrics are correctly parsed and normalized into biometrics_daily.
    """
    uid = 101
    sample_payload = {
        "date": "2026-08-15",
        "resting_hr": 52,
        "hrv": 74,
        "hrv_ms": 74,
        "hrv_status": "Balanced",
        "sleep_score": 88,
        "sleep_hours": 7.8,
        "deep_sleep_hours": 1.8,
        "rem_sleep_hours": 2.1,
        "light_sleep_hours": 3.9,
        "sleep_stages": {
            "deep": 6480,
            "rem": 7560,
            "light": 14040,
            "awake": 1200
        },
        "recovery_score": 85,
        "body_battery": 82,
        "stress_level": 24,
        "vo2_max": 54.5,
        "fitness_age": 22,
        "training_status": "PRODUCTIVE",
        "acute_load": 485,
        "spo2": 98.0,
        "respiration": 14.0,
        "steps": 10500,
        "source": "garmin"
    }

    record = record_daily_biometrics(uid, sample_payload)
    assert record["user_id"] == uid
    assert record["date"] == "2026-08-15"
    assert record["resting_hr"] == 52
    assert record["hrv"] == 74
    assert record["sleep_score"] == 88
    assert record["sleep_hours"] == 7.8
    assert record["deep_sleep_hours"] == 1.8
    assert record["rem_sleep_hours"] == 2.1
    assert record["light_sleep_hours"] == 3.9
    assert record["sleep_stages"]["deep"] == 6480
    assert record["sleep_stages"]["rem"] == 7560
    assert record["training_status"] == "PRODUCTIVE"
    assert record["body_battery"] == 82
    assert record["source"] == "garmin"

def test_telemetry_sync_if_needed_endpoint_freshness_debounce(client, auth_headers):
    """
    Test /telemetry/sync-if-needed endpoint.
    If sync was completed recently (< 15 mins), it should report fresh.
    If sync is stale (> 15 mins) or never completed, it should trigger non-blocking sync.
    """
    # Seed user with connected Garmin credentials
    supabase.table("users").upsert({
        "id": 1,
        "username": "athlete_sync_test",
        "garmin_email": "athlete@example.com",
        "garmin_password": "encrypted_test_pass",
        "garmin_sync_status": "synced",
        "garmin_sync_completed_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "goals": {"garmin_last_synced": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()}
    }, on_conflict="id").execute()

    # Call sync-if-needed when fresh (5 mins ago)
    res_fresh = client.post("/telemetry/sync-if-needed", headers=auth_headers)
    assert res_fresh.status_code == 200
    data_fresh = res_fresh.json
    assert data_fresh["status"] in ["fresh", "already_synced", "up_to_date"]
    assert data_fresh["triggered"] is False

    # Now make it stale (45 minutes ago)
    supabase.table("users").upsert({
        "id": 1,
        "garmin_sync_status": "synced",
        "garmin_sync_completed_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(),
        "goals": {"garmin_last_synced": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()}
    }, on_conflict="id").execute()

    res_stale = client.post("/telemetry/sync-if-needed", headers=auth_headers)
    assert res_stale.status_code == 200
    data_stale = res_stale.json
    assert data_stale["triggered"] is True
    assert "garmin" in data_stale.get("providers", [])

def test_login_triggers_non_blocking_auto_sync(client):
    """
    Test that /auth/login returns immediately with token and user object
    while dispatching background auto-sync when credentials exist.
    """
    import time
    username = f"autosync_{int(time.time())}"
    password = "password123"
    
    # 1. Register user
    reg_res = client.post("/auth/register", json={"username": username, "password": password, "email": f"{username}@test.com"})
    assert reg_res.status_code in [200, 201]
    
    # 2. Add Garmin credentials to user
    supabase.table("users").update({
        "garmin_email": "athlete_auto@example.com",
        "garmin_password": "encrypted_test_pw",
        "garmin_sync_status": "synced",
        "garmin_sync_completed_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }).eq("username", username).execute()

    # 3. Login
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    data = res.json
    assert "access_token" in data
    assert data["user"]["email"] == username

def test_telemetry_sync_supports_365_days_backfill_parameter(client, auth_headers):
    """
    Test that /telemetry/sync accepts { "days_back": 365, "force": true }
    and initiates backfill synchronization.
    """
    res = client.post("/telemetry/sync", json={"provider": "all", "days_back": 365, "force": True}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json
    assert data["status"] == "syncing"
    assert "garmin" in data.get("providers", [])
    assert data.get("force_resync") is True
    assert data.get("days_back") == 365
