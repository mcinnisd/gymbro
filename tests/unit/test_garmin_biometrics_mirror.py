"""Remirror biometrics_daily from stored Garmin rows, and don't drop it on sync."""
import argparse
from datetime import date
from unittest.mock import MagicMock, patch

from app.garmin.biometrics_mirror import (
    build_biometrics_from_raw,
    coerce_biometrics_row,
    remirror_biometrics_daily,
)
from app.mock_supabase import MockSupabaseClient
from app.supabase_client import supabase


UID = 8802


def _wipe(uid=UID):
    for table, column in (
        ("biometrics_daily", "user_id"),
        ("garmin_daily", "user_id"),
        ("garmin_sleep", "user_id"),
        ("users", "id"),
    ):
        supabase.table(table).delete().eq(column, uid).execute()


def _seed_raw(uid=UID, day="2026-09-15"):
    supabase.table("garmin_daily").insert({
        "user_id": uid,
        "date": day,
        "steps": [
            {"steps": 100, "endGMT": "2026-09-15T18:00:00.0", "pushes": 0, "startGMT": "2026-09-15T17:00:00.0"},
            {"steps": 50, "endGMT": "2026-09-15T19:00:00.0", "pushes": 0, "startGMT": "2026-09-15T18:00:00.0"},
        ],
        "resting_hr": 48.0,
        "stress": 18,
        "heartrate": {"restingHeartRate": 48},
    }).execute()
    supabase.table("garmin_sleep").insert({
        "user_id": uid,
        "date": day,
        "sleep_data": {
            "avgOvernightHrv": 42.5,
            "hrvStatus": "BALANCED",
            "restingHeartRate": 49,
            "sleepBodyBattery": [
                {"startGMT": "2026-09-15T06:00:00.0", "value": 30},
                {"startGMT": "2026-09-15T13:00:00.0", "value": 70},
            ],
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 81, "qualifierKey": "GOOD"}},
                "sleepTimeSeconds": 27000,
                "deepSleepSeconds": 5400,
                "remSleepSeconds": 6000,
                "lightSleepSeconds": 14000,
                "awakeSleepSeconds": 1600,
                "averageRespirationValue": 14.2,
            },
        },
    }).execute()


def test_coerce_float_resting_hr_and_hrv_ms_to_integers():
    row = coerce_biometrics_row({
        "user_id": "2",
        "date": "2026-09-15",
        "resting_hr": 48.0,
        "hrv": 42.5,
        "hrv_ms": 42.5,
        "sleep_score": 81.0,
        "sleep_hours": 500,
        "source": "garmin",
    })
    assert row["user_id"] == 2
    assert row["resting_hr"] == 48
    assert isinstance(row["resting_hr"], int)
    assert row["hrv"] == 42.5
    assert row["hrv_ms"] == 43
    assert isinstance(row["hrv_ms"], int)
    assert row["sleep_score"] == 81
    assert row["sleep_hours"] is None


def test_build_biometrics_from_stored_daily_and_sleep_shapes():
    daily = {
        "date": "2026-09-15",
        "steps": [{"steps": 100}, {"steps": 50}],
        "resting_hr": 48.0,
        "stress": 18,
    }
    sleep = {
        "date": "2026-09-15",
        "sleep_data": {
            "avgOvernightHrv": 42.5,
            "hrvStatus": "BALANCED",
            "restingHeartRate": 49,
            "sleepBodyBattery": [
                {"startGMT": "2026-09-15T06:00:00.0", "value": 30},
                {"startGMT": "2026-09-15T13:00:00.0", "value": 70},
            ],
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 81}},
                "sleepTimeSeconds": 27000,
                "deepSleepSeconds": 5400,
                "remSleepSeconds": 6000,
                "lightSleepSeconds": 14000,
                "awakeSleepSeconds": 1600,
                "averageRespirationValue": 14.2,
            },
        },
    }
    doc = build_biometrics_from_raw(2, "2026-09-15", daily, sleep)
    assert doc["resting_hr"] == 48
    assert doc["stress_level"] == 18
    assert doc["steps"] == 150
    assert doc["sleep_score"] == 81
    assert doc["sleep_hours"] == 7.5
    assert doc["hrv"] == 42.5
    assert doc["hrv_ms"] == 43
    assert doc["hrv_status"] == "BALANCED"
    assert doc["body_battery"] == 70
    assert doc["respiration"] == 14.2
    assert doc["deep_sleep_hours"] == 1.5
    assert "vo2_max" not in doc


