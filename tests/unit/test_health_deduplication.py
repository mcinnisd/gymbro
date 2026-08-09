import pytest
from app.health_hub.deduplication_service import deduplicate_activities, resolve_biometrics_priority

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

