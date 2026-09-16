"""
Activity & Wellness Query Tools.
Exposes database query helpers for the LLM agent and MCP adapter to retrieve
recent workouts and daily wellness metrics.

Reads Garmin-canonical tables (via get_unified_activities / biometrics_daily).
Does not invent athlete data when the window is empty.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from app.supabase_client import supabase
from app.health_hub.ingestion_service import get_unified_activities

logger = logging.getLogger(__name__)


def _as_km(raw_dist) -> float:
    try:
        value = float(raw_dist or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(value / 1000.0, 2) if value > 100 else round(value, 2)


def _as_minutes(raw_dur) -> float:
    try:
        value = float(raw_dur or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(value / 60.0, 1) if value > 300 else round(value, 1)


def _avg(values: List[Any]) -> Optional[float]:
    nums = []
    for v in values:
        if v is None:
            continue
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


def get_recent_activities(user_id: str, days: int = 14, activity_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves recent workout activities (runs, rides, swims, strength sessions) for a user.

    Garmin-first: uses get_unified_activities() which reads garmin_activities,
    then Strava, then generic/manual `activities`. MCP previously queried only
    `activities.start_date`, so Garmin rows were invisible.

    Args:
        user_id: The ID of the user (server-bound; never invent one).
        days: Lookback window in days (default 14).
        activity_type: Optional filter (e.g., 'run', 'cycling', 'swimming', 'strength').

    Returns:
        Dict containing status, activity count, total distance (km), total duration (min), and detailed activity list.
    """
    try:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        unified = get_unified_activities(
            user_id,
            start_date=cutoff_date,
            activity_type=activity_type,
            limit=200,
        )

        formatted_activities = []
        total_distance = 0.0
        total_duration = 0.0
        for act in unified:
            dist_km = _as_km(act.get("distance_km") if act.get("distance_km") is not None else act.get("distance"))
            dur_min = _as_minutes(
                act.get("moving_time_min")
                or act.get("duration_min")
                or act.get("duration")
            )
            pace_str = act.get("average_pace") or (
                f"{round(dur_min / dist_km, 2)} min/km" if dist_km > 0 else "N/A"
            )
            formatted_activities.append({
                "id": act.get("activity_id") or act.get("id"),
                "name": act.get("name") or act.get("activity_name") or act.get("title") or "Workout",
                "type": act.get("activity_type") or act.get("type") or "workout",
                "date": act.get("start_time_local") or act.get("start_time") or act.get("start_date"),
                "distance_km": dist_km,
                "duration_min": dur_min,
                "average_pace": pace_str,
                "average_hr": act.get("average_hr") or act.get("average_heartrate") or act.get("avg_hr"),
                "max_hr": act.get("max_hr") or act.get("max_heartrate"),
                "elevation_gain_m": act.get("elevation_gain") or act.get("total_elevation_gain") or act.get("elevation_m"),
                "source": act.get("source"),
            })
            total_distance += dist_km
            total_duration += dur_min

        return {
            "status": "success",
            "count": len(formatted_activities),
            "period_days": days,
            "summary": {
                "total_distance_km": round(total_distance, 2),
                "total_duration_min": round(total_duration, 1),
                "activity_count": len(formatted_activities),
            },
            "activities": formatted_activities,
        }
    except Exception as e:
        logger.error(f"Error retrieving activities for user {user_id}: {e}")
        return {"status": "error", "message": str(e), "activities": []}


def get_wellness_metrics(user_id: str, days: int = 14) -> Dict[str, Any]:
    """
    Retrieves health wellness metrics (sleep, HRV, resting heart rate, stress, body battery).

    Canonical source is biometrics_daily (Garmin sync writes sleep/HRV/RHR here).
    Does not query the nonexistent `journal_entries` table (journals live in daily_journals).

    Args:
        user_id: The ID of the user (server-bound; never invent one).
        days: Lookback window in days (default 14).

    Returns:
        Dict containing averages, records_count, and compact daily records. Empty windows stay empty.
    """
    try:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        uid = int(user_id) if str(user_id).isdigit() else user_id

        records: List[Dict[str, Any]] = []
        if supabase:
            bio_res = (
                supabase.table("biometrics_daily")
                .select("*")
                .eq("user_id", uid)
                .gte("date", cutoff_date)
                .order("date", desc=True)
                .execute()
            )
            records = bio_res.data or []

        sleep_scores = [r.get("sleep_score") for r in records]
        hrv_values = [r.get("hrv") if r.get("hrv") is not None else r.get("hrv_ms") for r in records]
        rhr_values = [r.get("resting_hr") for r in records]

        compact = []
        for r in records:
            compact.append({
                "date": r.get("date"),
                "sleep_score": r.get("sleep_score"),
                "sleep_hours": r.get("sleep_hours"),
                "hrv_ms": r.get("hrv") if r.get("hrv") is not None else r.get("hrv_ms"),
                "hrv_status": r.get("hrv_status"),
                "resting_hr_bpm": r.get("resting_hr"),
                "stress_level": r.get("stress_level"),
                "body_battery": r.get("body_battery"),
                "source": r.get("source") or r.get("raw_source"),
            })

        return {
            "status": "success",
            "period_days": days,
            "averages": {
                "sleep_score": _avg(sleep_scores),
                "hrv_ms": _avg(hrv_values),
                "resting_hr_bpm": _avg(rhr_values),
            },
            "records_count": len(records),
            "records": compact,
        }
    except Exception as e:
        logger.error(f"Error fetching wellness metrics for user {user_id}: {e}")
        return {"status": "error", "message": str(e), "records_count": 0, "records": []}