def test_remirror_is_idempotent_preserves_vo2_and_collapses_duplicate_dates():
    _wipe()
    _seed_raw()
    supabase.table("biometrics_daily").insert({
        "user_id": UID,
        "date": "2026-09-15",
        "sleep_score": 1,
        "vo2_max": 55,
        "source": "garmin",
        "updated_at": "2026-09-16T00:00:00+00:00",
    }).execute()
    supabase.table("biometrics_daily").insert({
        "user_id": UID,
        "date": "2026-09-15",
        "sleep_score": 2,
        "source": "garmin",
        "updated_at": "2026-09-01T00:00:00+00:00",
    }).execute()

    first = remirror_biometrics_daily(str(UID))
    assert first.get("failed") == 0
    assert "error" not in first
    assert first["source_days"] == 1
    assert first["upserted"] == 1
    assert first["duplicates_removed"] == 1

    rows = supabase.table("biometrics_daily").select("*").eq("user_id", UID).execute().data
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 48
    assert isinstance(rows[0]["resting_hr"], int)
    assert rows[0]["sleep_score"] == 81
    assert rows[0]["hrv_ms"] == 43
    assert rows[0]["steps"] == 150
    assert float(rows[0]["vo2_max"]) == 55

    second = remirror_biometrics_daily(str(UID))
    assert second["duplicates_removed"] == 0
    assert second["upserted"] == 1
    assert second["failed"] == 0
    again = supabase.table("biometrics_daily").select("*").eq("user_id", UID).execute().data
    assert len(again) == 1
    assert again[0]["sleep_score"] == 81
    assert float(again[0]["vo2_max"]) == 55
    _wipe()


def test_remirror_falls_back_when_unique_constraint_missing(monkeypatch):
    _wipe()
    _seed_raw()
    original = MockSupabaseClient.upsert

    def reject_on_conflict(self, data, on_conflict=None):
        if self.current_table == "biometrics_daily":
            raise Exception(
                "there is no unique or exclusion constraint matching the ON CONFLICT specification"
            )
        return original(self, data, on_conflict)

    monkeypatch.setattr(MockSupabaseClient, "upsert", reject_on_conflict)
    result = remirror_biometrics_daily(UID)
    assert result["failed"] == 0
    assert result["upserted"] == 1
    rows = supabase.table("biometrics_daily").select("*").eq("user_id", UID).execute().data
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 48

    again = remirror_biometrics_daily(UID)
    assert again["failed"] == 0
    rows = supabase.table("biometrics_daily").select("*").eq("user_id", UID).execute().data
    assert len(rows) == 1
    assert rows[0]["sleep_score"] == 81
    _wipe()


def test_cli_remirror_biometrics_for_connected_user(capsys):
    _wipe()
    supabase.table("users").insert({
        "id": UID,
        "username": "athlete_8802",
        "password": "stored-ciphertext",
        "garmin_email": "athlete-8802@example.com",
        "garmin_password": "stored-ciphertext",
    }).execute()
    _seed_raw()
    from app.garmin.cli import cmd_remirror_biometrics

    code = cmd_remirror_biometrics(argparse.Namespace(user_id=str(UID)))
    captured = capsys.readouterr().out
    assert code == 0
    assert f"user_id={UID}" in captured
    assert "upserted=1" in captured
    assert "athlete-8802@example.com" not in captured
    rows = supabase.table("biometrics_daily").select("*").eq("user_id", UID).execute().data
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 48
    _wipe()


