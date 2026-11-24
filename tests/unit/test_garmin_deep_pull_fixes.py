"""Window, typed feeds, partial days. No network."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.garmin.cli import main as garmin_cli_main
from app.garmin.feeds import (
    BodyBatteryPayload,
    SleepPayload,
    StepsPayload,
    TrainingStatusPayload,
    is_empty_shell,
)
from app.garmin.sync import sync_all_garmin_data_for_user
from app.supabase_client import supabase
from app.tools.activity_tools import get_recent_activities, get_wellness_metrics

TODAY = date(2026, 11, 24)


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return TODAY


def _wipe(uid):
    for table, column in (
        ("biometrics_daily", "user_id"),
        ("garmin_daily", "user_id"),
        ("garmin_sleep", "user_id"),
        ("garmin_activities", "user_id"),
        ("users", "id"),
    ):
        supabase.table(table).delete().eq(column, uid).execute()


def _api(**overrides):
    api = MagicMock()
    api.get_activities.return_value = []
    api.get_steps_data.return_value = [{"steps": 100}, {"steps": 250}]
    api.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "id": 7,
            "sleepStartTimestampGMT": 1,
            "sleepEndTimestampGMT": 2,
            "sleepScores": {"overall": {"value": 80}},
            "sleepTimeSeconds": 28800,
            "deepSleepSeconds": 7200,
        },
        "sleepLevels": [{"startGMT": "a"}],
    }
    api.get_heart_rates.return_value = {"restingHeartRate": 48, "heartRateValues": []}
    api.get_rhr_day.return_value = {"allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 48}]}}}
    api.get_stress_data.return_value = {"avgStressLevel": 20}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 45, "status": "BALANCED"}}
    api.get_training_status.return_value = {}
    api.get_body_battery.return_value = []
    api.get_max_metrics.return_value = {}
    api.get_spo2_data.return_value = {}
    api.get_respiration_data.return_value = {}
    for name, value in overrides.items():
        getattr(api, name).return_value = value
    return api


def _sync(uid, api, goals=None, inception=None, **kwargs):
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid, "username": f"a{uid}", "password": "x",
        "garmin_email": f"a{uid}@example.com", "garmin_password": "stored", "goals": goals or {},
    }).execute()
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=api), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=inception or TODAY), \
         patch("app.garmin.sync.date", _FrozenDate), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        sync_all_garmin_data_for_user(uid, **kwargs)
    return [c.args[0] for c in api.get_sleep_data.call_args_list]


@pytest.mark.parametrize("raw,expected", [
    ([{"charged": 18, "highestBodyBattery": 91, "bodyBatteryValuesArray": [[1, 40]]}], 91),
    ({"charged": 18, "bodyBatteryValuesArray": [[1, 90], [2, 44]]}, 44),
    ({"charged": 18, "drained": 40}, None),
    ({"highestBodyBattery": 0, "charged": 12}, 0),
    (70, 70),
])
def test_body_battery_level_is_not_the_charged_delta(raw, expected):
    assert BodyBatteryPayload.parse(raw).level() == expected


def test_optional_training_and_vo2_fields_are_null_safe():
    parsed = TrainingStatusPayload.parse({
        "userTrainingStatus": None,
        "trainingStatusKey": "PRODUCTIVE",
        "mostRecentVO2Max": {"generic": None, "vo2Max": 48},
        "acuteTrainingLoad": 310,
    })
    assert parsed.status_key() == "PRODUCTIVE"
    assert parsed.vo2() == 48
    assert parsed.load() == 310
    assert StepsPayload.parse([{"steps": 100}, {"steps": 250}]).total() == 350
    assert StepsPayload.parse({"totalSteps": 1200}).total() == 1200
    shell = {"dailySleepDTO": {"id": None, "sleepStartTimestampGMT": None, "sleepEndTimestampGMT": None}, "sleepLevels": []}
    assert is_empty_shell(shell) is True
    assert is_empty_shell(None) is True
    assert SleepPayload.parse(shell).score() is None


@pytest.mark.parametrize("kwargs,present,absent", [
    ({"mode": "incremental", "days_back": 7, "goals": {"garmin_last_synced": "2026-11-23T15:00:00+00:00"}}, "2026-11-20", "2026-11-19"),
    ({"mode": "incremental", "goals": {"garmin_last_synced": "2026-11-23T15:00:00+00:00"}}, "2026-11-20", "2026-11-17"),
    ({"mode": "incremental", "days_back": 30, "force_resync": True, "goals": {"garmin_last_synced": "2026-11-23T15:00:00+00:00"}}, "2026-10-25", "2026-10-24"),
    ({"mode": "incremental", "days_back": 7, "start_date": "2026-10-01"}, "2026-10-01", "2026-09-30"),
])
def test_sync_window_honors_explicit_range(kwargs, present, absent):
    goals = kwargs.pop("goals", None)
    days = _sync(9910, _api(), goals=goals, **kwargs)
    assert present in days
    assert absent not in days


def test_null_training_status_still_persists_steps_and_raw_rows():
    api = _api(
        get_training_status={
            "userTrainingStatus": None,
            "trainingStatusKey": "PRODUCTIVE",
            "mostRecentVO2Max": {"generic": None, "vo2Max": 48},
        },
        get_body_battery=[{"charged": 18, "highestBodyBattery": 91}],
    )
    _sync(9911, api, mode="all_time", force_resync=True, inception=TODAY)
    bio = supabase.table("biometrics_daily").select("*").eq("user_id", 9911).execute().data
    daily = supabase.table("garmin_daily").select("*").eq("user_id", 9911).execute().data
    sleep = supabase.table("garmin_sleep").select("date").eq("user_id", 9911).execute().data
    assert bio and bio[0]["steps"] == 350 and bio[0]["body_battery"] == 91
    assert bio[0]["training_status"] == "PRODUCTIVE" and float(bio[0]["vo2_max"]) == 48
    assert bio[0]["sleep_score"] == 80 and daily and sleep
    record = get_wellness_metrics("9911", days=400)["records"][0]
    assert record["body_battery"] == 91 and record["stress_level"] == 20
    assert record.get("spo2") is None
    _wipe(9911)


def test_one_feed_failing_does_not_drop_the_day():
    api = _api()
    uid = 9912
    real = __import__("app.garmin.feeds", fromlist=["fetch_feed"]).fetch_feed

    def flaky(api_obj, feed, day, call):
        if feed.name == "body_battery":
            raise RuntimeError("battery down")
        return real(api_obj, feed, day, call)

    _wipe(uid)
    supabase.table("users").insert({
        "id": uid, "username": "a", "password": "x", "garmin_email": f"a{uid}@example.com",
        "garmin_password": "stored", "goals": {},
    }).execute()
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=api), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=TODAY), \
         patch("app.garmin.sync.date", _FrozenDate), \
         patch("app.garmin.sync.fetch_feed", side_effect=flaky), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=True)
    bio = supabase.table("biometrics_daily").select("*").eq("user_id", uid).execute().data
    assert bio and bio[0]["sleep_score"] == 80 and bio[0].get("body_battery") is None
    assert supabase.table("garmin_sleep").select("date").eq("user_id", uid).execute().data
    _wipe(uid)


def test_empty_sleep_shell_is_refetched():
    uid = 9913
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid, "username": "a", "password": "x", "garmin_email": f"a{uid}@example.com",
        "garmin_password": "stored", "goals": {},
    }).execute()
    for day, shell in (("2026-11-22", True), ("2026-11-21", False)):
        supabase.table("biometrics_daily").insert({
            "user_id": uid, "date": day, "resting_hr": 50, "sleep_score": 70, "hrv": 40, "source": "garmin",
        }).execute()
        supabase.table("garmin_sleep").insert({
            "user_id": uid, "date": day,
            "sleep_data": (
                {"dailySleepDTO": {"id": None, "sleepStartTimestampGMT": None, "sleepEndTimestampGMT": None}, "sleepLevels": []}
                if shell else
                {"dailySleepDTO": {"id": 9, "sleepStartTimestampGMT": 1, "sleepEndTimestampGMT": 2}, "sleepLevels": [{"startGMT": "a"}]}
            ),
        }).execute()
    api = _api()
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=api), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=date(2026, 11, 21)), \
         patch("app.garmin.sync.date", _FrozenDate), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=False)
    called = [c.args[0] for c in api.get_sleep_data.call_args_list]
    assert "2026-11-22" in called and "2026-11-21" not in called
    _wipe(uid)


def test_missing_activity_distance_is_null_not_zero():
    uid = 9914
    _wipe(uid)
    supabase.table("garmin_activities").insert({
        "user_id": uid, "activity_id": "a1", "activity_name": "Run",
        "start_time_local": "2026-11-23T12:00:00", "activity_type": "running",
    }).execute()
    found = get_recent_activities(str(uid), days=30)
    assert found["count"] == 1
    assert found["activities"][0]["distance_km"] is None
    assert found["activities"][0]["duration_min"] is None
    _wipe(uid)


def test_cli_forwards_start_date_and_rejects_bad_dates(monkeypatch):
    uid = 9915
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid, "username": "a", "password": "x", "garmin_email": f"a{uid}@example.com",
        "garmin_password": "stored", "goals": {},
    }).execute()
    monkeypatch.setenv("ENCRYPTION_KEY", "test-key")
    captured = {}
    monkeypatch.setattr("app.garmin.sync.sync_all_garmin_data_for_user", lambda *a, **k: captured.update(k))
    monkeypatch.setattr("app.analytics.analytics_service.AnalyticsService.calculate_baselines", lambda *a, **k: None)
    assert garmin_cli_main(["sync", "--user-id", str(uid), "--days-back", "30", "--force", "--start-date", "2018-01-01"]) == 0
    assert captured["days_back"] == 30 and captured["force_resync"] is True and captured["start_date"] == "2018-01-01"
    assert garmin_cli_main(["sync", "--user-id", str(uid), "--start-date", "11/04/2026"]) == 1
    _wipe(uid)
