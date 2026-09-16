import pytest
from datetime import datetime, timezone, timedelta
from app.supabase_client import supabase
from app.analytics.analytics_service import AnalyticsService

def test_running_prs_extraction_including_mile():
    """Verify calculate_baselines extracts standard running PRs including 1 Mile, 5k, 10k, Half, and Marathon."""
    uid = 301
    supabase.table("users").upsert([{
        "id": uid,
        "username": f"runner_{uid}@test.com",
        "goals": {}
    }]).execute()
    
    activities = [
        {
            "user_id": uid,
            "activity_id": "run_1k",
            "activity_name": "1k Speed Work",
            "activity_type": "running",
            "start_time_local": "2022-04-10T08:00:00",
            "distance": 1000,
            "duration": 220, # 3:40 / km
            "average_hr": 165
        },
        {
            "user_id": uid,
            "activity_id": "run_1mi",
            "activity_name": "Mile Time Trial",
            "activity_type": "running",
            "start_time_local": "2023-06-15T09:00:00",
            "distance": 1610,
            "duration": 360, # ~5:58 mile
            "average_hr": 172
        },
        {
            "user_id": uid,
            "activity_id": "run_5k",
            "activity_name": "5k Parkrun",
            "activity_type": "running",
            "start_time_local": "2024-03-20T08:30:00",
            "distance": 5050,
            "duration": 1200, # 19:48 5k
            "average_hr": 170
        },
        {
            "user_id": uid,
            "activity_id": "run_10k",
            "activity_name": "10k Road Race",
            "activity_type": "running",
            "start_time_local": "2024-10-12T07:30:00",
            "distance": 10050,
            "duration": 2550, # 42:16 10k
            "average_hr": 168
        },
        {
            "user_id": uid,
            "activity_id": "run_half",
            "activity_name": "City Half Marathon",
            "activity_type": "running",
            "start_time_local": "2025-05-18T07:00:00",
            "distance": 21150,
            "duration": 5580, # 1:32:38 HM
            "average_hr": 166
        },
        {
            "user_id": uid,
            "activity_id": "run_full",
            "activity_name": "Spring Marathon",
            "activity_type": "running",
            "start_time_local": "2026-04-14T06:45:00",
            "distance": 42250,
            "duration": 11700, # 3:14:35 Marathon
            "average_hr": 164
        }
    ]
    
    supabase.table("garmin_activities").upsert(activities, on_conflict="activity_id").execute()
    
    baselines = AnalyticsService.calculate_baselines(uid)
    assert baselines is not None
    pbs = baselines.get("pbs") or {}
    
    assert "1k" in pbs
    assert "1 Mile" in pbs
    assert "5k" in pbs
    assert "10k" in pbs
    assert "Half Marathon" in pbs
    assert "Marathon" in pbs
    
    assert pbs["1 Mile"]["time_seconds"] > 0
    assert pbs["5k"]["time_seconds"] > 0
    assert pbs["Marathon"]["time_seconds"] > 0

def test_cycling_milestones_extraction():
    """Verify calculate_baselines extracts cycling milestones (longest ride, max climb, duration)."""
    uid = 302
    supabase.table("users").upsert([{
        "id": uid,
        "username": f"cyclist_{uid}@test.com",
        "goals": {}
    }]).execute()
    
    rides = [
        {
            "user_id": uid,
            "activity_id": "ride_1",
            "activity_name": "Sunday Gran Fondo",
            "activity_type": "cycling",
            "start_time_local": "2024-07-21T07:00:00",
            "distance": 105000, # 105 km
            "duration": 12600,  # 3.5 hours
            "elevation_gain": 1450,
            "average_hr": 142
        },
        {
            "user_id": uid,
            "activity_id": "ride_2",
            "activity_name": "Mountain Climb",
            "activity_type": "cycling",
            "start_time_local": "2025-08-10T08:00:00",
            "distance": 65000,  # 65 km
            "duration": 9000,   # 2.5 hours
            "elevation_gain": 2100, # 2100m climb
            "average_hr": 158
        }
    ]
    supabase.table("garmin_activities").upsert(rides, on_conflict="activity_id").execute()
    
    baselines = AnalyticsService.calculate_baselines(uid)
    assert baselines is not None
    cycling = baselines.get("cycling") or {}
    
    assert cycling.get("longest_ride_km") == 105.0
    assert cycling.get("max_elevation_m") == 2100.0
    assert cycling.get("longest_duration_hours") == 3.5

def test_aerobic_efficiency_curve_calculation():
    """Verify calculate_baselines computes multi-year aerobic efficiency trends."""
    uid = 303
    supabase.table("users").upsert([{
        "id": uid,
        "username": f"efficiency_{uid}@test.com",
        "goals": {}
    }]).execute()
    
    runs = [
        {
            "user_id": uid,
            "activity_id": "eff_2023",
            "activity_name": "2023 Tempo",
            "activity_type": "running",
            "start_time_local": "2023-05-10T08:00:00",
            "distance": 10000,
            "duration": 3000, # 5:00 / km = 3.33 m/s
            "average_hr": 160
        },
        {
            "user_id": uid,
            "activity_id": "eff_2024",
            "activity_name": "2024 Tempo",
            "activity_type": "running",
            "start_time_local": "2024-05-10T08:00:00",
            "distance": 10000,
            "duration": 2700, # 4:30 / km = 3.70 m/s
            "average_hr": 155
        }
    ]
    supabase.table("garmin_activities").upsert(runs, on_conflict="activity_id").execute()
    
    baselines = AnalyticsService.calculate_baselines(uid)
    assert baselines is not None
    eff = baselines.get("aerobic_efficiency_by_year") or {}
    
    assert "2023" in eff
    assert "2024" in eff
    # 2024 efficiency should be higher (faster speed at lower heart rate)
    assert eff["2024"]["efficiency_score"] > eff["2023"]["efficiency_score"]

def test_baselines_persisted_to_user_goals():
    """Verify calculated PRs and baselines are saved into users.goals."""
    uid = 304
    supabase.table("users").upsert([{
        "id": uid,
        "username": f"goals_user_{uid}@test.com",
        "goals": {"existing_goal": "sub_3_marathon"}
    }]).execute()
    
    supabase.table("garmin_activities").upsert([{
        "user_id": uid,
        "activity_id": "fast_5k",
        "activity_name": "Fast 5k",
        "activity_type": "running",
        "start_time_local": "2026-03-01T08:00:00",
        "distance": 5000,
        "duration": 1150,
        "average_hr": 175
    }], on_conflict="activity_id").execute()
    
    AnalyticsService.calculate_baselines(uid)
    
    user_res = supabase.table("users").select("goals").eq("id", uid).execute()
    user_goals = user_res.data[0].get("goals") or {}
    
    assert "personal_records" in user_goals
    assert "5k" in user_goals["personal_records"]
    assert user_goals.get("existing_goal") == "sub_3_marathon"
