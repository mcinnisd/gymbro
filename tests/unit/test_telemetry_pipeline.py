import pytest
from app.supabase_client import supabase
from app.health_hub.ingestion_service import get_unified_activities, get_telemetry_status
from app.scheduler_jobs import scheduled_telemetry_sync

def test_telemetry_sync_direct_healthkit_payload(client, auth_headers):
    # Test Apple HealthKit direct push payload
    payload = {
        "source": "apple_health",
        "biometrics": [
            {
                "date": "2026-08-14",
                "resting_hr": 53,
                "hrv": 72,
                "sleep_hours": 8.1,
                "sleep_score": 88,
                "deep_sleep_hours": 2.0,
                "rem_sleep_hours": 2.2,
                "light_sleep_hours": 3.9,
                "sleep_stages": {"deep": 7200, "rem": 7920, "light": 14040, "awake": 0},
                "steps": 11200,
                "calories_burned": 2550,
                "vo2_max": 53.5,
                "spo2": 99.0,
                "respiration": 13.8
            }
        ],
        "activities": [
            {
                "activity_id": "hk_run_999",
                "name": "Morning Trail Run",
                "activity_type": "running",
                "start_time_local": "2026-08-14T07:15:00Z",
                "distance": 8500.0,
                "duration": 2550.0,
                "calories": 620.0,
                "average_hr": 148,
                "max_hr": 172,
                "elevation_gain": 85.0
            }
        ]
    }

    res = client.post("/telemetry/sync", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json
    assert data["status"] == "success"
    assert data["source"] == "apple_health"
    assert data["biometrics_ingested"] == 1
    assert data["activities_ingested"] == 1

    # Verify biometrics_daily table contains the entry
    bio_res = supabase.table("biometrics_daily").select("*").eq("user_id", 1).eq("date", "2026-08-14").execute()
    assert len(bio_res.data) >= 1
    bio_entry = bio_res.data[0]
    assert bio_entry["resting_hr"] == 53
    assert bio_entry["hrv"] == 72
    assert bio_entry["sleep_score"] == 88

def test_telemetry_sync_provider_trigger(client, auth_headers):
    # Test triggering background provider sync
    res = client.post("/telemetry/sync", json={"provider": "all", "force": False}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json
    assert data["status"] == "syncing"
    assert "garmin" in data["providers"]
    assert "strava" in data["providers"]

def test_telemetry_status_endpoint(client, auth_headers):
    res = client.get("/telemetry/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json
    assert "garmin" in data
    assert "strava" in data
    assert "apple_health" in data
    assert "primary_source_priority" in data
    assert data["primary_source_priority"][0] == "garmin"

def test_telemetry_daily_endpoint(client, auth_headers):
    # Seed biometrics_daily
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": "2026-08-10",
        "resting_hr": 55,
        "hrv": 68,
        "sleep_hours": 7.5,
        "sleep_score": 82,
        "steps": 9500,
        "source": "garmin"
    }, on_conflict="user_id, date").execute()

    # Query range
    res = client.get("/telemetry/daily?days=30", headers=auth_headers)
    assert res.status_code == 200
    daily_list = res.json.get("daily_biometrics", [])
    assert len(daily_list) >= 1
    assert any(d["date"] == "2026-08-10" for d in daily_list)

    # Query single date
    res_single = client.get("/telemetry/daily?date=2026-08-10", headers=auth_headers)
    assert res_single.status_code == 200
    assert res_single.json["date"] == "2026-08-10"
    assert res_single.json["resting_hr"] == 55

def test_unified_activities_deduplication_garmin_strava_healthkit(client, auth_headers):
    # Clear prior activities for clean test
    supabase.table("garmin_activities").data["garmin_activities"] = []
    supabase.table("strava_activities").data["strava_activities"] = []
    supabase.table("activities").data["activities"] = []

    # 1. Seed Garmin run
    supabase.table("garmin_activities").insert({
        "id": 101,
        "user_id": 1,
        "activity_id": "garmin_act_101",
        "activity_name": "Tempo Run (Garmin)",
        "start_time_local": "2026-08-12T07:00:00Z",
        "distance": 10000.0,
        "duration": 3000.0,
        "calories": 750.0,
        "activity_type": "running",
        "average_hr": 155,
        "elevation_gain": 60.0
    }).execute()

    # 2. Seed Overlapping Strava run (within 2 mins and 1% distance)
    supabase.table("strava_activities").insert({
        "id": 201,
        "user_id": 1,
        "activity_id": "strava_act_201",
        "name": "Tempo Run (Strava)",
        "type": "Run",
        "start_date_local": "2026-08-12T07:01:30Z",
        "distance": 10050.0,
        "moving_time": 3010.0,
        "elapsed_time": 3010.0,
        "calories": 760.0,
        "average_hr": 155,
        "total_elevation_gain": 62.0
    }).execute()

    # 3. Seed Distinct Evening Workout
    supabase.table("activities").insert({
        "id": 301,
        "user_id": 1,
        "activity_type": "strength",
        "name": "Core & Mobility",
        "start_time_local": "2026-08-12T18:30:00Z",
        "distance": 0.0,
        "duration": 1800.0,
        "calories": 200.0,
        "notes": "Apple HealthKit Core Workout"
    }).execute()

    # Fetch from /activities endpoint
    res = client.get("/activities", headers=auth_headers)
    assert res.status_code == 200
    activities = res.json.get("activities", [])
    
    # 3 raw activities should deduplicate into 2 distinct activities
    assert len(activities) == 2

    # The morning run primary must be Garmin
    morning_run = [a for a in activities if "Tempo" in (a.get("name") or a.get("activity_name") or "")][0]
    assert morning_run["source"] == "garmin"
    assert morning_run["is_primary"] is True
    assert "duplicate_source_ids" in morning_run
    assert "strava_act_201" in morning_run["duplicate_source_ids"] or 201 in morning_run["duplicate_source_ids"]

def test_unified_activities_stats_and_summary(client, auth_headers):
    # Test aggregate stats across deduplicated activities
    res_stats = client.get("/activities/stats", headers=auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.json
    assert stats["total_activities"] == 2
    assert stats["total_distance_km"] == 10.0

    res_summary = client.get("/activities/summary", headers=auth_headers)
    assert res_summary.status_code == 200
    summary = res_summary.json
    assert summary["workouts"] == 2
    assert summary["active_days"] >= 1
    assert len(summary["recent_activities"]) == 2

def test_scheduled_telemetry_sync_job():
    # Verify scheduled job runs cleanly with mock Supabase
    scheduled_telemetry_sync()
