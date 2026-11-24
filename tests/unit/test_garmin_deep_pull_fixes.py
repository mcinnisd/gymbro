"""Deep-pull fixes: window, null-safe derived fields, steps, body battery, empty sleep."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.garmin.cli import main as garmin_cli_main
from app.garmin.sync import (
    _body_battery_level,
    _daily_steps,
    _sleep_is_empty_shell,
    sync_all_garmin_data_for_user,
)
from app.supabase_client import supabase

TODAY = date(2026, 11, 24)
UID = 9901


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return TODAY


def _wipe(uid=UID):
    for table, column in (
        ("biometrics_daily", "user_id"),
        ("garmin_daily", "user_id"),
        ("garmin_sleep", "user_id"),
        ("garmin_maxmetrics", "user_id"),
        ("users", "id"),
    ):
        supabase.table(table).delete().eq(column, uid).execute()


def _api():
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
        },
        "sleepLevels": [{"startGMT": "a", "endGMT": "b"}],
    }
    api.get_heart_rates.return_value = {"restingHeartRate": 48}
    api.get_rhr_day.return_value = {
        "allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 48}]}}
    }
    api.get_stress_data.return_value = {"avgStressLevel": 20}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 45, "status": "BALANCED"}}
    api.get_training_status.return_value = {}
    api.get_body_battery.return_value = []
    api.get_max_metrics.return_value = {}
    api.get_spo2_data.return_value = {}
    api.get_respiration_data.return_value = {}
    return api


def _sync(uid, api, goals=None, inception=None, **kwargs):
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid,
        "username": f"athlete{uid}",
        "password": "x",
        "garmin_email": f"athlete{uid}@example.com",
        "garmin_password": "stored",
        "goals": goals or {},
    }).execute()
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=api), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=inception or TODAY), \
         patch("app.garmin.sync.date", _FrozenDate), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        sync_all_garmin_data_for_user(uid, **kwargs)
    return [call.args[0] for call in api.get_sleep_data.call_args_list]


def _recent_goals():
    return {"garmin_last_synced": "2026-11-23T15:00:00+00:00"}


def test_plain_incremental_stays_inside_seven_days():
    days = _sync(9901, _api(), goals=_recent_goals(), mode="incremental", days_back=7)
    assert "2026-11-20" in days
    assert "2026-11-19" not in days
    assert "2026-11-24" in days


def test_omitted_days_back_does_not_expand_incremental_to_the_default_365():
    days = _sync(9902, _api(), goals=_recent_goals(), mode="incremental")
    assert "2026-11-20" in days
    assert "2026-11-17" not in days


def test_explicit_days_back_and_force_honor_the_requested_window():
    forced = _sync(
        9903, _api(), goals=_recent_goals(), mode="incremental", days_back=30, force_resync=True,
    )
    assert "2026-10-25" in forced
    assert "2026-10-24" not in forced
    assert "2026-11-04" in forced

    explicit = _sync(9904, _api(), goals=_recent_goals(), mode="incremental", days_back=30)
    assert "2026-10-25" in explicit
    assert "2026-10-24" not in explicit

    # --force alone still requests the 7-day window, without shrinking to last_synced-3.
    force_default = _sync(
        9905, _api(), goals=_recent_goals(), mode="incremental", days_back=7, force_resync=True,
    )
    assert "2026-11-17" in force_default
    assert "2026-11-16" not in force_default


def test_start_date_requests_a_long_backfill_through_the_same_entry_point():
    days = _sync(
        9906, _api(), mode="incremental", days_back=7, start_date="2026-10-01",
    )
    assert "2026-10-01" in days
    assert "2026-09-30" not in days
    assert "2026-11-24" in days


def test_cli_forwards_start_date_days_back_and_force(monkeypatch):
    uid = 9907
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid,
        "username": f"athlete{uid}",
        "password": "x",
        "garmin_email": f"athlete{uid}@example.com",
        "garmin_password": "stored",
        "goals": {},
    }).execute()
    monkeypatch.setenv("ENCRYPTION_KEY", "test-key")
    captured = {}

    def fake_sync(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr("app.garmin.sync.sync_all_garmin_data_for_user", fake_sync)
    monkeypatch.setattr(
        "app.analytics.analytics_service.AnalyticsService.calculate_baselines",
        lambda *a, **k: None,
    )
    code = garmin_cli_main([
        "sync", "--user-id", str(uid), "--mode", "incremental",
        "--days-back", "30", "--force", "--start-date", "2018-01-01",
    ])
    assert code == 0
    assert captured["kwargs"]["days_back"] == 30
    assert captured["kwargs"]["force_resync"] is True
    assert captured["kwargs"]["mode"] == "incremental"
    assert captured["kwargs"]["start_date"] == "2018-01-01"
    _wipe(uid)


def test_cli_rejects_a_bad_start_date(monkeypatch):
    uid = 9908
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid,
        "username": f"athlete{uid}",
        "password": "x",
        "garmin_email": f"athlete{uid}@example.com",
        "garmin_password": "stored",
        "goals": {},
    }).execute()
    monkeypatch.setenv("ENCRYPTION_KEY", "test-key")
    called = []
    monkeypatch.setattr(
        "app.garmin.sync.sync_all_garmin_data_for_user",
        lambda *a, **k: called.append(1),
    )
    code = garmin_cli_main([
        "sync", "--user-id", str(uid), "--start-date", "11/04/2026",
    ])
    assert code == 1
    assert called == []
    _wipe(uid)


def test_null_training_status_and_vo2_still_persist_the_day():
    api = _api()
    api.get_training_status.return_value = {
        "userTrainingStatus": None,
        "trainingStatusKey": "PRODUCTIVE",
        "mostRecentVO2Max": {"generic": None, "vo2Max": 48},
        "acuteTrainingLoad": 310,
    }
    api.get_body_battery.return_value = [{
        "charged": 18,
        "drained": 55,
        "highestBodyBattery": 91,
        "bodyBatteryValuesArray": [[1, 90], [2, 40]],
    }]
    _sync(9909, api, mode="all_time", force_resync=True, inception=TODAY)

    daily = supabase.table("garmin_daily").select("*").eq("user_id", 9909).execute().data
    sleep = supabase.table("garmin_sleep").select("*").eq("user_id", 9909).execute().data
    bio = supabase.table("biometrics_daily").select("*").eq("user_id", 9909).execute().data
    assert len(daily) == 1
    assert len(sleep) == 1
    assert len(bio) == 1
    assert bio[0]["date"] == "2026-11-24"
    assert bio[0]["training_status"] == "PRODUCTIVE"
    assert float(bio[0]["vo2_max"]) == 48
    assert bio[0]["acute_load"] == 310
    assert bio[0]["steps"] == 350
    assert bio[0]["body_battery"] == 91
    assert bio[0]["sleep_score"] == 80
    assert daily[0]["steps"] == [{"steps": 100}, {"steps": 250}]
    user = supabase.table("users").select("garmin_sync_status").eq("id", 9909).execute().data
    assert user[0]["garmin_sync_status"] == "synced"
    _wipe(9909)


def test_derived_parse_failure_still_writes_raw_rows():
    api = _api()

    def explode(_payload):
        raise RuntimeError("derived parse failed")

    uid = 9910
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid,
        "username": f"athlete{uid}",
        "password": "x",
        "garmin_email": f"athlete{uid}@example.com",
        "garmin_password": "stored",
        "goals": {},
    }).execute()
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=api), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=TODAY), \
         patch("app.garmin.sync.date", _FrozenDate), \
         patch("app.garmin.sync._body_battery_level", side_effect=explode), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=True)
    daily = supabase.table("garmin_daily").select("date").eq("user_id", uid).execute().data
    sleep = supabase.table("garmin_sleep").select("date").eq("user_id", uid).execute().data
    bio = supabase.table("biometrics_daily").select("date").eq("user_id", uid).execute().data
    assert [row["date"] for row in daily] == ["2026-11-24"]
    assert [row["date"] for row in sleep] == ["2026-11-24"]
    assert bio == []
    _wipe(uid)


def test_body_battery_level_ignores_charged_delta():
    assert _body_battery_level([{
        "charged": 18,
        "highestBodyBattery": 91,
        "bodyBatteryValuesArray": [[1, 90], [2, 40]],
    }]) == 91
    assert _body_battery_level({
        "charged": 18,
        "bodyBatteryValuesArray": [[1, 90], [2, 44], [3, None]],
    }) == 44
    assert _body_battery_level({"charged": 18, "drained": 40}) is None
    assert _body_battery_level({"charged": 5, "value": 63}) == 63
    assert _body_battery_level({"highestBodyBattery": 0, "charged": 12}) == 0
    assert _body_battery_level(70) == 70
    assert _daily_steps([{"steps": 100}, {"steps": 250}]) == 350
    assert _daily_steps({"totalSteps": 1200}) == 1200


def test_empty_sleep_shell_is_refetched_and_a_real_session_is_not():
    uid = 9911
    _wipe(uid)
    supabase.table("users").insert({
        "id": uid,
        "username": f"athlete{uid}",
        "password": "x",
        "garmin_email": f"athlete{uid}@example.com",
        "garmin_password": "stored",
        "goals": {},
    }).execute()
    for day, rhr in (("2026-11-04", 50), ("2026-11-05", 51)):
        supabase.table("biometrics_daily").insert({
            "user_id": uid,
            "date": day,
            "resting_hr": rhr,
            "source": "garmin",
        }).execute()
    supabase.table("garmin_sleep").insert({
        "user_id": uid,
        "date": "2026-11-04",
        "sleep_data": {
            "dailySleepDTO": {
                "id": None,
                "sleepStartTimestampGMT": None,
                "sleepEndTimestampGMT": None,
            },
            "sleepLevels": [],
        },
    }).execute()
    supabase.table("garmin_sleep").insert({
        "user_id": uid,
        "date": "2026-11-05",
        "sleep_data": {
            "dailySleepDTO": {
                "id": 99,
                "sleepStartTimestampGMT": 1,
                "sleepEndTimestampGMT": 2,
            },
            "sleepLevels": [{"startGMT": "a"}],
        },
    }).execute()
    api = _api()
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=api), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=date(2026, 11, 4)), \
         patch("app.garmin.sync.date", _FrozenDate), \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=False)
    called = [call.args[0] for call in api.get_sleep_data.call_args_list]
    assert "2026-11-04" in called
    assert "2026-11-06" in called
    assert "2026-11-05" not in called
    _wipe(uid)


def test_sleep_shell_predicate_matches_missing_session_data():
    shell = {
        "dailySleepDTO": {"id": None, "sleepStartTimestampGMT": None, "sleepEndTimestampGMT": None},
        "sleepLevels": [],
    }
    assert _sleep_is_empty_shell(shell) is True
    assert _sleep_is_empty_shell({"dailySleepDTO": {"sleepStartTimestampGMT": 5}}) is False
    assert _sleep_is_empty_shell(None) is True
