from datetime import datetime, timedelta, timezone

from app.scheduler_jobs import scheduled_telemetry_sync
from app.supabase_client import supabase


def test_telemetry_sync_ingests_healthkit_and_can_trigger_providers(client, auth_headers):
    payload = {
        "source": "apple_health",
        "biometrics": [{"date": "2026-08-14", "resting_hr": 53, "hrv": 72, "sleep_hours": 8.1, "sleep_score": 88, "steps": 11200}],
        "activities": [{"activity_id": "hk_run_999", "name": "Morning Trail Run", "activity_type": "running", "start_time_local": "2026-08-14T07:15:00Z", "distance": 8500.0, "duration": 2550.0}],
    }
    res = client.post("/telemetry/sync", json=payload, headers=auth_headers)
    assert res.status_code == 200 and res.json["biometrics_ingested"] == 1 and res.json["activities_ingested"] == 1
    bio = supabase.table("biometrics_daily").select("*").eq("user_id", 1).eq("date", "2026-08-14").execute().data[0]
    assert bio["resting_hr"] == 53 and bio["sleep_score"] == 88
    triggered = client.post("/telemetry/sync", json={"provider": "all", "force": False}, headers=auth_headers)
    assert triggered.status_code == 200 and triggered.json["status"] == "syncing" and "garmin" in triggered.json["providers"]


def test_telemetry_status_and_daily(client, auth_headers):
    status = client.get("/telemetry/status", headers=auth_headers).json
    assert status["fitbit"]["status"] == "reserved" and status["primary_source_priority"][0] == "garmin"
    day = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    supabase.table("biometrics_daily").upsert({
        "user_id": 1, "date": day, "resting_hr": 55, "hrv": 68, "sleep_hours": 7.5, "sleep_score": 82, "steps": 9500, "source": "garmin",
    }, on_conflict="user_id, date").execute()
    daily = client.get("/telemetry/daily?days=30", headers=auth_headers)
    assert daily.status_code == 200 and any(row["date"] == day for row in daily.json["daily_biometrics"])
    one = client.get(f"/telemetry/daily?date={day}", headers=auth_headers)
    assert one.json["resting_hr"] == 55


def test_unified_activities_prefer_garmin_and_summarize(client, auth_headers):
    for table in ("garmin_activities", "strava_activities", "activities"):
        supabase.table(table).data[table] = []
    supabase.table("garmin_activities").insert({
        "id": 101, "user_id": 1, "activity_id": "garmin_act_101", "activity_name": "Tempo Run (Garmin)",
        "start_time_local": "2026-08-12T07:00:00Z", "distance": 10000.0, "duration": 3000.0, "activity_type": "running",
    }).execute()
    supabase.table("strava_activities").insert({
        "id": 201, "user_id": 1, "activity_id": "strava_act_201", "name": "Tempo Run (Strava)", "type": "Run",
        "start_date_local": "2026-08-12T07:01:30Z", "distance": 10050.0, "moving_time": 3010.0, "elapsed_time": 3010.0,
    }).execute()
    supabase.table("activities").insert({
        "id": 301, "user_id": 1, "activity_type": "strength", "name": "Core & Mobility",
        "start_time_local": "2026-08-12T18:30:00Z", "distance": 0.0, "duration": 1800.0,
    }).execute()
    activities = client.get("/activities", headers=auth_headers).json["activities"]
    assert len(activities) == 2
    morning = next(a for a in activities if "Tempo" in (a.get("name") or a.get("activity_name") or ""))
    assert morning["source"] == "garmin" and morning["is_primary"] is True
    stats = client.get("/activities/stats", headers=auth_headers).json
    assert stats["total_activities"] == 2 and stats["total_distance_km"] == 10.0
    summary = client.get("/activities/summary", headers=auth_headers).json
    assert summary["workouts"] == 2 and len(summary["recent_activities"]) == 2


def test_scheduled_telemetry_sync_job():
    scheduled_telemetry_sync()
