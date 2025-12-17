"""
Chart Generator for Chat Intelligence

Generates Chart.js compatible data structures based on user queries.
Supports:
- Pace trends (line)
- Weekly distance (bar)
- HRV trends (line)
- Training load (line)
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.supabase_client import supabase

def generate_chart_data(user_id: str, metric: str, period_days: int = 30, scope: str = "trend", encryption_key: str = None, message: str = "") -> Optional[Dict[str, Any]]:
    """
    Generate chart configuration for the requested metric.
    Returns a dict compatible with Chart.js data structure.
    """
    if scope == "activity":
        return _generate_activity_chart(user_id, metric, encryption_key, message)

    cutoff = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    
    if metric in ["pace", "speed", "running_pace"]:
        return _get_pace_chart(user_id, cutoff)
    elif metric in ["distance", "mileage", "volume"]:
        return _get_distance_chart(user_id, cutoff)
    elif metric in ["hrv", "recovery", "stress"]:
        return _get_hrv_chart(user_id, cutoff)
    elif metric in ["training_load", "load"]:
        return _get_training_load_chart(user_id, cutoff)
    elif metric in ["heart_rate", "hr", "pulse"]:
        return _get_heart_rate_chart(user_id, cutoff)
    elif metric in ["cadence", "steps", "spm"]:
        return _get_cadence_chart(user_id, cutoff)
    elif metric in ["elevation", "climbing", "ascent"]:
        return _get_elevation_chart(user_id, cutoff)
    elif metric in ["sleep_score", "sleep_quality"]:
        return _get_sleep_score_chart(user_id, cutoff)
    
    return None


def _generate_activity_chart(user_id: str, metric: str, encryption_key: str, message: str) -> Optional[Dict[str, Any]]:
    """Generate chart for a specific activity by fetching details from Garmin."""
    try:
        # 1. Find the target activity ID
        from app.context.intent_detector import extract_specific_date
        target_date = extract_specific_date(message)
        
        query = supabase.table("garmin_activities").select("*").eq("user_id", user_id).ilike("activity_type", "%running%")
        
        if target_date:
            # Look for activity on that date
            # Assuming target_date is YYYY-MM-DD
            next_day = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            query = query.gte("start_time_local", target_date).lt("start_time_local", next_day)
        
        # Get most recent matching
        query = query.order("start_time_local", desc=True).limit(1)
        result = query.execute()
        
        if not result.data:
            return None
            
        activity = result.data[0]
        activity_id = activity["activity_id"]
        activity_name = activity.get("activity_name", "Activity")
        
        # 2. Fetch detailed data
        details = activity.get("details")
        
        if not details:
            # Try to fetch from Garmin API
            from app.garmin.sync import init_garmin_api_for_user
            api = init_garmin_api_for_user(user_id, encryption_key)
            if api:
                try:
                    details = api.get_activity_details(activity_id)
                    # Save back to DB for future use
                    supabase.table("garmin_activities").update({"details": details}).eq("activity_id", activity_id).execute()
                except Exception as e:
                    print(f"Failed to fetch details from API: {e}")
        
        if not details:
            return None
            
        # 3. Parse streams
        metrics_data = details.get("activityDetailMetrics", [])
        descriptors = details.get("metricDescriptors", [])
        
        if not metrics_data or not descriptors:
            return None
            
        # Map metric keys
        metric_key_map = {
            "heart_rate": "directHeartRate",
            "pace": "directSpeed",
            "cadence": "directCadence",
            "elevation": "directElevation"
        }
        
        target_key = metric_key_map.get(metric)
        if not target_key:
            if metric in ["speed", "running_pace"]: target_key = "directSpeed"
            elif metric in ["hr", "pulse"]: target_key = "directHeartRate"
            elif metric in ["steps", "spm"]: target_key = "directCadence"
            elif metric in ["climbing", "ascent"]: target_key = "directElevation"
            else: return None
            
        # Find index of target key
        target_index = -1
        for i, desc in enumerate(descriptors):
            if desc.get("key") == target_key:
                target_index = i
                break
                
        if target_index == -1:
            return None
            
        # Extract data
        labels = []
        data_points = []
        
        for point in metrics_data:
            val = point["metrics"][target_index]
            if val is not None:
                labels.append("") 
                
                if target_key == "directSpeed":
                    # m/s to min/km
                    if val > 0:
                        pace = (1000 / val) / 60
                        if pace < 30:
                            data_points.append(round(pace, 2))
                        else:
                            data_points.append(None)
                    else:
                        data_points.append(None)
                else:
                    data_points.append(val)
        
        # Decimate if too many points
        if len(data_points) > 500:
            step = len(data_points) // 200
            data_points = data_points[::step]
            labels = labels[::step]
            
        return {
            "type": "line",
            "title": f"{metric.title()} - {activity_name}",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": metric.title(),
                    "data": data_points,
                    "borderColor": "#3b82f6",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)",
                    "pointRadius": 0,
                    "tension": 0.2,
                    "fill": True
                }]
            },
            "options": {
                "scales": {
                    "x": {"display": False},
                    "y": {"reverse": (metric == "pace")}
                }
            }
        }

    except Exception as e:
        print(f"Error generating activity chart: {e}")
        return None


def _get_pace_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate running pace trend chart."""
    result = supabase.table("garmin_activities")\
        .select("start_time_local, distance, duration, raw_data")\
        .eq("user_id", user_id)\
        .ilike("activity_type", "%running%")\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=False)\
        .execute()
    
    activities = result.data or []
    if not activities:
        return None
        
    labels = []
    data_points = []
    
    for a in activities:
        date_str = a["start_time_local"][:10]
        dist = a.get("distance", 0)
        dur = a.get("duration", 0)
        
        if dist > 0:
            pace_min_km = (dur / 60) / (dist / 1000)
            # Filter outliers (e.g. GPS errors or walking breaks)
            if 3 < pace_min_km < 10:
                labels.append(date_str[5:]) # MM-DD
                data_points.append(round(pace_min_km, 2))
    
    return {
        "type": "line",
        "title": "Running Pace Trend (min/km)",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Pace (min/km)",
                "data": data_points,
                "borderColor": "#3b82f6",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "tension": 0.3,
                "fill": True
            }]
        },
        "options": {
            "scales": {
                "y": {
                    "reverse": True,  # Lower pace is better/faster
                    "title": {"display": True, "text": "min/km"}
                }
            }
        }
    }


