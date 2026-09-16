import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.garmin.routes import sync_if_needed
from app.scheduler import should_start_scheduler
from app.scheduler_jobs import scheduled_telemetry_sync
from app.supabase_client import supabase


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


def test_should_start_scheduler_disabled_during_pytest():
    assert os.environ.get("PYTEST_CURRENT_TEST")
    class _App:
        config = {}
        debug = False
    assert should_start_scheduler(_App()) is False


def test_should_start_scheduler_honors_env_flag(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ENABLE_TELEMETRY_SCHEDULER", "false")
    class _App:
        config = {"TESTING": False}
        debug = False
    assert should_start_scheduler(_App()) is False

    monkeypatch.setenv("ENABLE_TELEMETRY_SCHEDULER", "true")
    assert should_start_scheduler(_App()) is True


def test_scheduled_telemetry_sync_calls_incremental_garmin_mode():
    supabase.table("users").upsert({
        "id": 7,
        "username": "scheduler_athlete",
        "garmin_email": "athlete@example.com",
        "garmin_password": "encrypted_test_pass",
        "garmin_sync_status": "synced",
    }, on_conflict="id").execute()

    with patch("app.scheduler_jobs.sync_all_garmin_data_for_user") as mock_sync, \
         patch("app.scheduler_jobs.AnalyticsService.calculate_baselines"):
        scheduled_telemetry_sync()

    assert mock_sync.called
    kwargs_list = [c.kwargs for c in mock_sync.call_args_list]
    assert any(k.get("mode") == "incremental" for k in kwargs_list)
    assert any(k.get("days_back") == 7 for k in kwargs_list)


def test_scheduled_telemetry_sync_skips_users_already_syncing():
    supabase.table("users").upsert({
        "id": 8,
        "username": "already_syncing",
        "garmin_email": "busy@example.com",
        "garmin_password": "encrypted_test_pass",
        "garmin_sync_status": "syncing",
    }, on_conflict="id").execute()

    with patch("app.scheduler_jobs.sync_all_garmin_data_for_user") as mock_sync:
        scheduled_telemetry_sync()

    synced_ids = [c.args[0] for c in mock_sync.call_args_list]
    assert "8" not in synced_ids and 8 not in synced_ids


def test_sync_if_needed_uses_incremental_after_first_sync(monkeypatch, app):
    captured = {}

    def fake_sync(uid, days_back=365, encryption_key=None, force_resync=False, mode="all_time"):
        captured["uid"] = uid
        captured["days_back"] = days_back
        captured["mode"] = mode

    monkeypatch.setattr("app.garmin.routes.sync_all_garmin_data_for_user", fake_sync)
    monkeypatch.setattr("threading.Thread", ImmediateThread)

    supabase.table("users").upsert({
        "id": 1,
        "username": "athlete_sync_test",
        "garmin_email": "athlete@example.com",
        "garmin_password": "encrypted_test_pass",
        "garmin_sync_status": "synced",
        "garmin_sync_completed_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }, on_conflict="id").execute()

    with app.app_context():
        triggered = sync_if_needed("1", debounce_minutes=15)

    assert triggered is True
    assert captured["mode"] == "incremental"
    assert captured["days_back"] == 7


def test_sync_if_needed_uses_all_time_for_first_sync(monkeypatch, app):
    captured = {}

    def fake_sync(uid, days_back=365, encryption_key=None, force_resync=False, mode="all_time"):
        captured["mode"] = mode
        captured["days_back"] = days_back

    monkeypatch.setattr("app.garmin.routes.sync_all_garmin_data_for_user", fake_sync)
    monkeypatch.setattr("threading.Thread", ImmediateThread)

    supabase.table("users").upsert({
        "id": 11,
        "username": "first_sync_user",
        "garmin_email": "new@example.com",
        "garmin_password": "encrypted_test_pass",
        "garmin_sync_status": None,
        "garmin_sync_completed_at": None,
    }, on_conflict="id").execute()

    with app.app_context():
        triggered = sync_if_needed("11", debounce_minutes=15)

    assert triggered is True
    assert captured["mode"] == "all_time"
    assert captured["days_back"] == 365


def test_internal_telemetry_sync_endpoint_requires_token(client, monkeypatch):
    monkeypatch.delenv("INTERNAL_JOB_TOKEN", raising=False)
    res = client.post("/internal/jobs/telemetry-sync")
    assert res.status_code == 503
    assert res.json["status"] == "disabled"


def test_internal_telemetry_sync_endpoint_runs_with_token(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "test-job-token")
    with patch("app.scheduler_jobs.scheduled_telemetry_sync") as mock_job:
        res = client.post(
            "/internal/jobs/telemetry-sync",
            headers={"X-Internal-Job-Token": "test-job-token"},
        )
    assert res.status_code == 200
    assert res.json["status"] == "ok"
    mock_job.assert_called_once()


def test_internal_telemetry_sync_endpoint_rejects_bad_token(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "test-job-token")
    res = client.post(
        "/internal/jobs/telemetry-sync",
        headers={"X-Internal-Job-Token": "wrong"},
    )
    assert res.status_code == 401