def _patch_int_columns(monkeypatch, reject_all=False):
    original = MockSupabaseClient.upsert
    int_fields = ("resting_hr", "hrv_ms", "sleep_score", "body_battery", "steps")

    def guarded(self, data, on_conflict=None):
        if self.current_table == "biometrics_daily":
            items = data if isinstance(data, list) else [data]
            for item in items:
                if reject_all:
                    raise Exception('invalid input syntax for type integer: "48.0"')
                for key in int_fields:
                    if isinstance(item.get(key), float):
                        raise Exception('invalid input syntax for type integer: "48.0"')
        return original(self, data, on_conflict)

    monkeypatch.setattr(MockSupabaseClient, "upsert", guarded)


def _run_one_day_sync(uid):
    from app.garmin.sync import sync_all_garmin_data_for_user

    supabase.table("users").insert({
        "id": uid,
        "username": f"athlete_{uid}",
        "password": "stored-ciphertext",
        "garmin_email": f"athlete-{uid}@example.com",
        "garmin_password": "stored-ciphertext",
        "goals": {},
    }).execute()
    mock_garmin = MagicMock()
    mock_garmin.get_activities.return_value = []
    mock_garmin.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "sleepScores": {"overall": {"value": 81}},
            "sleepTimeSeconds": 27000,
            "deepSleepSeconds": 5400,
            "remSleepSeconds": 6000,
            "lightSleepSeconds": 14000,
            "awakeSleepSeconds": 1600,
        }
    }
    mock_garmin.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 42.5, "status": "BALANCED"}}
    mock_garmin.get_rhr_day.return_value = {
        "allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 48.0}]}}
    }
    mock_garmin.get_stress_data.return_value = {"avgStressLevel": 18}
    today = date(2026, 9, 15)
    with patch("app.garmin.sync.init_garmin_api_for_user", return_value=mock_garmin), \
         patch("app.garmin.sync.discover_garmin_inception_date", return_value=today), \
         patch("app.garmin.sync.date") as mock_date, \
         patch("app.analytics.analytics_service.AnalyticsService.calculate_baselines"):
        mock_date.today.return_value = today
        sync_all_garmin_data_for_user(uid, mode="all_time", force_resync=True)


def test_sync_coerces_float_resting_hr_before_biometrics_upsert(monkeypatch):
    uid = 8803
    _wipe(uid)
    _patch_int_columns(monkeypatch, reject_all=False)
    _run_one_day_sync(uid)
    bio = supabase.table("biometrics_daily").select("*").eq("user_id", uid).execute().data
    assert len(bio) == 1
    assert bio[0]["date"] == "2026-09-15"
    assert bio[0]["resting_hr"] == 48
    assert isinstance(bio[0]["resting_hr"], int)
    assert bio[0]["hrv_ms"] == 43
    assert isinstance(bio[0]["hrv_ms"], int)
    assert bio[0]["sleep_score"] == 81
    daily = supabase.table("garmin_daily").select("*").eq("user_id", uid).execute().data
    assert len(daily) == 1
    user = supabase.table("users").select("garmin_sync_status,garmin_last_sync_error").eq("id", uid).execute().data
    assert user[0]["garmin_sync_status"] == "synced"
    assert not user[0].get("garmin_last_sync_error")
    _wipe(uid)


def test_sync_marks_error_when_biometrics_upsert_still_fails(monkeypatch):
    uid = 8804
    _wipe(uid)
    _patch_int_columns(monkeypatch, reject_all=True)
    _run_one_day_sync(uid)
    daily = supabase.table("garmin_daily").select("*").eq("user_id", uid).execute().data
    assert len(daily) == 1
    user = supabase.table("users").select("garmin_sync_status,garmin_last_sync_error").eq("id", uid).execute().data
    assert user[0]["garmin_sync_status"] == "error"
    assert "biometrics_daily" in (user[0].get("garmin_last_sync_error") or "")
    _wipe(uid)