def _get_distance_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate weekly distance bar chart."""
    result = supabase.table("garmin_activities")\
        .select("start_time_local, distance")\
        .eq("user_id", user_id)\
        .ilike("activity_type", "%running%")\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=False)\
        .execute()
    
    activities = result.data or []
    if not activities:
        return None
        
    # Aggregate by week
    weekly_dist = {}
    for a in activities:
        dt = datetime.fromisoformat(a["start_time_local"])
        # Get start of week (Monday)
        week_start = (dt - timedelta(days=dt.weekday())).strftime('%m-%d')
        dist_km = (a.get("distance") or 0) / 1000
        weekly_dist[week_start] = weekly_dist.get(week_start, 0) + dist_km
    
    labels = sorted(weekly_dist.keys())
    data_points = [round(weekly_dist[k], 1) for k in labels]
    
    return {
        "type": "bar",
        "title": "Weekly Running Distance",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Distance (km)",
                "data": data_points,
                "backgroundColor": "#10b981",
                "borderRadius": 4
            }]
        }
    }


def _get_hrv_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate HRV trend chart."""
    result = supabase.table("garmin_sleep")\
        .select("date, sleep_data")\
        .eq("user_id", user_id)\
        .gte("date", cutoff)\
        .order("date", desc=False)\
        .execute()
    
    data = result.data or []
    if not data:
        return None
        
    labels = []
    hrv_points = []
    
    for d in data:
        sd = d.get("sleep_data") or {}
        hrv = sd.get("avgOvernightHrv")
        if hrv:
            labels.append(d["date"][5:]) # MM-DD
            hrv_points.append(hrv)
            
    return {
        "type": "line",
        "title": "Overnight HRV Trend (ms)",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "HRV (ms)",
                "data": hrv_points,
                "borderColor": "#8b5cf6",
                "backgroundColor": "rgba(139, 92, 246, 0.1)",
                "tension": 0.4,
                "fill": True
            }]
        }
    }


