from datetime import datetime, timezone

import pytest

from app.calendar.constraints import (
    TRAINING_EVENT_CREATED_BY_ALLOWED,
    assert_training_event_row,
    calendar_event_from_garmin_activity,
    map_activity_type_to_event_type,
)
from app.garmin.sync import _sync_activities_to_calendar
from app.supabase_client import supabase


def test_created_by_allowlist_includes_garmin():
    assert "garmin" in TRAINING_EVENT_CREATED_BY_ALLOWED
    assert "user" in TRAINING_EVENT_CREATED_BY_ALLOWED


def test_garmin_created_by_passes_training_events_check():
    row = {
        "user_id": 2,
        "date": "2026-09-15",
        "title": "Santa Monica Running",
        "event_type": "run",
        "status": "completed",
        "created_by": "garmin",
    }
    assert_training_event_row(row)


def test_legacy_garmin_created_by_would_fail_without_allowlist():
    """Documents the live Postgres error before the migration."""
    row = {
        "user_id": 2,
        "date": "2026-09-15",
        "title": "Santa Monica Running",
        "event_type": "run",
        "status": "completed",
        "created_by": "garmin",
    }
    legacy_allowed = ("user", "coach", "agent")
    assert row["created_by"] not in legacy_allowed
    assert row["created_by"] in TRAINING_EVENT_CREATED_BY_ALLOWED


def test_unknown_created_by_still_rejected():
    with pytest.raises(ValueError, match="training_events_created_by_check"):
        assert_training_event_row({
            "user_id": 2,
            "date": "2026-09-15",
            "title": "Nope",
            "event_type": "run",
            "status": "completed",
            "created_by": "not-a-source",
        })


def test_map_garmin_running_to_calendar_run():
    assert map_activity_type_to_event_type("running") == "run"
    assert map_activity_type_to_event_type("trail_running") == "run"
    assert map_activity_type_to_event_type("cycling") == "cross_train"
    assert map_activity_type_to_event_type("strength_training") == "strength"
    assert map_activity_type_to_event_type("workout") == "other"


def test_calendar_event_from_garmin_activity_is_constraint_safe():
    event = calendar_event_from_garmin_activity(2, {
        "activity_name": "Santa Monica Running",
        "start_time_local": "2026-09-15T06:12:00",
        "distance": 8000.0,
        "duration": 2400.0,
        "average_hr": 148,
        "activity_type": "running",
    })
    assert event is not None
    assert event["created_by"] == "garmin"
    assert event["event_type"] == "run"
    assert event["status"] == "completed"
    assert event["title"] == "Santa Monica Running"
    assert event["user_id"] == 2
    assert_training_event_row(event)


def test_garmin_calendar_mirror_upserts_training_events():
    supabase.table("training_events").data["training_events"] = []
    _sync_activities_to_calendar("2", [{
        "activity_name": "Santa Monica Running",
        "start_time_local": datetime.now(timezone.utc).isoformat(),
        "distance": 5000.0,
        "duration": 1500.0,
        "average_hr": 140,
        "activity_type": "running",
    }])
    rows = supabase.table("training_events").select("*").eq("user_id", 2).execute().data
    assert len(rows) >= 1
    assert any(r["created_by"] == "garmin" and r["title"] == "Santa Monica Running" for r in rows)
    assert all(r["event_type"] == "run" for r in rows if r.get("title") == "Santa Monica Running")


def test_mock_supabase_rejects_invalid_created_by_like_postgres():
    with pytest.raises(ValueError, match="training_events_created_by_check"):
        supabase.table("training_events").insert({
            "user_id": 2,
            "date": "2026-09-15",
            "title": "Should fail",
            "event_type": "run",
            "status": "completed",
            "created_by": "legacy-device",
        }).execute()
