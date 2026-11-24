import pytest
from app.garmin.biometrics_mirror import upsert_biometrics_daily
from app.health_hub.deduplication_service import (
    DEFAULT_SOURCE_PRIORITY, SOURCE_PRIORITY_ORDER, deduplicate_activities, resolve_biometrics_priority,
)
from app.health_hub.ingestion_service import record_daily_biometrics
from app.supabase_client import supabase


def _act(id, source, start, distance, duration=1500, name="Run"):
    return {"id": id, "source": source, "start_time": start, "distance_m": distance, "duration_s": duration, "name": name}


@pytest.mark.parametrize("activities,priority,count,winner,dup", [
    ([
        _act(1, "garmin", "2026-08-08T08:00:00Z", 5000, name="Morning Run (Garmin)"),
        _act(2, "strava", "2026-08-08T08:01:00Z", 5020, 1505, "Morning Run (Strava)"),
        _act(3, "strava", "2026-08-08T18:00:00Z", 8000, 2400, "Evening Run"),
    ], None, 2, "garmin", 2),
    ([
        _act(10, "garmin", "2026-08-08T08:00:00Z", 5000),
        _act(11, "strava", "2026-08-08T08:01:00Z", 5010),
    ], {"strava": 1, "garmin": 2, "apple_health": 3, "manual": 4}, 1, "strava", 10),
    ([
        _act("hk_run_1", "apple_health", "2026-08-08T08:00:00Z", 5000, name="Morning Run (Apple Health)"),
        _act("garmin_run_1", "garmin", "2026-08-08T08:02:00Z", 5050, 1510, "Morning Run (Garmin)"),
    ], None, 1, "garmin", "hk_run_1"),
])
def test_duplicate_workouts_keep_the_preferred_source(activities, priority, count, winner, dup):
    deduped = deduplicate_activities(activities, custom_priority=priority)
    assert len(deduped) == count
    assert deduped[0]["source"] == winner and deduped[0]["is_primary"] is True
    assert dup in deduped[0]["duplicate_source_ids"]


def test_distance_outside_tolerance_is_not_a_duplicate():
    deduped = deduplicate_activities([
        _act(20, "garmin", "2026-08-08T08:00:00Z", 5000, name="5k Run"),
        _act(21, "strava", "2026-08-08T08:02:00Z", 6000, 1800, "6k Run"),
    ])
    assert len(deduped) == 2


def test_biometrics_priority_and_field_merge():
    assert DEFAULT_SOURCE_PRIORITY["garmin"] < DEFAULT_SOURCE_PRIORITY["strava"] < DEFAULT_SOURCE_PRIORITY["apple_health"]
    assert DEFAULT_SOURCE_PRIORITY["apple_health"] == DEFAULT_SOURCE_PRIORITY["healthkit"]
    assert DEFAULT_SOURCE_PRIORITY["apple_health"] < DEFAULT_SOURCE_PRIORITY["fitbit"] < DEFAULT_SOURCE_PRIORITY["manual"]
    assert SOURCE_PRIORITY_ORDER == ["garmin", "strava", "apple_health", "fitbit", "manual"]

    ranked = resolve_biometrics_priority([
        {"raw_source": "manual", "resting_hr": 65, "sleep_hours": 6.5},
        {"raw_source": "apple_health", "resting_hr": 58, "sleep_hours": 7.5},
        {"raw_source": "garmin", "resting_hr": 56, "sleep_hours": 7.8},
    ])
    assert ranked["resting_hr"] == 56 and ranked["primary_source"] == "garmin"
    custom = resolve_biometrics_priority([
        {"raw_source": "garmin", "resting_hr": 56},
        {"raw_source": "apple_health", "resting_hr": 54},
    ], custom_priority={"apple_health": 1, "garmin": 2})
    assert custom["resting_hr"] == 54 and custom["primary_source"] == "apple_health"

    merged = resolve_biometrics_priority([
        {"source": "garmin", "sleep_hours": 7.6, "sleep_score": 80, "hrv": 48, "hrv_ms": 48, "hrv_status": "BALANCED", "steps": None,
         "sleep_stages": {"deep": 5040}},
        {"source": "apple_health", "steps": 11200, "sleep_hours": 6.1, "hrv": 22},
    ])
    assert merged["sleep_hours"] == 7.6 and merged["hrv"] == 48 and merged["steps"] == 11200
    assert merged["field_sources"]["steps"] == "apple_health" and merged["field_sources"]["hrv"] == "garmin"

    empty = resolve_biometrics_priority([
        {"source": "garmin", "sleep_hours": None, "hrv": None, "steps": None},
        {"source": "apple_health", "steps": 8432, "calories_burned": 420},
    ])
    assert empty["steps"] == 8432 and "sleep_hours" not in empty and empty["primary_source"] == "apple_health"

    fitbit = resolve_biometrics_priority([
        {"source": "manual", "steps": 100, "sleep_hours": 4},
        {"source": "fitbit", "steps": 4000, "sleep_hours": 5.5},
        {"source": "apple_health", "steps": 8000},
    ])
    assert fitbit["steps"] == 8000 and fitbit["sleep_hours"] == 5.5
    assert fitbit["field_sources"]["sleep_hours"] == "fitbit"


def test_stored_day_merges_garmin_sleep_with_apple_steps_and_ignores_nulls():
    uid, day = 9911, "2026-11-01"
    supabase.table("biometrics_daily").delete().eq("user_id", uid).execute()
    try:
        upsert_biometrics_daily([{"user_id": uid, "date": day, "steps": None, "source": "garmin"}])
        record_daily_biometrics(uid, {"date": day, "steps": 9000, "resting_hr": 53, "sleep_hours": 6.0, "source": "apple_health"})
        upsert_biometrics_daily([{
            "user_id": uid, "date": day, "hrv": 51, "hrv_ms": 51, "hrv_status": "BALANCED",
            "sleep_score": 82, "sleep_hours": 7.4, "steps": None, "source": "garmin",
        }])
        record_daily_biometrics(uid, {"date": day, "steps": 12000, "sleep_hours": 6.2, "hrv": 20, "source": "apple_health"})
        upsert_biometrics_daily([{"user_id": uid, "date": day, "sleep_hours": 7.4, "hrv": 51, "steps": None, "source": "garmin"}])
        row = supabase.table("biometrics_daily").select("*").eq("user_id", uid).eq("date", day).execute().data[0]
        assert row["steps"] == 12000 and row["sleep_hours"] == 7.4 and row["hrv"] == 51
        assert row["resting_hr"] == 53 and row["field_sources"]["steps"] == "apple_health"
        assert row["field_sources"]["sleep_hours"] == "garmin"
    finally:
        supabase.table("biometrics_daily").delete().eq("user_id", uid).execute()
