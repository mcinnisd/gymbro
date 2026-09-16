from datetime import datetime, timezone

import pytest

from app.calendar.constraints import (
    TRAINING_EVENT_CREATED_BY_ALLOWED,
    assert_training_event_row,
    calendar_event_from_garmin_activity,
    is_undefined_column_error,
    map_activity_type_to_event_type,
    parse_garmin_activity_id_from_row,
    strip_metrics_column,
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
        "activity_id": "act-123",
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
    assert event["metrics"]["garmin_activity_id"] == "act-123"
    assert "[garmin_activity_id=act-123]" in event["description"]
    assert_training_event_row(event)
    assert_training_event_row(strip_metrics_column(event))


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


def test_remirror_garmin_calendar_from_existing_activities_is_idempotent():
    from app.garmin.sync import remirror_garmin_calendar

    supabase.table("training_events").data["training_events"] = []
    supabase.table("garmin_activities").data["garmin_activities"] = []
    supabase.table("garmin_activities").insert({
        "user_id": 2,
        "activity_id": "garmin_remirror_1",
        "activity_name": "Remirror Easy Run",
        "start_time_local": datetime.now(timezone.utc).isoformat(),
        "distance": 5000.0,
        "duration": 1500.0,
        "average_hr": 138,
        "activity_type": "running",
    }).execute()

    first = remirror_garmin_calendar("2")
    assert first["source"] >= 1
    assert first["inserted"] >= 1
    rows = supabase.table("training_events").select("*").eq("user_id", 2).eq("created_by", "garmin").execute().data
    assert any(r["title"] == "Remirror Easy Run" for r in rows)

    second = remirror_garmin_calendar("2")
    assert second["source"] >= 1
    assert second["inserted"] == 0
    assert second["skipped"] >= 1
    again = supabase.table("training_events").select("*").eq("user_id", 2).eq("created_by", "garmin").execute().data
    titles = [r["title"] for r in again if r["title"] == "Remirror Easy Run"]
    assert len(titles) == 1


def test_undefined_column_error_detects_postgres_42703():
    class ApiError(Exception):
        code = "42703"

    assert is_undefined_column_error(
        ApiError('column training_events.metrics does not exist')
    )
    assert is_undefined_column_error(
        ValueError("column training_events.metrics does not exist")
    )
    assert not is_undefined_column_error(ValueError("unrelated"))


def test_parse_garmin_activity_id_from_description_without_metrics():
    aid = parse_garmin_activity_id_from_row({
        "date": "2026-09-15",
        "title": "Easy Run",
        "description": "Distance: 5.0km, Duration: 25.0min, Avg HR: 138 bpm [garmin_activity_id=abc-9]",
    })
    assert aid == "abc-9"


def test_metrics_migration_sql_adds_jsonb_column():
    from pathlib import Path
    sql = Path("migrations/20260916_training_events_metrics.sql").read_text()
    assert "ADD COLUMN IF NOT EXISTS metrics" in sql
    assert "JSONB" in sql.upper()


def test_remirror_succeeds_when_metrics_column_missing():
    """Live 42703: match schema without metrics; stay idempotent via description."""
    from app.garmin.sync import remirror_garmin_calendar, reset_training_events_metrics_column_cache

    reset_training_events_metrics_column_cache(None)
    supabase.missing_columns["training_events"] = {"metrics"}
    supabase.table("training_events").data["training_events"] = []
    supabase.table("garmin_activities").data["garmin_activities"] = []
    try:
        supabase.table("garmin_activities").insert({
            "user_id": 2,
            "activity_id": "garmin_live_schema_1",
            "activity_name": "Live Schema Run",
            "start_time_local": datetime.now(timezone.utc).isoformat(),
            "distance": 5000.0,
            "duration": 1500.0,
            "average_hr": 138,
            "activity_type": "running",
        }).execute()

        first = remirror_garmin_calendar("2")
        assert first.get("error") is None
        assert first["source"] >= 1
        assert first["inserted"] >= 1
        rows = supabase.table("training_events").select("*").eq("user_id", 2).eq("created_by", "garmin").execute().data
        mirrored = [r for r in rows if r.get("title") == "Live Schema Run"]
        assert len(mirrored) == 1
        assert "metrics" not in mirrored[0]
        assert "[garmin_activity_id=garmin_live_schema_1]" in (mirrored[0].get("description") or "")

        second = remirror_garmin_calendar("2")
        assert second.get("error") is None
        assert second["inserted"] == 0
        assert second["skipped"] >= 1
        again = supabase.table("training_events").select("*").eq("user_id", 2).eq("created_by", "garmin").execute().data
        assert len([r for r in again if r.get("title") == "Live Schema Run"]) == 1
    finally:
        supabase.missing_columns.pop("training_events", None)
        reset_training_events_metrics_column_cache(None)


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
