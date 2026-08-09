"""
Activity & Wellness Query Tools.
Exposes database query helpers for the LLM agent to retrieve recent workouts, runs,
heart rate metrics, and wellness data.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from app.supabase_client import supabase

logger = logging.getLogger(__name__)


def get_recent_activities(user_id: str, days: int = 14, activity_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves recent workout activities (runs, rides, swims, strength sessions) for a user.

    Args:
        user_id: The ID of the user.
        days: Lookback window in days (default 14).
        activity_type: Optional filter (e.g., 'run', 'cycling', 'swimming', 'strength').

    Returns:
        Dict containing status, activity count, total distance (km), total duration (min), and detailed activity list.
    """
    try:
        # Determine date cut-off
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = supabase.table("activities").select("*").eq("user_id", user_id).gte("start_date", cutoff_date)
        if activity_type:
            query = query.ilike("type", f"%{activity_type}%")
            
        res = query.order("start_date", desc=True).execute()
        activities = res.data if res.data else []
        
        # Calculate summary metrics
        total_distance = sum(act.get("distance_km") or act.get("distance", 0) / 1000.0 for act in activities)
        total_duration = sum(act.get("moving_time_min") or act.get("duration_min") or act.get("elapsed_time", 0) / 60.0 for act in activities)
        
        formatted_activities = []
        for act in activities:
            dist_km = round(act.get("distance_km") or (act.get("distance", 0) / 1000.0), 2)
            dur_min = round(act.get("moving_time_min") or act.get("duration_min") or (act.get("elapsed_time", 0) / 60.0), 1)
            pace_str = act.get("average_pace") or (f"{round(dur_min / dist_km, 2)} min/km" if dist_km > 0 else "N/A")
            
            formatted_activities.append({
                "id": act.get("id"),
                "name": act.get("name") or act.get("title") or "Workout",
                "type": act.get("type") or "run",
                "date": act.get("start_date") or act.get("date"),
                "distance_km": dist_km,
                "duration_min": dur_min,
                "average_pace": pace_str,
                "average_hr": act.get("average_heartrate") or act.get("avg_hr"),
                "max_hr": act.get("max_heartrate") or act.get("max_hr"),
                "elevation_gain_m": act.get("total_elevation_gain") or act.get("elevation_m")
            })

        return {
            "status": "success",
            "count": len(formatted_activities),
            "period_days": days,
            "summary": {
                "total_distance_km": round(total_distance, 2),
                "total_duration_min": round(total_duration, 1),
                "activity_count": len(formatted_activities)
            },
            "activities": formatted_activities
        }
    except Exception as e:
        logger.error(f"Error retrieving activities for user {user_id}: {e}")
        return {"status": "error", "message": str(e), "activities": []}


def get_wellness_metrics(user_id: str, days: int = 14) -> Dict[str, Any]:
    """
    Retrieves health wellness metrics (sleep, HRV, resting heart rate, stress, body battery).

    Args:
        user_id: The ID of the user.
        days: Lookback window in days (default 14).

    Returns:
        Dict containing average sleep score, average HRV, resting HR trends, and raw journal/health records.
    """
    try:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        # Query daily journal & health hub metrics
        journal_res = supabase.table("journal_entries").select("*").eq("user_id", user_id).gte("created_at", cutoff_date).execute()
        entries = journal_res.data if journal_res.data else []
        
        sleep_scores = [e.get("sleep_quality") for e in entries if e.get("sleep_quality") is not None]
        hrv_values = [e.get("hrv") for e in entries if e.get("hrv") is not None]
        rhr_values = [e.get("resting_hr") for e in entries if e.get("resting_hr") is not None]
        
        avg_sleep = round(sum(sleep_scores) / len(sleep_scores), 1) if sleep_scores else None
        avg_hrv = round(sum(hrv_values) / len(hrv_values), 1) if hrv_values else None
        avg_rhr = round(sum(rhr_values) / len(rhr_values), 1) if rhr_values else None

        return {
            "status": "success",
            "period_days": days,
            "averages": {
                "sleep_score": avg_sleep,
                "hrv_ms": avg_hrv,
                "resting_hr_bpm": avg_rhr
            },
            "records_count": len(entries)
        }
    except Exception as e:
        logger.error(f"Error fetching wellness metrics for user {user_id}: {e}")
        return {"status": "error", "message": str(e)}
