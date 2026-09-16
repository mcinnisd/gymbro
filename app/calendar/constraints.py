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
import json
import re

TRAINING_EVENT_CREATED_BY_ALLOWED = ("user", "coach", "agent", "garmin", "strava")
TRAINING_EVENT_TYPES_ALLOWED = ("run", "strength", "rest", "race", "cross_train", "other")
TRAINING_EVENT_STATUS_ALLOWED = ("planned", "completed", "skipped")

# Live Postgres may not yet have training_events.metrics (42703). Persist the
# Garmin activity id in description so remirror stays idempotent either way.
GARMIN_ACTIVITY_ID_MARKER = "garmin_activity_id="
_GARMIN_ACTIVITY_ID_RE = re.compile(r"\[garmin_activity_id=([^\]]+)\]")

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


def garmin_activity_id_from_doc(doc: Dict[str, Any]) -> Optional[str]:
    raw = doc.get("activity_id") or doc.get("id")
    if raw in (None, ""):
        return None
    return str(raw)


def parse_garmin_activity_id_from_row(row: Dict[str, Any]) -> Optional[str]:
    """Read garmin activity id from metrics jsonb or description marker."""
    metrics = row.get("metrics") or {}
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except Exception:
            metrics = {}
    if isinstance(metrics, dict):
        aid = metrics.get("garmin_activity_id")
        if aid not in (None, ""):
            return str(aid)
    desc = str(row.get("description") or "")
    match = _GARMIN_ACTIVITY_ID_RE.search(desc)
    if match:
        return match.group(1)
    return None


def strip_metrics_column(row: Dict[str, Any]) -> Dict[str, Any]:
    """Drop metrics so the payload matches live tables that lack the column."""
    return {k: v for k, v in row.items() if k != "metrics"}


def is_undefined_column_error(exc: BaseException, column: str = "metrics") -> bool:
    text = str(exc)
    code = str(getattr(exc, "code", "") or "")
    if code == "42703":
        return True
    lowered = text.lower()
    return column in lowered and ("does not exist" in lowered or "42703" in lowered)


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
    activity_id = garmin_activity_id_from_doc(doc)
    description = (
        f"Distance: {dist_km}km, Duration: {dur_min}min, Avg HR: {doc.get('average_hr', 'N/A')} bpm"
    )
    if activity_id:
        description = f"{description} [{GARMIN_ACTIVITY_ID_MARKER}{activity_id}]"
    row = {
        "user_id": uid,
        "date": act_date,
        "title": doc.get("activity_name") or doc.get("name") or "Garmin Workout",
        "description": description,
        "event_type": map_activity_type_to_event_type(doc.get("activity_type")),
        "status": "completed",
        "created_by": "garmin",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if activity_id:
        row["metrics"] = {"garmin_activity_id": activity_id}
    return row


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
