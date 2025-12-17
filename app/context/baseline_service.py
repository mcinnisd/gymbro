"""
Baseline Service for Contextual Chat Intelligence

Computes user-specific baselines and averages for fitness metrics.
These baselines are used to compare current data against personal norms.
Supports caching to user_baselines table for fast retrieval.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from app.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

# Cache expiry time in hours
CACHE_EXPIRY_HOURS = 24


def get_user_baselines(user_id: str, activity_type: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
    """
    Get user baselines, preferring cached values if recent.
    
    Args:
        user_id: The user's ID
        activity_type: Optional filter for activity-specific baselines
        use_cache: Whether to use cached baselines (default: True)
        
    Returns:
        Dictionary with baseline values for various metrics
    """
    if use_cache:
        cached = get_cached_baselines(user_id)
        if cached:
            logger.debug(f"Using cached baselines for user {user_id}")
            return cached
    
    # Compute fresh baselines
    baselines = {
        "running": get_running_baselines(user_id),
        "health": get_health_baselines(user_id),
        "training_load": get_training_load(user_id)
    }
    
    return baselines


def get_cached_baselines(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached baselines if they exist and are fresh.
    """
    try:
        result = supabase.table("user_baselines")\
            .select("metric_category, baselines, computed_at")\
            .eq("user_id", user_id)\
            .execute()
        
        if not result.data:
            return None
        
        # Check freshness - use first row's computed_at
        computed_at = result.data[0].get("computed_at")
        if computed_at:
            # Parse ISO timestamp
            if isinstance(computed_at, str):
                computed_time = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
            else:
                computed_time = computed_at
            
            age_hours = (datetime.now(timezone.utc) - computed_time).total_seconds() / 3600
            if age_hours > CACHE_EXPIRY_HOURS:
                logger.debug(f"Cache expired for user {user_id} ({age_hours:.1f}h old)")
                return None
        
        # Build baselines dict from cached rows
        baselines = {}
        for row in result.data:
            category = row.get("metric_category")
            if category:
                baselines[category] = row.get("baselines", {})
        
        return baselines if baselines else None
        
    except Exception as e:
        logger.warning(f"Error reading baseline cache: {e}")
        return None


def refresh_user_baselines(user_id: str) -> Dict[str, Any]:
    """
    Compute fresh baselines and save to cache.
    Called on login or when cache expires.
    
    Args:
        user_id: The user's ID
        
    Returns:
        Dictionary with fresh baseline values
    """
    logger.info(f"Refreshing baselines for user {user_id}")
    
    baselines = {
        "running": get_running_baselines(user_id),
        "health": get_health_baselines(user_id),
        "training_load": get_training_load(user_id)
    }
    
    # Save to cache
    try:
        for category, data in baselines.items():
            supabase.table("user_baselines").upsert({
                "user_id": int(user_id),
                "metric_category": category,
                "baselines": data,
                "computed_at": datetime.now(timezone.utc).isoformat()
            }, on_conflict="user_id, metric_category").execute()
        
        logger.info(f"Cached {len(baselines)} baseline categories for user {user_id}")
    except Exception as e:
        logger.warning(f"Error caching baselines (non-fatal): {e}")
    
    return baselines


