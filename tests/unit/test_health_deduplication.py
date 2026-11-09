import pytest
from app.health_hub.deduplication_service import (
    DEFAULT_SOURCE_PRIORITY,
    SOURCE_PRIORITY_ORDER,
    deduplicate_activities,
    resolve_biometrics_priority,
)
from app.health_hub.ingestion_service import record_daily_biometrics
from app.garmin.biometrics_mirror import upsert_biometrics_daily
from app.supabase_client import supabase

def test_deduplicate_activities_matching():
    # Simulate duplicate Garmin and Strava runs occurring at the same start time
    activities = [
        {
            "id": 1,
            "source": "garmin",
            "start_time": "2026-08-08T08:00:00Z",
            "distance_m": 5000,
            "duration_s": 1500,
            "name": "Morning Run (Garmin)"
        },
        {
            "id": 2,
            "source": "strava",
            "start_time": "2026-08-08T08:01:00Z", # Within 5 mins
            "distance_m": 5020, # Within 5%
            "duration_s": 1505,
            "name": "Morning Run (Strava)"
        },
        {
            "id": 3,
            "source": "strava",
            "start_time": "2026-08-08T18:00:00Z", # Different time
            "distance_m": 8000,
            "duration_s": 2400,
            "name": "Evening Run"
        }
    ]

    deduped = deduplicate_activities(activities)
    assert len(deduped) == 2
    primary = deduped[0]
    assert primary["source"] == "garmin" # Native Garmin preferred over Strava
    assert primary["is_primary"] is True
    assert "duplicate_source_ids" in primary
    assert 2 in primary["duplicate_source_ids"]

def test_resolve_biometrics_priority():
    # Test recovery biometrics priority: Garmin/Apple Health > Manual
    sources = [
        {"raw_source": "manual", "resting_hr": 65, "sleep_hours": 6.5},
        {"raw_source": "apple_health", "resting_hr": 58, "sleep_hours": 7.5},
        {"raw_source": "garmin", "resting_hr": 56, "sleep_hours": 7.8}
    ]

    resolved = resolve_biometrics_priority(sources)
    assert resolved["resting_hr"] == 56
    assert resolved["sleep_hours"] == 7.8
    assert resolved["primary_source"] == "garmin"

def test_deduplicate_activities_custom_user_priority():
    # Test user setting custom preference (e.g. strava over garmin)
    activities = [
        {
            "id": 10,
            "source": "garmin",
            "start_time": "2026-08-08T08:00:00Z",
            "distance_m": 5000,
            "duration_s": 1500,
            "name": "Morning Run (Garmin)"
        },
        {
            "id": 11,
            "source": "strava",
            "start_time": "2026-08-08T08:01:00Z",
            "distance_m": 5010,
            "duration_s": 1500,
            "name": "Morning Run (Strava)"
        }
    ]

    # Pass custom priority giving strava highest rank (1) over garmin (2)
    custom_priority = {"strava": 1, "garmin": 2, "apple_health": 3, "manual": 4}
    deduped = deduplicate_activities(activities, custom_priority=custom_priority)
    assert len(deduped) == 1
    assert deduped[0]["source"] == "strava"
    assert deduped[0]["duplicate_source_ids"] == [10]

def test_deduplicate_activities_tolerance_bounds():
    # Activities outside 5% distance difference should NOT be grouped
    activities = [
        {
            "id": 20,
            "source": "garmin",
            "start_time": "2026-08-08T08:00:00Z",
            "distance_m": 5000,
            "duration_s": 1500,
            "name": "5k Run"
        },
        {
            "id": 21,
            "source": "strava",
            "start_time": "2026-08-08T08:02:00Z",
            "distance_m": 6000, # 20% diff -> NOT a duplicate
            "duration_s": 1800,
            "name": "6k Run"
        }
    ]

    deduped = deduplicate_activities(activities)
    assert len(deduped) == 2

