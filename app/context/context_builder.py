"""
Context Builder for Contextual Chat Intelligence

Fetches and formats relevant user data based on detected intent.
Designed to be injected into LLM prompts for personalized responses.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from app.supabase_client import supabase
from .intent_detector import DetectedIntent, IntentType
from .baseline_service import get_user_baselines


def build_context(user_id: str, intent: DetectedIntent) -> Optional[Dict[str, Any]]:
    """
    Build context payload based on detected intent.
    
    Args:
        user_id: The user's ID
        intent: The detected intent from the user's message
        
    Returns:
        Dictionary with relevant context data, or None if no context needed
    """
    if intent.intent_type == IntentType.NONE:
        return None
    
    context = {
        "intent": intent.intent_type.value,
        "generated_at": datetime.now().isoformat()
    }
    
    # Get baselines (used by multiple intent types)
    baselines = get_user_baselines(user_id)
    
    if intent.intent_type == IntentType.RECENT_ACTIVITY:
        activity_data = get_recent_activity_context(
            user_id, 
            intent.activity_type_hint,
            intent.time_reference,
            intent.specific_date  # Pass specific date
        )
        context["activity"] = activity_data
        
        # Add comparative metrics if we have both activity and baselines
        running_baselines = baselines.get("running", {})
        context["baselines"] = running_baselines
        
        if activity_data.get("found") and running_baselines.get("has_data"):
            context["comparison"] = compute_activity_comparison(activity_data, running_baselines)
        
    elif intent.intent_type == IntentType.FATIGUE_RECOVERY:
        health_baselines = baselines.get("health", {})
        context["health"] = get_health_recovery_context(user_id, health_baselines)
        context["training_load"] = baselines.get("training_load", {})
        context["baselines"] = health_baselines
        
    elif intent.intent_type == IntentType.PERFORMANCE_REVIEW:
        context["performance"] = get_performance_context(user_id)
        context["baselines"] = baselines
        
    elif intent.intent_type == IntentType.SPECIFIC_METRIC:
        # Include baselines by default
        context["metrics"] = baselines
        
        # Check if sleep-related query - if so, also fetch health context
        message_lower = str(intent.matched_keywords).lower()
        if "sleep" in message_lower or any(kw in message_lower for kw in ["hrv", "rhr", "recovery"]):
            health_baselines = baselines.get("health", {})
            context["health"] = get_health_recovery_context(user_id, health_baselines)
            context["baselines"] = health_baselines
        
    elif intent.intent_type == IntentType.COMPARISON:
        context["comparison"] = get_comparison_context(user_id)
        context["baselines"] = baselines
    
    # Add proactive coaching insights (Phase 4)
    try:
        from app.context.proactive_coach import get_proactive_context
        proactive = get_proactive_context(user_id, baselines)
        if proactive:
            context["proactive"] = proactive
    except Exception as e:
        pass  # Non-blocking, silently fail
    
    # Add recent activities list for reference (helps ground LLM in verifiable data)
    try:
        recent_activities = get_recent_activities_list(user_id, limit=5, activity_type="running")
        if recent_activities:
            context["recent_activities"] = recent_activities
            # Extract latest VO2 max from activities
            for act in recent_activities:
                if act.get("vo2_max"):
                    context["current_vo2_max"] = act["vo2_max"]
                    break
    except Exception as e:
        pass
    
    return context


def compute_activity_comparison(activity: Dict[str, Any], baselines: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute comparison metrics between a specific activity and user baselines.
    """
    comparison = {}
    
    # Distance comparison
    if activity.get("distance_km") and baselines.get("avg_distance_m"):
        avg_dist_km = baselines["avg_distance_m"] / 1000
        diff_pct = ((activity["distance_km"] - avg_dist_km) / avg_dist_km) * 100 if avg_dist_km > 0 else 0
        comparison["distance"] = {
            "vs_avg_km": round(avg_dist_km, 2),
            "diff_pct": round(diff_pct, 1),
            "description": f"{'longer' if diff_pct > 0 else 'shorter'} than typical" if abs(diff_pct) > 5 else "typical distance"
        }
    
    # Pace comparison
    if activity.get("pace_min_km") and baselines.get("avg_pace_sec_km"):
        avg_pace_min = baselines["avg_pace_sec_km"] / 60
        diff_pct = ((activity["pace_min_km"] - avg_pace_min) / avg_pace_min) * 100 if avg_pace_min > 0 else 0
        comparison["pace"] = {
            "vs_avg_min_km": round(avg_pace_min, 2),
            "diff_pct": round(diff_pct, 1),
            "description": f"{'slower' if diff_pct > 0 else 'faster'} than typical" if abs(diff_pct) > 5 else "typical pace"
        }
    
    # HR comparison
    if activity.get("avg_hr") and baselines.get("avg_hr"):
        diff_pct = ((activity["avg_hr"] - baselines["avg_hr"]) / baselines["avg_hr"]) * 100 if baselines["avg_hr"] > 0 else 0
        comparison["heart_rate"] = {
            "vs_avg_bpm": baselines["avg_hr"],
            "diff_pct": round(diff_pct, 1),
            "description": f"{'higher' if diff_pct > 0 else 'lower'} than typical" if abs(diff_pct) > 5 else "typical HR"
        }
    
    # Efficiency comparison
    if activity.get("efficiency_index") and baselines.get("avg_efficiency"):
        diff_pct = ((activity["efficiency_index"] - baselines["avg_efficiency"]) / baselines["avg_efficiency"]) * 100 if baselines["avg_efficiency"] > 0 else 0
        comparison["efficiency"] = {
            "vs_avg": round(baselines["avg_efficiency"], 2),
            "diff_pct": round(diff_pct, 1),
            "description": f"{'more' if diff_pct > 0 else 'less'} efficient than typical" if abs(diff_pct) > 5 else "typical efficiency"
        }
    
    return comparison