def get_running_baselines(user_id: str, days: int = 90) -> Dict[str, Any]:
    """
    Calculate running-specific baselines over the past N days.
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        result = supabase.table("garmin_activities")\
            .select("distance, duration, raw_data, start_time_local")\
            .eq("user_id", user_id)\
            .ilike("activity_type", "%running%")\
            .gte("start_time_local", cutoff)\
            .execute()
        
        activities = result.data or []
        
        if not activities:
            return {"has_data": False}
        
        # Calculate averages - extract HR from raw_data
        total_distance = sum(a.get("distance") or 0 for a in activities)
        total_duration = sum(a.get("duration") or 0 for a in activities)
        
        hr_values = []
        cadence_values = []
        for a in activities:
            raw = a.get("raw_data") or {}
            if raw.get("averageHR"):
                hr_values.append(raw["averageHR"])
            if raw.get("averageRunningCadenceInStepsPerMinute"):
                cadence_values.append(raw["averageRunningCadenceInStepsPerMinute"])
        
        avg_distance = total_distance / len(activities) if activities else 0
        avg_duration = total_duration / len(activities) if activities else 0
        avg_hr = sum(hr_values) / len(hr_values) if hr_values else 0
        avg_cadence = sum(cadence_values) / len(cadence_values) if cadence_values else 0
        
        # Calculate pace (sec/km)
        avg_pace = 0
        if total_distance > 0:
            avg_pace = (total_duration / total_distance) * 1000  # sec per km
        
        # Efficiency (speed / HR)
        avg_efficiency = 0
        if avg_hr > 0 and total_duration > 0:
            avg_speed = total_distance / total_duration
            avg_efficiency = (avg_speed * 60) / avg_hr * 1000
        
        return {
            "has_data": True,
            "period_days": days,
            "activity_count": len(activities),
            "avg_distance_m": round(avg_distance, 0),
            "avg_duration_sec": round(avg_duration, 0),
            "avg_pace_sec_km": round(avg_pace, 1),
            "avg_hr": round(avg_hr, 0) if avg_hr else None,
            "avg_cadence": round(avg_cadence, 0) if avg_cadence else None,
            "avg_efficiency": round(avg_efficiency, 2),
            "total_distance_km": round(total_distance / 1000, 1),
            "runs_per_week": round(len(activities) / (days / 7), 1)
        }
    except Exception as e:
        return {"has_data": False, "error": str(e)}


def get_health_baselines(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Calculate health metric baselines (sleep, HRV, RHR) over past N days.
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        # Fetch sleep data
        sleep_res = supabase.table("garmin_sleep")\
            .select("date, sleep_data")\
            .eq("user_id", user_id)\
            .gte("date", cutoff)\
            .execute()
        
        sleep_data = sleep_res.data or []
        
        # Fetch daily data for RHR
        daily_res = supabase.table("garmin_daily")\
            .select("date, resting_hr")\
            .eq("user_id", user_id)\
            .gte("date", cutoff)\
            .execute()
        
        daily_data = daily_res.data or []
        
        # Calculate HRV average
        hrv_values = []
        sleep_hours = []
        for s in sleep_data:
            sd = s.get("sleep_data") or {}
            if sd.get("avgOvernightHrv"):
                hrv_values.append(sd["avgOvernightHrv"])
            if sd.get("sleepTimeSeconds"):
                sleep_hours.append(sd["sleepTimeSeconds"] / 3600)
        
        # Calculate RHR average - handle complex nested JSON from Garmin
        rhr_values = []
        for d in daily_data:
            rhr = d.get("resting_hr")
            rhr_val = None
            
            # Handle different formats of resting_hr data
            if isinstance(rhr, (int, float)) and rhr > 0:
                rhr_val = rhr
            elif isinstance(rhr, dict):
                # Try common paths in Garmin JSON structure
                if rhr.get("restingHeartRate"):
                    rhr_val = rhr["restingHeartRate"]
                # Deeply nested Garmin format: allMetrics.metricsMap.WELLNESS_RESTING_HEART_RATE[0].value
                elif rhr.get("allMetrics"):
                    metrics_map = rhr.get("allMetrics", {}).get("metricsMap", {})
                    wellness_rhr = metrics_map.get("WELLNESS_RESTING_HEART_RATE", [])
                    if wellness_rhr and isinstance(wellness_rhr, list) and len(wellness_rhr) > 0:
                        rhr_val = wellness_rhr[0].get("value")
            
            if rhr_val and rhr_val > 0:
                rhr_values.append(rhr_val)
        
        return {
            "has_data": bool(hrv_values or rhr_values or sleep_hours),
            "period_days": days,
            "avg_hrv": round(sum(hrv_values) / len(hrv_values), 1) if hrv_values else None,
            "avg_rhr": round(sum(rhr_values) / len(rhr_values), 0) if rhr_values else None,
            "avg_sleep_hours": round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else None,
            "hrv_data_points": len(hrv_values),
            "rhr_data_points": len(rhr_values),
            "sleep_data_points": len(sleep_hours)
        }
    except Exception as e:
        return {"has_data": False, "error": str(e)}


def get_training_load(user_id: str) -> Dict[str, Any]:
    """
    Calculate recent training load and compare to previous period.
    """
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    two_weeks_ago = (now - timedelta(days=14)).strftime('%Y-%m-%d')
    
    try:
        # Last 7 days
        recent_res = supabase.table("garmin_activities")\
            .select("distance, duration")\
            .eq("user_id", user_id)\
            .gte("start_time_local", week_ago)\
            .execute()
        
        # Previous 7 days
        prev_res = supabase.table("garmin_activities")\
            .select("distance, duration")\
            .eq("user_id", user_id)\
            .gte("start_time_local", two_weeks_ago)\
            .lt("start_time_local", week_ago)\
            .execute()
        
        recent = recent_res.data or []
        previous = prev_res.data or []
        
        recent_dist = sum(a.get("distance") or 0 for a in recent) / 1000  # km
        recent_dur = sum(a.get("duration") or 0 for a in recent) / 3600  # hours
        prev_dist = sum(a.get("distance") or 0 for a in previous) / 1000
        prev_dur = sum(a.get("duration") or 0 for a in previous) / 3600
        
        # Calculate change percentages
        dist_change = 0
        dur_change = 0
        if prev_dist > 0:
            dist_change = ((recent_dist - prev_dist) / prev_dist) * 100
        if prev_dur > 0:
            dur_change = ((recent_dur - prev_dur) / prev_dur) * 100
        
        return {
            "last_7_days": {
                "distance_km": round(recent_dist, 1),
                "duration_hours": round(recent_dur, 1),
                "activity_count": len(recent)
            },
            "previous_7_days": {
                "distance_km": round(prev_dist, 1),
                "duration_hours": round(prev_dur, 1),
                "activity_count": len(previous)
            },
            "change": {
                "distance_pct": round(dist_change, 1),
                "duration_pct": round(dur_change, 1)
            }
        }
    except Exception as e:
        return {"error": str(e)}
