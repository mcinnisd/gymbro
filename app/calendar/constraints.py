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
# Writers emit this closed set. Unknown Garmin typeKeys map to "other" rather
# than growing the enum (cross_train/ride/swim/walk/hike stay CHECK-only).
TRAINING_EVENT_TYPES_WRITTEN = ("run", "strength", "rest", "race", "other")
TRAINING_EVENT_TYPES_ALLOWED = TRAINING_EVENT_TYPES_WRITTEN
# Live Postgres CHECK (widened 2026-09-16). assert_training_event_row accepts
# this set; Garmin remirror still writes TRAINING_EVENT_TYPES_WRITTEN only.
TRAINING_EVENT_TYPES_CHECK = (
    "run",
    "strength",
    "rest",
    "race",
    "other",
    "cross_train",
    "ride",
    "swim",
    "walk",
    "hike",
)
TRAINING_EVENT_STATUS_ALLOWED = ("planned", "completed", "skipped")

# Live Postgres may not yet have training_events.metrics (42703). Persist the
# Garmin activity id in description so remirror stays idempotent either way.
GARMIN_ACTIVITY_ID_MARKER = "garmin_activity_id="
_GARMIN_ACTIVITY_ID_RE = re.compile(r"\[garmin_activity_id=([^\]]+)\]")

_EXACT_ACTIVITY_TYPE_TO_EVENT_TYPE = {
    "run": "run",
    "running": "run",
    "trail_running": "run",
    "treadmill_running": "run",
    "track_running": "run",
    "virtual_run": "run",
    "strength": "strength",
    "strength_training": "strength",
    "weight_training": "strength",
    "workout": "other",
    "rest": "rest",
    "race": "race",
    "hiking": "other",
    "hike": "other",
    "walking": "other",
    "walk": "other",
    "cycling": "other",
    "indoor_cycling": "other",
    "mountain_biking": "other",
    "road_biking": "other",
    "ride": "other",
    "bike": "other",
    "biking": "other",
    "swimming": "other",
    "lap_swimming": "other",
    "open_water_swimming": "other",
    "swim": "other",
    "yoga": "other",
    "cardio": "other",
    "elliptical": "other",
    "resort_snowboarding": "other",
    "snowboarding": "other",
    "resort_skiing": "other",
    "skiing": "other",
    "cross_country_skiing": "other",
    "cross_train": "other",
}

_ACTIVITY_TYPE_TO_EVENT_TYPE = (
    ("strength", "strength"),
    ("weight", "strength"),
    ("gym", "strength"),
    ("race", "race"),
    ("rest", "rest"),
    ("running", "run"),
    ("run", "run"),
)


def map_activity_type_to_event_type(activity_type: Optional[str]) -> str:
    """Map Garmin/Strava activity_type strings onto written calendar types.

    Live CHECK also allows cross_train/ride/swim/walk/hike (onboarding / widened
    live enum). Do not passthrough those: unknown Garmin types become `other`.
    """
    raw = str(activity_type or "other").strip().lower().replace(" ", "_").replace("-", "_")
    if raw in TRAINING_EVENT_TYPES_WRITTEN:
        return raw
    if raw in _EXACT_ACTIVITY_TYPE_TO_EVENT_TYPE:
        mapped = _EXACT_ACTIVITY_TYPE_TO_EVENT_TYPE[raw]
    else:
        mapped = "other"
        for needle, mapped_type in _ACTIVITY_TYPE_TO_EVENT_TYPE:
            if needle in raw:
                mapped = mapped_type
                break
    if mapped not in TRAINING_EVENT_TYPES_WRITTEN:
        return "other"
    return mapped


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
    row["event_type"] = map_activity_type_to_event_type(row["event_type"])
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
    if event_type not in TRAINING_EVENT_TYPES_CHECK:
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
