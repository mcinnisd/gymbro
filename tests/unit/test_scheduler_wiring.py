import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.garmin.routes import sync_if_needed
from app.scheduler import should_start_scheduler
from app.scheduler_jobs import scheduled_telemetry_sync
from app.supabase_client import supabase


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args, self._kwargs = args, kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


def _garmin_user(uid, email, status="synced"):
    supabase.table("users").upsert({
        "id": uid, "username": f"u{uid}", "garmin_email": email, "garmin_password": "encrypted_test_pass",
        "garmin_sync_status": status,
    }, on_conflict="id").execute()


def test_scheduler_starts_only_when_enabled(app, monkeypatch):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/mcp" in rules and "/internal/jobs/telemetry-sync" in rules
    bare = type("App", (), {"config": {"TESTING": False}, "debug": False})()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ENABLE_TELEMETRY_SCHEDULER", "false")
    assert should_start_scheduler(bare) is False
    monkeypatch.setenv("ENABLE_TELEMETRY_SCHEDULER", "true")
    assert should_start_scheduler(bare) is True


def test_scheduled_sync_is_incremental_and_respects_scope(monkeypatch):
    _garmin_user(7, "athlete@example.com")
    with patch("app.scheduler_jobs.sync_all_garmin_data_for_user") as mock_sync, \
         patch("app.scheduler_jobs.AnalyticsService.calculate_baselines"):
        scheduled_telemetry_sync()
    assert any(c.kwargs.get("mode") == "incremental" and c.kwargs.get("days_back") == 7 for c in mock_sync.call_args_list)

    monkeypatch.setenv("GYMBRO_GARMIN_SYNC_USER_IDS", "7")
    _garmin_user(100, "other@example.com")
    with patch("app.scheduler_jobs.sync_all_garmin_data_for_user") as mock_sync, \
         patch("app.scheduler_jobs.AnalyticsService.calculate_baselines"):
        scheduled_telemetry_sync()
    ids = [str(c.args[0]) for c in mock_sync.call_args_list]
    assert "7" in ids and "100" not in ids

    monkeypatch.delenv("GYMBRO_GARMIN_SYNC_USER_IDS", raising=False)
    original = list(supabase.data.get("users") or [])
    supabase.data["users"] = [
        {"id": 2, "username": "canonical", "garmin_email": "shared@example.com", "garmin_password": "x", "garmin_sync_status": "synced"},
        {"id": 100, "username": "dup", "garmin_email": "shared@example.com", "garmin_password": "x", "garmin_sync_status": "synced"},
    ]
    try:
        with patch("app.scheduler_jobs.sync_all_garmin_data_for_user") as mock_sync, \
             patch("app.scheduler_jobs.AnalyticsService.calculate_baselines"):
            scheduled_telemetry_sync()
        assert [str(c.args[0]) for c in mock_sync.call_args_list] == ["2"]
    finally:
        supabase.data["users"] = original

    _garmin_user(8, "busy@example.com", status="syncing")
    with patch("app.scheduler_jobs.sync_all_garmin_data_for_user") as mock_sync:
        scheduled_telemetry_sync()
    assert all(c.args[0] not in (8, "8") for c in mock_sync.call_args_list)


@pytest.mark.parametrize("completed,mode,days", [
    (True, "incremental", 7),
    (False, "all_time", 365),
])
def test_sync_if_needed_chooses_window_from_prior_sync(monkeypatch, app, completed, mode, days):
    captured = {}
    monkeypatch.setattr("app.garmin.routes.sync_all_garmin_data_for_user", lambda *a, **k: captured.update(k))
    monkeypatch.setattr("threading.Thread", ImmediateThread)
    uid = 1 if completed else 11
    supabase.table("users").upsert({
        "id": uid, "username": f"s{uid}", "garmin_email": f"s{uid}@example.com", "garmin_password": "x",
        "garmin_sync_status": "synced" if completed else None,
        "garmin_sync_completed_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() if completed else None,
    }, on_conflict="id").execute()
    with app.app_context():
        assert sync_if_needed(str(uid), debounce_minutes=15) is True
    assert captured["mode"] == mode and captured["days_back"] == days


@pytest.mark.parametrize("token,header,status", [
    (None, None, 503),
    ("test-job-token", "wrong", 401),
    ("test-job-token", "test-job-token", 200),
])
def test_internal_job_token(client, monkeypatch, token, header, status):
    if token:
        monkeypatch.setenv("INTERNAL_JOB_TOKEN", token)
    else:
        monkeypatch.delenv("INTERNAL_JOB_TOKEN", raising=False)
    headers = {"X-Internal-Job-Token": header} if header else {}
    with patch("app.scheduler_jobs.scheduled_telemetry_sync"):
        res = client.post("/internal/jobs/telemetry-sync", headers=headers)
    assert res.status_code == status