def test_resolve_biometrics_priority_custom_user_priority():
    sources = [
        {"raw_source": "garmin", "resting_hr": 56, "sleep_hours": 7.8},
        {"raw_source": "apple_health", "resting_hr": 54, "sleep_hours": 8.0}
    ]
    custom_priority = {"apple_health": 1, "garmin": 2}
    resolved = resolve_biometrics_priority(sources, custom_priority=custom_priority)
    assert resolved["resting_hr"] == 54
    assert resolved["primary_source"] == "apple_health"

def test_field_level_merge_keeps_garmin_sleep_hrv_and_apple_steps():
    # Same calendar day: Garmin owns the night, Apple Health owns the daytime steps.
    resolved = resolve_biometrics_priority([
        {
            "source": "garmin",
            "sleep_hours": 7.6,
            "sleep_score": 80,
            "deep_sleep_hours": 1.4,
            "rem_sleep_hours": 1.8,
            "light_sleep_hours": 4.4,
            "sleep_stages": {"deep": 5040, "rem": 6480, "light": 15840, "awake": 600},
            "hrv": 48,
            "hrv_ms": 48,
            "hrv_status": "BALANCED",
            "steps": None,
        },
        {
            "source": "apple_health",
            "steps": 11200,
            "sleep_hours": 6.1,
            "hrv": 22,
            "hrv_ms": 22,
            "hrv_status": "LOW",
        },
    ])

    assert resolved["sleep_hours"] == 7.6
    assert resolved["sleep_score"] == 80
    assert resolved["sleep_stages"]["deep"] == 5040
    assert resolved["hrv"] == 48
    assert resolved["hrv_ms"] == 48
    assert resolved["hrv_status"] == "BALANCED"
    assert resolved["steps"] == 11200
    assert resolved["field_sources"]["sleep_hours"] == "garmin"
    assert resolved["field_sources"]["hrv"] == "garmin"
    assert resolved["field_sources"]["steps"] == "apple_health"
    assert resolved["primary_source"] == "garmin"

def test_empty_garmin_day_does_not_block_apple_steps():
    resolved = resolve_biometrics_priority([
        {"source": "garmin", "sleep_hours": None, "hrv": None, "hrv_ms": None, "hrv_status": None, "steps": None},
        {"source": "apple_health", "steps": 8432, "calories_burned": 420},
    ])

    assert resolved["steps"] == 8432
    assert resolved["calories_burned"] == 420
    assert "sleep_hours" not in resolved
    assert "hrv" not in resolved
    assert resolved["field_sources"] == {"steps": "apple_health", "calories_burned": "apple_health"}
    assert resolved["primary_source"] == "apple_health"

def test_garmin_workout_preferred_over_duplicate_apple_health():
    activities = [
        {
            "id": "hk_run_1",
            "source": "apple_health",
            "start_time": "2026-08-08T08:00:00Z",
            "distance_m": 5000,
            "duration_s": 1500,
            "name": "Morning Run (Apple Health)",
        },
        {
            "id": "garmin_run_1",
            "source": "garmin",
            "start_time": "2026-08-08T08:02:00Z",
            "distance_m": 5050,
            "duration_s": 1510,
            "name": "Morning Run (Garmin)",
        },
    ]

    deduped = deduplicate_activities(activities)
    assert len(deduped) == 1
    assert deduped[0]["source"] == "garmin"
    assert deduped[0]["is_primary"] is True
    assert deduped[0]["duplicate_source_ids"] == ["hk_run_1"]