def get_recent_activity_context(
    user_id: str, 
    activity_type: Optional[str] = None,
    time_ref: Optional[str] = None,
    specific_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get the most recent activity matching the criteria, or activity from specific date.
    """
    try:
        query = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("start_time_local", desc=True)
        
        # If specific date is provided, filter by that date
        if specific_date:
            # Match activities starting on that date (YYYY-MM-DD)
            next_day = (datetime.strptime(specific_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            query = query.gte("start_time_local", specific_date).lt("start_time_local", next_day)
        
        if activity_type:
            query = query.ilike("activity_type", f"%{activity_type}%")
        
        query = query.limit(5)
        result = query.execute()
        activities = result.data or []
        
        if not activities:
            return {"found": False, "searched_date": specific_date}
        
        # Get the most recent one (or first match for specific date)
        activity = activities[0]
        raw_data = activity.get("raw_data") or {}
        
        # Extract metrics from raw_data JSON
        distance = activity.get("distance") or raw_data.get("distance") or 0
        duration = activity.get("duration") or raw_data.get("duration") or 0
        avg_hr = raw_data.get("averageHR")
        max_hr = raw_data.get("maxHR")
        avg_cadence = raw_data.get("averageRunningCadenceInStepsPerMinute")
        elevation_gain = raw_data.get("elevationGain")
        vo2_max = raw_data.get("vO2MaxValue")
        calories = activity.get("calories") or raw_data.get("calories")
        training_load = raw_data.get("activityTrainingLoad")
        avg_speed = raw_data.get("averageSpeed")  # m/s
        training_effect = raw_data.get("aerobicTrainingEffect")
        
        # Calculate pace
        pace_sec_km = 0
        if distance > 0:
            pace_sec_km = (duration / distance) * 1000
        
        # Calculate efficiency (meters per heartbeat)
        efficiency = 0
        if avg_hr and avg_hr > 0 and duration > 0:
            speed = distance / duration
            efficiency = (speed * 60) / avg_hr * 1000
        
        # Get HR zone times
        hr_zones = {}
        for i in range(1, 6):
            zone_key = f"hrTimeInZone_{i}"
            if raw_data.get(zone_key):
                hr_zones[f"zone_{i}_sec"] = raw_data[zone_key]
        
        return {
            "found": True,
            "type": activity.get("activity_type"),
            "name": raw_data.get("activityName") or activity.get("activity_name"),
            "date": activity.get("start_time_local", "")[:10],
            "time": activity.get("start_time_local", "")[11:16] if activity.get("start_time_local") else None,
            "distance_km": round(distance / 1000, 2),
            "duration_min": round(duration / 60, 1),
            "pace_min_km": round(pace_sec_km / 60, 2) if pace_sec_km else None,
            "avg_hr": round(avg_hr, 0) if avg_hr else None,
            "max_hr": round(max_hr, 0) if max_hr else None,
            "avg_cadence": round(avg_cadence, 0) if avg_cadence else None,
            "elevation_gain_m": round(elevation_gain, 0) if elevation_gain else None,
            "calories": round(calories, 0) if calories else None,
            "vo2_max": vo2_max,
            "training_load": round(training_load, 1) if training_load else None,
            "training_effect": training_effect,
            "efficiency_index": round(efficiency, 2) if efficiency else None,
            "hr_zones": hr_zones if hr_zones else None,
            "searched_date": specific_date  # Include what date was searched
        }
    except Exception as e:
        return {"found": False, "error": str(e), "searched_date": specific_date}


def get_recent_activities_list(user_id: str, limit: int = 5, activity_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get a list of recent activities with key metrics for reference.
    Helps ground LLM responses in verifiable data.
    """
    try:
        query = supabase.table("garmin_activities")\
            .select("activity_id, activity_type, distance, duration, raw_data, start_time_local")\
            .eq("user_id", user_id)\
            .order("start_time_local", desc=True)\
            .limit(limit)
        
        if activity_type:
            query = query.ilike("activity_type", f"%{activity_type}%")
        
        result = query.execute()
        activities = []
        
        for a in result.data or []:
            raw = a.get("raw_data") or {}
            distance_km = round((a.get("distance") or 0) / 1000, 1)
            duration_min = round((a.get("duration") or 0) / 60, 1)
            pace = round(duration_min / distance_km, 2) if distance_km > 0 else None
            
            activities.append({
                "id": a.get("activity_id"),
                "type": a.get("activity_type"),
                "name": raw.get("activityName"),
                "date": a.get("start_time_local", "")[:10],
                "distance_km": distance_km,
                "duration_min": duration_min,
                "pace_min_km": pace,
                "avg_hr": raw.get("averageHR"),
                "max_hr": raw.get("maxHR"),
                "vo2_max": raw.get("vO2MaxValue"),
                "training_load": raw.get("activityTrainingLoad")
            })
        
        return activities
    except Exception as e:
        return []


def get_health_recovery_context(user_id: str, health_baselines: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get recent health/recovery data for fatigue analysis.
    Includes alerts and comparisons to baselines.
    """
    try:
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Get sleep data
        sleep_res = supabase.table("garmin_sleep")\
            .select("date, sleep_data")\
            .eq("user_id", user_id)\
            .gte("date", week_ago)\
            .order("date", desc=True)\
            .execute()
        
        # Get daily data
        daily_res = supabase.table("garmin_daily")\
            .select("date, resting_hr")\
            .eq("user_id", user_id)\
            .gte("date", week_ago)\
            .order("date", desc=True)\
            .execute()
        
        sleep_data = sleep_res.data or []
        daily_data = daily_res.data or []
        
        # Process last 7 days
        hrv_values = []
        sleep_hours = []
        sleep_quality = []
        rhr_values = []
        
        for s in sleep_data:
            sd = s.get("sleep_data") or {}
            if sd.get("avgOvernightHrv"):
                hrv_values.append({"date": s["date"], "value": sd["avgOvernightHrv"]})
            if sd.get("sleepTimeSeconds"):
                hours = sd["sleepTimeSeconds"] / 3600
                sleep_hours.append({"date": s["date"], "value": round(hours, 1)})
            # Extract sleep quality score if available
            if sd.get("overallSleepScore", {}).get("value"):
                sleep_quality.append({"date": s["date"], "value": sd["overallSleepScore"]["value"]})
            elif sd.get("sleepScores", {}).get("overall", {}).get("value"):
                sleep_quality.append({"date": s["date"], "value": sd["sleepScores"]["overall"]["value"]})
        
        for d in daily_data:
            rhr = d.get("resting_hr")
            rhr_val = None
            
            # Handle different formats of resting_hr data
            if isinstance(rhr, (int, float)) and rhr > 0:
                rhr_val = rhr
            elif isinstance(rhr, dict):
                if rhr.get("restingHeartRate"):
                    rhr_val = rhr["restingHeartRate"]
                # Deeply nested Garmin format
                elif rhr.get("allMetrics"):
                    metrics_map = rhr.get("allMetrics", {}).get("metricsMap", {})
                    wellness_rhr = metrics_map.get("WELLNESS_RESTING_HEART_RATE", [])
                    if wellness_rhr and isinstance(wellness_rhr, list) and len(wellness_rhr) > 0:
                        rhr_val = wellness_rhr[0].get("value")
            
            if rhr_val and rhr_val > 0:
                rhr_values.append({"date": d["date"], "value": rhr_val})
        
        # Calculate averages
        avg_hrv = sum(v["value"] for v in hrv_values) / len(hrv_values) if hrv_values else None
        avg_sleep = sum(v["value"] for v in sleep_hours) / len(sleep_hours) if sleep_hours else None
        avg_rhr = sum(v["value"] for v in rhr_values) / len(rhr_values) if rhr_values else None
        avg_quality = sum(v["value"] for v in sleep_quality) / len(sleep_quality) if sleep_quality else None
        
        # Calculate trends (last 3 days vs first 4 days)
        hrv_trend = calculate_trend(hrv_values)
        sleep_trend = calculate_trend(sleep_hours)
        rhr_trend = calculate_trend(rhr_values)
        
        # Get most recent values
        latest_hrv = hrv_values[0]["value"] if hrv_values else None
        latest_sleep = sleep_hours[0]["value"] if sleep_hours else None
        latest_rhr = rhr_values[0]["value"] if rhr_values else None
        
        # Generate alerts based on patterns
        alerts = []
        
        # HRV alerts (lower = stress/fatigue)
        if avg_hrv and health_baselines and health_baselines.get("avg_hrv"):
            baseline_hrv = health_baselines["avg_hrv"]
            diff_pct = ((avg_hrv - baseline_hrv) / baseline_hrv) * 100
            if diff_pct < -15:
                alerts.append({
                    "type": "warning",
                    "metric": "HRV",
                    "message": f"HRV is {abs(diff_pct):.0f}% below baseline - possible stress or incomplete recovery"
                })
            elif diff_pct < -10:
                alerts.append({
                    "type": "caution",
                    "metric": "HRV",
                    "message": f"HRV slightly below normal ({abs(diff_pct):.0f}% under baseline)"
                })
        
        # Sleep alerts
        if avg_sleep and health_baselines and health_baselines.get("avg_sleep_hours"):
            baseline_sleep = health_baselines["avg_sleep_hours"]
            diff_hours = avg_sleep - baseline_sleep
            if diff_hours < -1.0:
                alerts.append({
                    "type": "warning",
                    "metric": "Sleep",
                    "message": f"Sleep deficit: averaging {abs(diff_hours):.1f}h less than baseline"
                })
            elif diff_hours < -0.5:
                alerts.append({
                    "type": "caution", 
                    "metric": "Sleep",
                    "message": f"Slightly under-sleeping ({abs(diff_hours):.1f}h below baseline)"
                })
        
        # RHR alerts (higher = stress/illness)
        if avg_rhr and health_baselines and health_baselines.get("avg_rhr"):
            baseline_rhr = health_baselines["avg_rhr"]
            diff = avg_rhr - baseline_rhr
            if diff > 5:
                alerts.append({
                    "type": "warning",
                    "metric": "RHR",
                    "message": f"Resting HR elevated by {diff:.0f} bpm - monitor for overtraining or illness"
                })
            elif diff > 3:
                alerts.append({
                    "type": "caution",
                    "metric": "RHR",
                    "message": f"RHR slightly elevated ({diff:.0f} bpm above baseline)"
                })
        
        # Training load alerts from recent context
        if hrv_trend == "declining" and rhr_trend == "rising":
            alerts.append({
                "type": "warning",
                "metric": "Recovery",
                "message": "Both HRV declining AND RHR rising - strong fatigue signal"
            })
        
        # Sleep debt accumulation
        if sleep_hours and len(sleep_hours) >= 3:
            recent_avg = sum(v["value"] for v in sleep_hours[:3]) / 3
            if recent_avg < 6.0:
                alerts.append({
                    "type": "warning",
                    "metric": "Sleep",
                    "message": f"Sleep debt building: only {recent_avg:.1f}h avg over last 3 nights"
                })
        
        return {
            "period": "last_7_days",
            "summary": {
                "avg_hrv": round(avg_hrv, 1) if avg_hrv else None,
                "avg_sleep_hours": round(avg_sleep, 1) if avg_sleep else None,
                "avg_rhr": round(avg_rhr, 0) if avg_rhr else None,
                "avg_sleep_quality": round(avg_quality, 0) if avg_quality else None
            },
            "latest": {
                "hrv": latest_hrv,
                "sleep_hours": latest_sleep,
                "rhr": latest_rhr
            },
            "trends": {
                "hrv": hrv_trend,
                "sleep": sleep_trend,
                "rhr": rhr_trend
            },
            "alerts": alerts,
            "daily_hrv": hrv_values[:7],
            "daily_sleep": sleep_hours[:7],
            "daily_rhr": rhr_values[:7]
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_trend(values: list) -> str:
    """
    Calculate trend direction from a list of {date, value} dicts.
    Returns 'improving', 'declining', or 'stable'.
    """
    if not values or len(values) < 4:
        return "insufficient_data"
    
    # Compare recent (first 3) vs earlier (rest)
    recent = [v["value"] for v in values[:3]]
    earlier = [v["value"] for v in values[3:]]
    
    if not recent or not earlier:
        return "insufficient_data"
    
    recent_avg = sum(recent) / len(recent)
    earlier_avg = sum(earlier) / len(earlier)
    
    diff_pct = ((recent_avg - earlier_avg) / earlier_avg) * 100 if earlier_avg else 0
    
    if diff_pct > 5:
        return "rising"
    elif diff_pct < -5:
        return "declining"
    else:
        return "stable"


def get_performance_context(user_id: str) -> Dict[str, Any]:
    """
    Get performance trend data for progress review.
    """
    try:
        # Get last 30 days vs previous 30 days
        now = datetime.now()
        thirty_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        sixty_ago = (now - timedelta(days=60)).strftime('%Y-%m-%d')
        
        # Recent period
        recent_res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("start_time_local", thirty_ago)\
            .execute()
        
        # Previous period
        prev_res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("start_time_local", sixty_ago)\
            .lt("start_time_local", thirty_ago)\
            .execute()
        
        recent = recent_res.data or []
        previous = prev_res.data or []
        
        def calc_stats(activities):
            if not activities:
                return None
            
            running = [a for a in activities if "running" in (a.get("activity_type") or "").lower()]
            
            total_dist = sum(a.get("distance") or 0 for a in running)
            total_dur = sum(a.get("duration") or 0 for a in running)
            hr_values = [a.get("average_hr") for a in running if a.get("average_hr")]
            
            avg_pace = (total_dur / total_dist * 1000) if total_dist > 0 else 0
            avg_hr = sum(hr_values) / len(hr_values) if hr_values else 0
            
            return {
                "run_count": len(running),
                "total_distance_km": round(total_dist / 1000, 1),
                "avg_pace_min_km": round(avg_pace / 60, 2) if avg_pace else None,
                "avg_hr": round(avg_hr, 0) if avg_hr else None
            }
        
        recent_stats = calc_stats(recent)
        prev_stats = calc_stats(previous)
        
        # Calculate improvements
        improvements = {}
        if recent_stats and prev_stats and recent_stats.get("avg_pace_min_km") and prev_stats.get("avg_pace_min_km"):
            pace_diff = prev_stats["avg_pace_min_km"] - recent_stats["avg_pace_min_km"]
            improvements["pace_improvement_sec_km"] = round(pace_diff * 60, 1)
            improvements["pace_faster"] = pace_diff > 0
        
        return {
            "period": "30_days_vs_previous_30",
            "recent": recent_stats,
            "previous": prev_stats,
            "improvements": improvements
        }
    except Exception as e:
        return {"error": str(e)}


def get_comparison_context(user_id: str) -> Dict[str, Any]:
    """
    Get year-over-year comparison data (Phase 3).
    Compares current 30-day period to same period last year.
    """
    try:
        now = datetime.now()
        
        # Current period: last 30 days
        current_start = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        current_end = now.strftime('%Y-%m-%d')
        
        # Same period last year
        last_year = now.replace(year=now.year - 1)
        ly_start = (last_year - timedelta(days=30)).strftime('%Y-%m-%d')
        ly_end = last_year.strftime('%Y-%m-%d')
        
        # Fetch current period activities
        current_res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("start_time_local", current_start)\
            .lte("start_time_local", current_end)\
            .execute()
        
        # Fetch last year's activities
        last_year_res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("start_time_local", ly_start)\
            .lte("start_time_local", ly_end)\
            .execute()
        
        current_activities = current_res.data or []
        ly_activities = last_year_res.data or []
        
        def calc_period_stats(activities):
            if not activities:
                return None
            
            running = [a for a in activities if "running" in (a.get("activity_type") or "").lower()]
            
            total_dist = sum(a.get("distance") or 0 for a in running)
            total_dur = sum(a.get("duration") or 0 for a in running)
            hr_values = [a.get("average_hr") for a in running if a.get("average_hr")]
            
            avg_pace = (total_dur / total_dist * 1000) if total_dist > 0 else 0
            avg_hr = sum(hr_values) / len(hr_values) if hr_values else 0
            
            return {
                "run_count": len(running),
                "total_distance_km": round(total_dist / 1000, 1),
                "avg_pace_min_km": round(avg_pace / 60, 2) if avg_pace else None,
                "avg_hr": round(avg_hr, 0) if avg_hr else None,
                "avg_distance_km": round((total_dist / 1000) / len(running), 1) if running else None
            }
        
        current_stats = calc_period_stats(current_activities)
        ly_stats = calc_period_stats(ly_activities)
        
        # Calculate year-over-year changes
        yoy_changes = {}
        if current_stats and ly_stats:
            if current_stats.get("total_distance_km") and ly_stats.get("total_distance_km"):
                dist_change = ((current_stats["total_distance_km"] - ly_stats["total_distance_km"]) / ly_stats["total_distance_km"]) * 100
                yoy_changes["distance"] = {
                    "pct_change": round(dist_change, 1),
                    "direction": "up" if dist_change > 0 else "down",
                    "description": f"Running {abs(dist_change):.0f}% {'more' if dist_change > 0 else 'less'} than last year"
                }
            
            if current_stats.get("avg_pace_min_km") and ly_stats.get("avg_pace_min_km"):
                pace_change = ((ly_stats["avg_pace_min_km"] - current_stats["avg_pace_min_km"]) / ly_stats["avg_pace_min_km"]) * 100
                yoy_changes["pace"] = {
                    "pct_change": round(pace_change, 1),
                    "direction": "faster" if pace_change > 0 else "slower",
                    "description": f"Running {abs(pace_change):.0f}% {'faster' if pace_change > 0 else 'slower'} than last year"
                }
            
            if current_stats.get("run_count") and ly_stats.get("run_count"):
                freq_change = ((current_stats["run_count"] - ly_stats["run_count"]) / ly_stats["run_count"]) * 100
                yoy_changes["frequency"] = {
                    "pct_change": round(freq_change, 1),
                    "direction": "up" if freq_change > 0 else "down",
                    "description": f"Running {abs(freq_change):.0f}% {'more' if freq_change > 0 else 'less'} often"
                }
        
        return {
            "period": "30_days",
            "current_period": {
                "start": current_start,
                "end": current_end,
                "stats": current_stats
            },
            "last_year_period": {
                "start": ly_start,
                "end": ly_end,
                "stats": ly_stats
            },
            "yoy_changes": yoy_changes,
            "has_last_year_data": ly_stats is not None
        }
    except Exception as e:
        return {"error": str(e), "has_last_year_data": False}


def format_context_for_prompt(context: Dict[str, Any]) -> str:
    """
    Format context data as a readable string for LLM injection.
    """
    if not context:
        return ""
    
    lines = ["[USER FITNESS CONTEXT]"]
    
    # Activity context
    if "activity" in context and context["activity"].get("found"):
        act = context["activity"]
        date_note = f" (requested: {act.get('searched_date')})" if act.get("searched_date") else ""
        name = f" - {act.get('name')}" if act.get("name") else ""
        lines.append(f"\n📍 Activity ({act.get('type', 'workout')}){name}{date_note}:")
        lines.append(f"  - Date: {act.get('date')} at {act.get('time', 'unknown time')}")
        lines.append(f"  - Distance: {act.get('distance_km')} km")
        lines.append(f"  - Duration: {act.get('duration_min')} min")
        if act.get("pace_min_km"):
            lines.append(f"  - Pace: {act.get('pace_min_km')} min/km")
        if act.get("avg_hr"):
            hr_str = f"Avg HR: {act.get('avg_hr')} bpm"
            if act.get("max_hr"):
                hr_str += f", Max HR: {act.get('max_hr')} bpm"
            lines.append(f"  - {hr_str}")
        if act.get("avg_cadence"):
            lines.append(f"  - Cadence: {act.get('avg_cadence')} spm")
        if act.get("elevation_gain_m"):
            lines.append(f"  - Elevation Gain: {act.get('elevation_gain_m')} m")
        if act.get("calories"):
            lines.append(f"  - Calories: {act.get('calories')} kcal")
        if act.get("vo2_max"):
            lines.append(f"  - VO2 Max: {act.get('vo2_max')}")
        if act.get("training_load"):
            lines.append(f"  - Training Load: {act.get('training_load')}")
        if act.get("training_effect"):
            lines.append(f"  - Training Effect: {act.get('training_effect')}/5.0")
        if act.get("efficiency_index"):
            lines.append(f"  - Efficiency Index: {act.get('efficiency_index')}")
        # HR Zones breakdown
        if act.get("hr_zones"):
            zones = act["hr_zones"]
            zone_strs = []
            for i in range(1, 6):
                k = f"zone_{i}_sec"
                if zones.get(k):
                    mins = round(zones[k] / 60, 1)
                    zone_strs.append(f"Z{i}:{mins}m")
            if zone_strs:
                lines.append(f"  - HR Zones: {', '.join(zone_strs)}")
    elif "activity" in context and context["activity"].get("searched_date"):
        lines.append(f"\n⚠️ No activity found for date: {context['activity']['searched_date']}")
    
    # Comparison vs baselines (activity-specific)
    if "comparison" in context and context.get("activity", {}).get("found"):
        comp = context["comparison"]
        lines.append("\n📈 Compared to Your Averages:")
        if "distance" in comp:
            d = comp["distance"]
            lines.append(f"  - Distance: {d['diff_pct']:+.1f}% ({d['description']})")
        if "pace" in comp:
            p = comp["pace"]
            lines.append(f"  - Pace: {p['diff_pct']:+.1f}% ({p['description']})")
        if "heart_rate" in comp:
            h = comp["heart_rate"]
            lines.append(f"  - Heart Rate: {h['diff_pct']:+.1f}% ({h['description']})")
        if "efficiency" in comp:
            e = comp["efficiency"]
            lines.append(f"  - Efficiency: {e['diff_pct']:+.1f}% ({e['description']})")
    
    # Baselines summary
    if "baselines" in context:
        baselines = context["baselines"]
        if baselines.get("has_data"):
            lines.append(f"\n📊 User's Typical Stats ({baselines.get('period_days', 30)} days, {baselines.get('activity_count', '?')} runs):")
            if baselines.get("avg_distance_m"):
                lines.append(f"  - Avg Distance: {round(baselines['avg_distance_m']/1000, 1)} km")
            if baselines.get("avg_pace_sec_km"):
                lines.append(f"  - Avg Pace: {round(baselines['avg_pace_sec_km']/60, 2)} min/km")
            if baselines.get("avg_hr"):
                lines.append(f"  - Avg HR: {baselines['avg_hr']} bpm")
            if baselines.get("runs_per_week"):
                lines.append(f"  - Runs/week: {baselines['runs_per_week']}")
    
    # Health context (Phase 2 enhanced)
    if "health" in context:
        health = context["health"]
        summary = health.get("summary", {})
        latest = health.get("latest", {})
        trends = health.get("trends", {})
        alerts = health.get("alerts", [])
        daily_rhr = health.get("daily_rhr", [])
        
        if summary:
            # Add source citation with date range
            date_range = ""
            if daily_rhr and len(daily_rhr) > 0:
                start_date = daily_rhr[-1]["date"] if daily_rhr else ""
                end_date = daily_rhr[0]["date"] if daily_rhr else ""
                date_range = f" [Source: Garmin {start_date} to {end_date}]"
            
            lines.append(f"\n❤️ Recovery Status (Last 7 Days){date_range}:")
            if summary.get("avg_hrv"):
                trend_emoji = {"rising": "📈", "declining": "📉", "stable": "➡️"}.get(trends.get("hrv", ""), "")
                lines.append(f"  - Avg HRV: {summary['avg_hrv']} ms {trend_emoji}")
            if summary.get("avg_sleep_hours"):
                trend_emoji = {"rising": "📈", "declining": "📉", "stable": "➡️"}.get(trends.get("sleep", ""), "")
                lines.append(f"  - Avg Sleep: {summary['avg_sleep_hours']} hours {trend_emoji}")
            if summary.get("avg_rhr"):
                trend_emoji = {"rising": "📈", "declining": "📉", "stable": "➡️"}.get(trends.get("rhr", ""), "")
                lines.append(f"  - Avg RHR: {summary['avg_rhr']} bpm {trend_emoji}")
            if summary.get("avg_sleep_quality"):
                lines.append(f"  - Sleep Quality: {summary['avg_sleep_quality']}/100")
        
        # Show latest values if available
        if latest and any(latest.values()):
            lines.append("\n📊 Most Recent:")
            if latest.get("hrv"):
                lines.append(f"  - Last HRV: {latest['hrv']} ms")
            if latest.get("sleep_hours"):
                lines.append(f"  - Last Sleep: {latest['sleep_hours']} hours")
            if latest.get("rhr"):
                lines.append(f"  - Last RHR: {latest['rhr']} bpm")
        
        # Show alerts prominently
        if alerts:
            lines.append("\n⚠️ ALERTS:")
            for alert in alerts:
                icon = "🚨" if alert["type"] == "warning" else "⚡"
                lines.append(f"  {icon} [{alert['metric']}] {alert['message']}")
    
    # Training load
    if "training_load" in context:
        load = context["training_load"]
        if load.get("last_7_days"):
            recent = load["last_7_days"]
            change = load.get("change", {})
            lines.append("\n🏋️ Training Load:")
            lines.append(f"  - Last 7 days: {recent.get('distance_km')} km, {recent.get('activity_count')} activities")
            if change.get("distance_pct"):
                direction = "↑" if change["distance_pct"] > 0 else "↓"
                lines.append(f"  - Load change: {direction} {abs(change['distance_pct'])}% vs previous week")
    
    # Year-over-Year comparison (Phase 3)
    if "comparison" in context and context["comparison"].get("has_last_year_data"):
        comp = context["comparison"]
        yoy = comp.get("yoy_changes", {})
        current = comp.get("current_period", {}).get("stats", {})
        ly = comp.get("last_year_period", {}).get("stats", {})
        
        lines.append("\n📅 Year-over-Year Comparison (Last 30 Days):")
        if current and ly:
            lines.append(f"  - This year: {current.get('run_count', 0)} runs, {current.get('total_distance_km', 0)} km total")
            lines.append(f"  - Last year: {ly.get('run_count', 0)} runs, {ly.get('total_distance_km', 0)} km total")
        
        if yoy:
            lines.append("  Changes:")
            if "distance" in yoy:
                emoji = "📈" if yoy["distance"]["direction"] == "up" else "📉"
                lines.append(f"    {emoji} {yoy['distance']['description']}")
            if "pace" in yoy:
                emoji = "🏃" if yoy["pace"]["direction"] == "faster" else "🐢"
                lines.append(f"    {emoji} {yoy['pace']['description']}")
            if "frequency" in yoy:
                emoji = "📈" if yoy["frequency"]["direction"] == "up" else "📉"
                lines.append(f"    {emoji} {yoy['frequency']['description']}")
    elif "comparison" in context and not context["comparison"].get("has_last_year_data"):
        lines.append("\n📅 Year-over-Year: No data from this time last year for comparison")
    
    # Proactive Coaching Insights (Phase 4)
    if "proactive" in context and context["proactive"].get("insights"):
        proactive = context["proactive"]
        insights = proactive["insights"][:3]  # Top 3 only
        
        lines.append("\n🎯 COACHING INSIGHTS:")
        for insight in insights:
            icon = {
                "warning": "⚠️",
                "tip": "💡",
                "celebration": "🎉",
                "goal": "🎯"
            }.get(insight["type"], "📌")
            
            lines.append(f"  {icon} {insight['title']}")
            lines.append(f"     {insight['message']}")
            if insight.get("action"):
                lines.append(f"     → Suggestion: {insight['action']}")
    
    lines.append("\n[END CONTEXT]")
    
    return "\n".join(lines)
