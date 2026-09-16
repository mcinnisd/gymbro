# app/calendar/constraints.py
"""
Canonical training_events CHECK values.

Postgres constraint names:
  training_events_created_by_check
  training_events_event_type_check
  training_events_status_check
"""
from __future__ import annotations

from typing import Any, Dict, Optional

TRAINING_EVENT_CREATED_BY_ALLOWED = ("user", "coach", "agent", "garmin", "strava")
TRAINING_EVENT_TYPES_ALLOWED = ("run", "strength", "rest", "race", "cross_train", "other")
TRAINING_EVENT_STATUS_ALLOWED = ("planned", "completed", "skipped")

_ACTIVITY_TYPE_TO_EVENT_TYPE = (
    ("strength", "strength"),
    ("weight", "strength"),
    ("gym", "strength"),
    ("race", "race"),
    ("rest", "rest"),
    ("run", "run"),
    ("cycling", "cross_train"),
    ("cycle", "cross_train"),
    ("bik", "cross_train"),
    ("swim", "cross_train"),
    ("walk", "cross_train"),
    ("hik", "cross_train"),
    ("row", "cross_train"),
    ("yoga", "cross_train"),
    ("cardio", "cross_train"),
    ("elliptical", "cross_train"),
)


def map_activity_type_to_event_type(activity_type: Optional[str]) -> str:
    """Map Garmin/Strava activity_type strings onto training_events.event_type."""
    raw = str(activity_type or "other").strip().lower()
    if raw in TRAINING_EVENT_TYPES_ALLOWED:
        return raw
    for needle, mapped in _ACTIVITY_TYPE_TO_EVENT_TYPE:
        if needle in raw:
            return mapped
    return "other"


def calendar_event_from_garmin_activity(user_id: Any, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build a training_events row for a Garmin activity. Returns None if undated."""
    from datetime import datetime, timezone

    act_date = str(doc.get("start_time_local") or doc.get("start_time") or "")[:10]
    if not act_date:
        return None
    raw_dist = doc.get("distance") or 0
    dist_km = round(raw_dist / 1000, 2) if raw_dist > 100 else round(raw_dist, 2)
    raw_dur = doc.get("duration") or 0
    dur_min = round(raw_dur / 60, 1) if raw_dur > 300 else round(raw_dur, 1)
    uid = int(user_id) if str(user_id).isdigit() else user_id
    activity_id = doc.get("activity_id") or doc.get("id")
    return {
        "user_id": uid,
        "date": act_date,
        "title": doc.get("activity_name") or doc.get("name") or "Garmin Workout",
        "description": f"Distance: {dist_km}km, Duration: {dur_min}min, Avg HR: {doc.get('average_hr', 'N/A')} bpm",
        "event_type": map_activity_type_to_event_type(doc.get("activity_type")),
        "status": "completed",
        "created_by": "garmin",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {"garmin_activity_id": str(activity_id)} if activity_id not in (None, "") else {},
    }


def assert_training_event_row(row: Dict[str, Any]) -> None:
    """Raise a Postgres-like check violation if the row would fail on training_events."""
    created_by = row.get("created_by", "user")
    if created_by not in TRAINING_EVENT_CREATED_BY_ALLOWED:
        raise ValueError(
            'new row for relation "training_events" violates check constraint '
            '"training_events_created_by_check"'
        )
    event_type = row.get("event_type")
    if event_type not in TRAINING_EVENT_TYPES_ALLOWED:
        raise ValueError(
            'new row for relation "training_events" violates check constraint '
            '"training_events_event_type_check"'
        )
    status = row.get("status", "planned")
    if status not in TRAINING_EVENT_STATUS_ALLOWED:
        raise ValueError(
            'new row for relation "training_events" violates check constraint '
            '"training_events_status_check"'
        )