def _get_training_load_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate training load chart from activities."""
    result = supabase.table("garmin_activities")\
        .select("start_time_local, raw_data")\
        .eq("user_id", user_id)\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=False)\
        .execute()
    
    activities = result.data or []
    if not activities:
        return None
        
    labels = []
    load_points = []
    
    for a in activities:
        raw = a.get("raw_data") or {}
        load = raw.get("activityTrainingLoad")
        if load:
            labels.append(a["start_time_local"][:10][5:])
            load_points.append(load)
            
    return {
        "type": "bar",
        "title": "Training Load per Activity",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Training Load",
                "data": load_points,
                "backgroundColor": "#f59e0b",
                "borderRadius": 2
            }]
        }
    }

def _get_heart_rate_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate Avg Heart Rate chart."""
    result = supabase.table("garmin_activities")\
        .select("start_time_local, raw_data")\
        .eq("user_id", user_id)\
        .ilike("activity_type", "%running%")\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=False)\
        .execute()
    
    activities = result.data or []
    if not activities:
        return None
        
    labels = []
    data_points = []
    
    for a in activities:
        raw = a.get("raw_data") or {}
        hr = raw.get("averageHR")
        if hr:
            labels.append(a["start_time_local"][:10][5:])
            data_points.append(hr)
            
    return {
        "type": "line",
        "title": "Avg Heart Rate (bpm)",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Avg HR (bpm)",
                "data": data_points,
                "borderColor": "#ef4444",
                "backgroundColor": "rgba(239, 68, 68, 0.1)",
                "tension": 0.3,
                "fill": True
            }]
        }
    }

def _get_cadence_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate Avg Cadence chart."""
    result = supabase.table("garmin_activities")\
        .select("start_time_local, raw_data")\
        .eq("user_id", user_id)\
        .ilike("activity_type", "%running%")\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=False)\
        .execute()
    
    activities = result.data or []
    if not activities:
        return None
        
    labels = []
    data_points = []
    
    for a in activities:
        raw = a.get("raw_data") or {}
        cadence = raw.get("averageRunningCadenceInStepsPerMinute")
        if cadence:
            labels.append(a["start_time_local"][:10][5:])
            data_points.append(cadence)
            
    return {
        "type": "line",
        "title": "Avg Cadence (spm)",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Cadence (spm)",
                "data": data_points,
                "borderColor": "#8b5cf6",
                "backgroundColor": "rgba(139, 92, 246, 0.1)",
                "tension": 0.3,
                "fill": True
            }]
        }
    }

def _get_elevation_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate Elevation Gain chart."""
    result = supabase.table("garmin_activities")\
        .select("start_time_local, raw_data")\
        .eq("user_id", user_id)\
        .ilike("activity_type", "%running%")\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=False)\
        .execute()
    
    activities = result.data or []
    if not activities:
        return None
        
    labels = []
    data_points = []
    
    for a in activities:
        raw = a.get("raw_data") or {}
        gain = raw.get("elevationGain")
        if gain:
            labels.append(a["start_time_local"][:10][5:])
            data_points.append(round(gain))
            
    return {
        "type": "bar",
        "title": "Elevation Gain (m)",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Ascent (m)",
                "data": data_points,
                "backgroundColor": "#6366f1",
                "borderRadius": 2
            }]
        }
    }

def _get_sleep_score_chart(user_id: str, cutoff: str) -> Dict[str, Any]:
    """Generate Sleep Score trend chart."""
    result = supabase.table("garmin_sleep")\
        .select("date, sleep_data")\
        .eq("user_id", user_id)\
        .gte("date", cutoff)\
        .order("date", desc=False)\
        .execute()
    
    data = result.data or []
    if not data:
        return None
        
    labels = []
    data_points = []
    
    for d in data:
        sd = d.get("sleep_data") or {}
        score = sd.get("sleepScores", {}).get("overall", {}).get("value")
        if score:
            labels.append(d["date"][5:]) # MM-DD
            data_points.append(score)
            
    return {
        "type": "line",
        "title": "Sleep Score Trend",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Sleep Score",
                "data": data_points,
                "borderColor": "#10b981",
                "backgroundColor": "rgba(16, 185, 129, 0.1)",
                "tension": 0.3,
                "fill": True
            }]
        },
        "options": {
            "scales": {
                "y": {
                    "min": 0,
                    "max": 100
                }
            }
        }
    }
