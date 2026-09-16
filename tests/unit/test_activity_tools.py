from datetime import datetime, timedelta, timezone

from app.supabase_client import supabase
from app.tools.activity_tools import get_recent_activities, get_wellness_metrics
from app.tools.registry import get_tool_implementation


def _recent_iso(days_ago: int, hour: int = 7) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def _recent_date(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()


def test_registry_binds_activity_and_wellness_tools():
    assert get_tool_implementation("get_recent_activities") is get_recent_activities
    assert get_tool_implementation("get_wellness_metrics") is get_wellness_metrics


def test_get_recent_activities_reads_garmin_table_not_generic_activities():
    """MCP reads must surface Garmin rows even when the generic `activities` table is empty."""
    supabase.table("garmin_activities").data["garmin_activities"] = []
    supabase.table("strava_activities").data["strava_activities"] = []
    supabase.table("activities").data["activities"] = []

    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_run_mcp_1",
        "activity_name": "Easy Aerobic Run",
        "start_time_local": _recent_iso(2),
        "distance": 8000.0,
        "duration": 2400.0,
        "calories": 520.0,
        "activity_type": "running",
        "average_hr": 142,
        "max_hr": 161,
        "elevation_gain": 40.0,
    }).execute()

    res = get_recent_activities(user_id="1", days=14)
    assert res["status"] == "success"
    assert res["count"] >= 1
    names = [a["name"] for a in res["activities"]]
    assert "Easy Aerobic Run" in names
    easy = next(a for a in res["activities"] if a["name"] == "Easy Aerobic Run")
    assert easy["source"] == "garmin"
    assert easy["distance_km"] == 8.0


def test_get_recent_activities_empty_when_no_garmin_or_other_workouts():
    supabase.table("garmin_activities").data["garmin_activities"] = []
    supabase.table("strava_activities").data["strava_activities"] = []
    supabase.table("activities").data["activities"] = []

    res = get_recent_activities(user_id="99", days=14)
    assert res["status"] == "success"
    assert res["count"] == 0
    assert res["activities"] == []


def test_get_wellness_metrics_reads_biometrics_daily_not_journal_entries():
    """Garmin sleep/HRV/RHR live in biometrics_daily; journal_entries is not a real table."""
    supabase.table("biometrics_daily").data["biometrics_daily"] = []
    supabase.table("journal_entries").data["journal_entries"] = []

    day = _recent_date(1)
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": day,
        "sleep_score": 82,
        "sleep_hours": 7.6,
        "hrv": 64,
        "hrv_ms": 64,
        "hrv_status": "BALANCED",
        "resting_hr": 51,
        "stress_level": 28,
        "body_battery": 78,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()

    res = get_wellness_metrics(user_id="1", days=7)
    assert res["status"] == "success"
    assert res["records_count"] >= 1
    assert res["averages"]["sleep_score"] == 82
    assert res["averages"]["hrv_ms"] == 64
    assert res["averages"]["resting_hr_bpm"] == 51
    assert res["records"][0]["source"] == "garmin"


def test_get_wellness_metrics_empty_window_does_not_invent_data():
    supabase.table("biometrics_daily").data["biometrics_daily"] = []

    res = get_wellness_metrics(user_id="99", days=7)
    assert res["status"] == "success"
    assert res["records_count"] == 0
    assert res["averages"]["sleep_score"] is None
    assert res["averages"]["hrv_ms"] is None
    assert res["averages"]["resting_hr_bpm"] is None
    assert res.get("records") == []


def test_localhost_mcp_equivalent_routes_bind_jwt_and_read_garmin_tables(client, auth_headers):
    """JWT-bound /telemetry/tools/* is the localhost stand-in for MCP (no Cloudflare)."""
    supabase.table("garmin_activities").data["garmin_activities"] = []
    supabase.table("strava_activities").data["strava_activities"] = []
    supabase.table("activities").data["activities"] = []
    supabase.table("biometrics_daily").data["biometrics_daily"] = []

    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_local_verify",
        "activity_name": "Localhost Verify Run",
        "start_time_local": _recent_iso(1),
        "distance": 5000.0,
        "duration": 1500.0,
        "activity_type": "running",
    }).execute()
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": _recent_date(1),
        "sleep_score": 79,
        "hrv": 61,
        "resting_hr": 52,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()

    wellness = client.get("/telemetry/tools/wellness-metrics?days=7", headers=auth_headers)
    assert wellness.status_code == 200
    w = wellness.json
    assert w["status"] == "success"
    assert w["records_count"] >= 1
    assert w["averages"]["sleep_score"] == 79

    acts = client.get("/telemetry/tools/recent-activities?days=14", headers=auth_headers)
    assert acts.status_code == 200
    a = acts.json
    assert a["status"] == "success"
    assert a["count"] >= 1
    assert any(row["name"] == "Localhost Verify Run" for row in a["activities"])


def test_verify_mcp_tools_for_user_uses_canonical_tables():
    from app.garmin.cli import verify_mcp_tools_for_user

    supabase.table("biometrics_daily").data["biometrics_daily"] = []
    supabase.table("garmin_activities").data["garmin_activities"] = []
    supabase.table("strava_activities").data["strava_activities"] = []
    supabase.table("activities").data["activities"] = []

    empty = verify_mcp_tools_for_user("99", wellness_days=7, activity_days=14)
    assert empty["user_id"] == "99"
    assert empty["wellness"]["records_count"] == 0
    assert empty["activities"]["count"] == 0

    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": _recent_date(1),
        "sleep_score": 80,
        "hrv": 70,
        "resting_hr": 50,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()
    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_cli_verify",
        "activity_name": "CLI Verify Ride",
        "start_time_local": _recent_iso(1),
        "distance": 20000.0,
        "duration": 3600.0,
        "activity_type": "cycling",
    }).execute()

    snapshot = verify_mcp_tools_for_user("1")
    assert snapshot["wellness"]["records_count"] >= 1
    assert snapshot["wellness"]["averages"]["hrv_ms"] == 70
    assert snapshot["activities"]["count"] >= 1
