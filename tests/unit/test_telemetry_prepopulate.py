import pytest
from datetime import datetime, timedelta, timezone
from app.supabase_client import supabase
from app.onboarding.prepopulate_service import TelemetryPrepopulateService, format_duration


@pytest.fixture
def mock_telemetry_user(client):
    """Seed a test user with mock biometrics and activities."""
    user_id = 9991
    # Clean/seed user in mock DB
    supabase.table("users").upsert({
        "id": user_id,
        "username": f"onboarding_user_{user_id}",
        "age": 32,
        "weight": 76.5,
        "height": 181.0,
        "sport_history": "Running and Gym",
        "running_experience": "Intermediate",
        "goals": {}
    }, on_conflict="id").execute()

    return user_id


def test_format_duration():
    assert format_duration(3600) == "1:00:00"
    assert format_duration(3665) == "1:01:05"
    assert format_duration(1500) == "25:00"
    assert format_duration(45) == "0:45"
    assert format_duration(None) is None
    assert format_duration("invalid") is None


def test_prepopulate_fallback_when_empty():
    """When a new user has no wearable data, return sensible defaults without crashing."""
    empty_user_id = 9992
    supabase.table("users").upsert({
        "id": empty_user_id,
        "username": f"empty_user_{empty_user_id}",
        "goals": {}
    }, on_conflict="id").execute()

    data = TelemetryPrepopulateService.get_prepopulation_data(empty_user_id)
    assert data is not None
    assert data["data_available"] is False
    assert data["resting_hr"] == 65
    assert data["sleep_hours"] == 7.5
    assert data["weekly_volume"] == 0.0
    assert data["running_experience"] == "Beginner"
    assert data["connected_providers"] == []
    assert data["personal_records"]["run_5k"] is None


def test_prepopulate_with_garmin_daily_and_sleep(mock_telemetry_user):
    user_id = mock_telemetry_user
    today = datetime.now(timezone.utc).date()

    # Seed 14 days of garmin_daily & sleep
    for i in range(14):
        d_str = (today - timedelta(days=i)).isoformat()
        supabase.table("garmin_daily").insert({
            "user_id": user_id,
            "date": d_str,
            "resting_hr": 54 if i % 2 == 0 else 56
        }).execute()

        supabase.table("garmin_sleep").insert({
            "user_id": user_id,
            "date": d_str,
            "sleep_data": {
                "dailySleepDTO": {
                    "sleepTimeSeconds": 28800  # 8.0 hours
                }
            }
        }).execute()

    data = TelemetryPrepopulateService.get_prepopulation_data(user_id)
    assert data is not None
    assert data["data_available"] is True
    assert data["resting_hr"] == 55
    assert data["sleep_hours"] == 8.0
    assert data["age"] == 32
    assert data["weight"] == 76.5
    assert data["height"] == 181.0


def test_prepopulate_with_biometrics_daily_and_hrv(mock_telemetry_user):
    user_id = mock_telemetry_user
    today = datetime.now(timezone.utc).date()

    # Seed biometrics_daily with HRV
    for i in range(7):
        d_str = (today - timedelta(days=i)).isoformat()
        supabase.table("biometrics_daily").upsert({
            "user_id": user_id,
            "date": d_str,
            "resting_hr": 50,
            "hrv": 75,
            "sleep_hours": 7.8,
            "source": "apple_health"
        }, on_conflict="user_id, date").execute()

    data = TelemetryPrepopulateService.get_prepopulation_data(user_id)
    assert data is not None
    assert data["data_available"] is True
    assert data["hrv"] == 75
    assert "apple_health" in data["connected_providers"]


def test_prepopulate_weekly_volume_and_prs(mock_telemetry_user):
    user_id = mock_telemetry_user
    now = datetime.now(timezone.utc)

    # 1. Insert 5k run (approx 5000m in 1320s = 22:00)
    supabase.table("garmin_activities").insert({
        "user_id": user_id,
        "activity_id": "garmin_run_5k",
        "activity_name": "5k Tempo",
        "activity_type": "running",
        "start_time_local": (now - timedelta(days=3)).isoformat(),
        "distance": 5000.0,
        "duration": 1320.0
    }).execute()

    # 2. Insert 10k run (approx 10000m in 2820s = 47:00)
    supabase.table("strava_activities").insert({
        "user_id": user_id,
        "activity_id": "strava_run_10k",
        "name": "10k Progression",
        "type": "Run",
        "start_date_local": (now - timedelta(days=7)).isoformat(),
        "distance": 10000.0,
        "moving_time": 2820.0
    }).execute()

    # 3. Insert Long Bike Ride
    supabase.table("strava_activities").insert({
        "user_id": user_id,
        "activity_id": "strava_bike_longest",
        "name": "Weekend Century",
        "type": "Ride",
        "start_date_local": (now - timedelta(days=12)).isoformat(),
        "distance": 85000.0,
        "moving_time": 10800.0
    }).execute()

    data = TelemetryPrepopulateService.get_prepopulation_data(user_id)
    assert data is not None
    assert data["personal_records"]["run_5k"] == "22:00"
    assert data["personal_records"]["run_10k"] == "47:00"
    assert "85 km" in data["personal_records"]["bike_longest"]
    # 15km total in last 28 days -> ~3.8 km/week average
    assert data["weekly_volume"] > 0


def test_ingest_raw_healthkit_payload_in_prepopulate():
    user_id = 9993
    supabase.table("users").upsert({
        "id": user_id,
        "username": f"healthkit_user_{user_id}",
        "goals": {}
    }, on_conflict="id").execute()

    payload = {
        "source": "apple_health",
        "biometrics": [
            {
                "date": "2026-08-15",
                "resting_hr": 52,
                "hrv": 68,
                "sleep_hours": 8.2,
                "steps": 12500
            }
        ],
        "activities": [
            {
                "activity_id": "hk_run_101",
                "activity_type": "running",
                "name": "Morning 5k",
                "distance": 5000.0,
                "duration": 1500.0,
                "start_time_local": "2026-08-15T07:00:00Z"
            }
        ]
    }

    data = TelemetryPrepopulateService.get_prepopulation_data(user_id, raw_payload=payload)
    assert data is not None
    assert data["data_available"] is True
    assert data["resting_hr"] == 52
    assert data["hrv"] == 68
    assert data["sleep_hours"] == 8.2
    assert "apple_health" in data["connected_providers"]