def test_fitbit_is_reserved_between_apple_health_and_manual():
    # Ranking stays Garmin > Strava > Apple Health, with Fitbit reserved before manual.
    assert DEFAULT_SOURCE_PRIORITY["garmin"] < DEFAULT_SOURCE_PRIORITY["strava"]
    assert DEFAULT_SOURCE_PRIORITY["strava"] < DEFAULT_SOURCE_PRIORITY["apple_health"]
    assert DEFAULT_SOURCE_PRIORITY["apple_health"] == DEFAULT_SOURCE_PRIORITY["healthkit"]
    assert DEFAULT_SOURCE_PRIORITY["apple_health"] < DEFAULT_SOURCE_PRIORITY["fitbit"] < DEFAULT_SOURCE_PRIORITY["manual"]
    assert SOURCE_PRIORITY_ORDER == ["garmin", "strava", "apple_health", "fitbit", "manual"]

    resolved = resolve_biometrics_priority([
        {"source": "manual", "steps": 100, "sleep_hours": 4},
        {"source": "fitbit", "steps": 4000, "sleep_hours": 5.5},
        {"source": "apple_health", "steps": 8000},
    ])
    assert resolved["steps"] == 8000
    assert resolved["sleep_hours"] == 5.5
    assert resolved["field_sources"]["steps"] == "apple_health"
    assert resolved["field_sources"]["sleep_hours"] == "fitbit"
    assert resolved["primary_source"] == "apple_health"


def _wipe_biometrics(uid):
    supabase.table("biometrics_daily").delete().eq("user_id", uid).execute()


def _stored_day(uid, day):
    rows = supabase.table("biometrics_daily").select("*").eq("user_id", uid).eq("date", day).execute().data
    assert len(rows) == 1
    return rows[0]


def test_stored_day_merges_garmin_sleep_with_apple_steps_and_ignores_nulls():
    """Write path: later Garmin nulls must not wipe Health steps, and Health must not replace Garmin sleep."""
    uid = 9911
    day = "2026-11-01"
    _wipe_biometrics(uid)
    try:
        upsert_biometrics_daily([{
            "user_id": uid,
            "date": day,
            "resting_hr": None,
            "hrv": None,
            "hrv_ms": None,
            "sleep_hours": None,
            "steps": None,
            "source": "garmin",
        }])
        record_daily_biometrics(uid, {
            "date": day,
            "steps": 9000,
            "resting_hr": 53,
            "sleep_hours": 6.0,
            "source": "apple_health",
        })
        after_health = _stored_day(uid, day)
        assert after_health["steps"] == 9000
        assert after_health["resting_hr"] == 53

        upsert_biometrics_daily([{
            "user_id": uid,
            "date": day,
            "resting_hr": None,
            "hrv": 51,
            "hrv_ms": 51,
            "hrv_status": "BALANCED",
            "sleep_score": 82,
            "sleep_hours": 7.4,
            "steps": None,
            "source": "garmin",
        }])
        merged = _stored_day(uid, day)
        assert merged["steps"] == 9000
        assert merged["resting_hr"] == 53
        assert merged["sleep_hours"] == 7.4
        assert merged["hrv"] == 51
        assert merged["hrv_status"] == "BALANCED"
        assert merged["field_sources"]["steps"] == "apple_health"
        assert merged["field_sources"]["sleep_hours"] == "garmin"
        assert merged["field_sources"]["hrv"] == "garmin"
        assert merged["source"] == "garmin"

        record_daily_biometrics(uid, {
            "date": day,
            "steps": 12000,
            "sleep_hours": 6.2,
            "hrv": 20,
            "source": "apple_health",
        })
        refreshed = _stored_day(uid, day)
        assert refreshed["steps"] == 12000
        assert refreshed["sleep_hours"] == 7.4
        assert refreshed["hrv"] == 51
        assert refreshed["field_sources"]["steps"] == "apple_health"

        upsert_biometrics_daily([{
            "user_id": uid,
            "date": day,
            "sleep_hours": 7.4,
            "hrv": 51,
            "steps": None,
            "source": "garmin",
        }])
        remirrored = _stored_day(uid, day)
        assert remirrored["steps"] == 12000
        assert remirrored["sleep_hours"] == 7.4
    finally:
        _wipe_biometrics(uid)

