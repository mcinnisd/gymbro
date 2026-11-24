from app.analytics.analytics_service import AnalyticsService
from app.supabase_client import supabase


def _user(uid, goals=None):
    supabase.table("users").upsert([{
        "id": uid, "username": f"u{uid}@test.com", "goals": goals or {},
    }]).execute()


def _activities(uid, rows):
    payload = []
    for aid, name, kind, start, dist, dur, hr, elev in rows:
        row = {
            "user_id": uid, "activity_id": aid, "activity_name": name, "activity_type": kind,
            "start_time_local": start, "distance": dist, "duration": dur, "average_hr": hr,
        }
        if elev is not None:
            row["elevation_gain"] = elev
        payload.append(row)
    supabase.table("garmin_activities").upsert(payload, on_conflict="activity_id").execute()


def test_running_prs_extraction_including_mile():
    uid = 301
    _user(uid)
    _activities(uid, [
        ("run_1k", "1k Speed Work", "running", "2022-04-10T08:00:00", 1000, 220, 165, None),
        ("run_1mi", "Mile Time Trial", "running", "2023-06-15T09:00:00", 1610, 360, 172, None),
        ("run_5k", "5k Parkrun", "running", "2024-03-20T08:30:00", 5050, 1200, 170, None),
        ("run_10k", "10k Road Race", "running", "2024-10-12T07:30:00", 10050, 2550, 168, None),
        ("run_half", "City Half Marathon", "running", "2025-05-18T07:00:00", 21150, 5580, 166, None),
        ("run_full", "Spring Marathon", "running", "2026-04-14T06:45:00", 42250, 11700, 164, None),
    ])
    pbs = (AnalyticsService.calculate_baselines(uid) or {}).get("pbs") or {}
    for key in ("1k", "1 Mile", "5k", "10k", "Half Marathon", "Marathon"):
        assert key in pbs
    assert pbs["1 Mile"]["time_seconds"] > 0
    assert pbs["5k"]["time_seconds"] > 0
    assert pbs["Marathon"]["time_seconds"] > 0


def test_cycling_milestones_extraction():
    uid = 302
    _user(uid)
    _activities(uid, [
        ("ride_1", "Sunday Gran Fondo", "cycling", "2024-07-21T07:00:00", 105000, 12600, 142, 1450),
        ("ride_2", "Mountain Climb", "cycling", "2025-08-10T08:00:00", 65000, 9000, 158, 2100),
    ])
    cycling = (AnalyticsService.calculate_baselines(uid) or {}).get("cycling") or {}
    assert cycling.get("longest_ride_km") == 105.0
    assert cycling.get("max_elevation_m") == 2100.0
    assert cycling.get("longest_duration_hours") == 3.5


def test_aerobic_efficiency_curve_calculation():
    uid = 303
    _user(uid)
    _activities(uid, [
        ("eff_2023", "2023 Tempo", "running", "2023-05-10T08:00:00", 10000, 3000, 160, None),
        ("eff_2024", "2024 Tempo", "running", "2024-05-10T08:00:00", 10000, 2700, 155, None),
    ])
    eff = (AnalyticsService.calculate_baselines(uid) or {}).get("aerobic_efficiency_by_year") or {}
    assert eff["2024"]["efficiency_score"] > eff["2023"]["efficiency_score"]


def test_baselines_persisted_to_user_goals():
    uid = 304
    _user(uid, {"existing_goal": "sub_3_marathon"})
    _activities(uid, [
        ("fast_5k", "Fast 5k", "running", "2026-03-01T08:00:00", 5000, 1150, 175, None),
    ])
    AnalyticsService.calculate_baselines(uid)
    goals = (supabase.table("users").select("goals").eq("id", uid).execute().data[0].get("goals") or {})
    assert "5k" in goals["personal_records"]
    assert goals.get("existing_goal") == "sub_3_marathon"
