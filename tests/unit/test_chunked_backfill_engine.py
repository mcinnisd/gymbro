import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock, patch
from app.supabase_client import supabase
from app.garmin.sync import generate_monthly_chunks, sync_all_garmin_data_for_user

def test_monthly_chunk_generator_ranges():
    """Verify generate_monthly_chunks slices multi-year date ranges into reverse-chronological 30-day windows."""
    end_d = date(2026, 8, 1)
    start_d = date(2023, 8, 1) # 3 years ago
    
    chunks = generate_monthly_chunks(start_d, end_d, chunk_size_days=30)
    assert len(chunks) > 0
    
    # First chunk should end at end_d
    assert chunks[0][1] == end_d
    # Last chunk should start at or before start_d
    assert chunks[-1][0] <= start_d
    
    # Verify continuity
    for i in range(len(chunks) - 1):
        curr_start = chunks[i][0]
        next_end = chunks[i + 1][1]
        assert curr_start == next_end + timedelta(days=1)

def test_smart_delta_skipping_in_monthly_chunks():
    """Verify smart delta skips API queries for dates already populated in biometrics_daily."""
    uid = 202
    existing_date_1 = "2024-05-10"
    existing_date_2 = "2024-05-11"
    
    supabase.table("biometrics_daily").upsert([
        {
            "user_id": uid,
            "date": existing_date_1,
            "resting_hr": 54,
            "hrv": 65,
            "sleep_score": 85,
            "sleep_hours": 7.5,
            "source": "garmin"
        },
        {
            "user_id": uid,
            "date": existing_date_2,
            "resting_hr": 55,
            "hrv": 62,
            "sleep_score": 80,
            "sleep_hours": 7.2,
            "source": "garmin"
        }
    ]).execute()
    
    mock_garmin = MagicMock()
    # Mock return values for missing date
    mock_garmin.get_activities.return_value = []
    mock_garmin.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "sleepScores": {"overall": {"value": 88}},
            "sleepTimeSeconds": 28800,
            "deepSleepSeconds": 7200,
            "remSleepSeconds": 6000,
            "lightSleepSeconds": 14400,
            "awakeSleepSeconds": 1200
        }
    }
    mock_garmin.get_hrv_data.return_value = {"hrvSummary": {"weeklyAvg": 70, "status": "Balanced"}}
    mock_garmin.get_rhr_day.return_value = {"allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 50}]}}}
    mock_garmin.get_stats_and_body_battery.return_value = [{"bodyBatteryValuesArray": [[0, 85]]}]
    mock_garmin.get_stress_data.return_value = {"overallStressLevel": 22}
    
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=mock_garmin), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=date(2024, 5, 9)), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=False)
        
        # Verify get_sleep_data was NOT called for 2024-05-10 or 2024-05-11
        called_dates = [call.args[0] for call in mock_garmin.get_sleep_data.call_args_list]
        assert existing_date_1 not in called_dates
        assert existing_date_2 not in called_dates

def test_rate_limit_and_error_resilience():
    """Verify transient rate limit (429) errors on daily endpoints are handled with retry and don't crash backfill."""
    uid = 203
    supabase.table("users").upsert([{
        "id": uid,
        "username": f"resilience_{uid}@test.com",
        "garmin_email": "athlete@garmin.com",
        "garmin_password": "pass",
        "garmin_sync_status": "syncing",
        "goals": {}
    }]).execute()

    mock_garmin = MagicMock()
    mock_garmin.get_activities.return_value = []
    
    # Simulate a rate limit error on first attempt, success on second
    call_count = {"count": 0}
    def mock_sleep(day_str):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise Exception("429 Too Many Requests: Rate limited")
        return {"dailySleepDTO": {"sleepScores": {"overall": {"value": 82}}, "sleepTimeSeconds": 27000}}
    
    mock_garmin.get_sleep_data.side_effect = mock_sleep
    mock_garmin.get_hrv_data.return_value = {"hrvSummary": {"weeklyAvg": 68}}
    mock_garmin.get_rhr_day.return_value = {"allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 52}]}}}
    mock_garmin.get_stats_and_body_battery.return_value = []
    mock_garmin.get_stress_data.return_value = {}
    
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=mock_garmin), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=date(2026, 8, 13)), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        
        # Should complete cleanly without unhandled exception
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=True)
        
        # Verify sync marked as completed
        user_res = supabase.table("users").select("garmin_sync_status, goals").eq("id", uid).execute()
        assert user_res.data[0]["garmin_sync_status"] == "synced"
