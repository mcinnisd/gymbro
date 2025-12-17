from flask import Blueprint, request, jsonify, current_app
from app.supabase_client import supabase
from app.auth.utils import token_required
from datetime import datetime, timedelta
from collections import defaultdict

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/summary', methods=['GET'])
@token_required
def get_analytics_summary():
    try:
        current_user = request.current_user
        user_id = current_user["id"]
        
        # Fetch Activities (Last 6 months for trends)
        six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        activities_res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("start_time_local", six_months_ago)\
            .order("start_time_local", desc=True)\
            .execute()
            
        activities = activities_res.data or []
        
        # Initialize aggregation structures
        breakdown = defaultdict(lambda: {"count": 0, "distance": 0, "duration": 0})
        weekly_volume = defaultdict(lambda: {"distance": 0, "duration": 0, "count": 0})
        running_efficiency_trend = []
        
        # Running stats accumulators
        total_run_distance = 0
        total_run_duration = 0
        total_run_hr = 0
        run_count = 0
        hiking_elevation = 0
        
        for act in activities:
            a_type = act.get("activity_type", "unknown")
            dist = act.get("distance") or 0
            dur = act.get("duration") or 0
            
            # Activity Breakdown
            breakdown[a_type]["count"] += 1
            breakdown[a_type]["distance"] += dist
            breakdown[a_type]["duration"] += dur
            
            # Weekly Volume Trends
            start_date = act.get("start_time_local", "")[:10]
            if start_date:
                try:
                    dt = datetime.strptime(start_date, "%Y-%m-%d")
                    week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
                    weekly_volume[week_key]["distance"] += dist
                    weekly_volume[week_key]["duration"] += dur
                    weekly_volume[week_key]["count"] += 1
                except ValueError:
                    pass  # Skip if date parsing fails
            
            # Running Efficiency Trend
            if "running" in a_type.lower():
                avg_hr = act.get("average_hr")
                if dur > 0 and avg_hr and avg_hr > 0:
                    speed_mps = dist / dur
                    efficiency = (speed_mps * 60) / avg_hr * 1000
                    running_efficiency_trend.append({
                        "date": start_date,
                        "efficiency": efficiency,
                        "speed": speed_mps,
                        "hr": avg_hr
                    })
                    total_run_distance += dist
                    total_run_duration += dur
                    total_run_hr += avg_hr
                    run_count += 1
            
            # Hiking Elevation
            if "hiking" in a_type.lower():
                hiking_elevation += act.get("elevation_gain") or 0
        
        # Sort efficiency trend by date
        running_efficiency_trend.sort(key=lambda x: x["date"])
        
        # Calculate running averages
        avg_run_pace = 0
        avg_run_hr = 0
        if run_count > 0 and total_run_duration > 0:
            avg_run_speed = total_run_distance / total_run_duration
            avg_run_pace = 1000 / avg_run_speed if avg_run_speed > 0 else 0
            avg_run_hr = total_run_hr / run_count
        
        # Count long runs (> 15km)
        long_run_count = sum(
            1 for a in activities 
            if "running" in a.get("activity_type", "").lower() 
            and (a.get("distance") or 0) > 15000
        )
        
        # Fetch VO2 Max (Last 1 Year) - stored as JSON in max_metrics column
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        vo2_res = supabase.table("garmin_maxmetrics")\
            .select("date, max_metrics")\
            .eq("user_id", user_id)\
            .gte("date", one_year_ago)\
            .order("date", desc=True)\
            .execute()
            
        vo2_max_data = []
        for row in (vo2_res.data or []):
            max_metrics = row.get("max_metrics")
            if max_metrics and isinstance(max_metrics, list) and len(max_metrics) > 0:
                # Extract VO2 Max from the nested structure
                for metric in max_metrics:
                    generic = metric.get("generic") or {}
                    vo2 = generic.get("vo2MaxValue")
                    if vo2:
                        vo2_max_data.append({"date": row["date"], "value": vo2})
                        break  # Only take first valid value per day
        
        # Fetch Daily Stats (RHR) - Last 30 days
        daily_res = supabase.table("garmin_daily")\
            .select("date, resting_hr")\
            .eq("user_id", user_id)\
            .order("date", desc=True)\
            .limit(30)\
            .execute()
            
        # Fetch Sleep Data (HRV) - Last 30 days
        sleep_res = supabase.table("garmin_sleep")\
            .select("date, sleep_data")\
            .eq("user_id", user_id)\
            .order("date", desc=True)\
            .limit(30)\
            .execute()
            
        # Merge recovery data by date
        daily_map = {row["date"]: row for row in (daily_res.data or [])}
        sleep_map = {row["date"]: row for row in (sleep_res.data or [])}
        
        recovery_stats = []
        all_dates = sorted(list(set(daily_map.keys()) | set(sleep_map.keys())), reverse=True)
        
        for d in all_dates:
            daily = daily_map.get(d, {})
            sleep_row = sleep_map.get(d, {})
            
            rhr = daily.get("resting_hr")
            rhr_val = 0
            if isinstance(rhr, int):
                rhr_val = rhr
            elif isinstance(rhr, dict):
                rhr_val = rhr.get("restingHeartRate", 0)
            
            sleep_data = sleep_row.get("sleep_data") or {}
            hrv = sleep_data.get("avgOvernightHrv")
            
            recovery_stats.append({
                "date": d,
                "rhr": rhr_val,
                "hrv": hrv
            })

        return jsonify({
            "breakdown": dict(breakdown),
            "weekly_volume": dict(weekly_volume),
            "performance": {
                "running": {
                    "efficiency_trend": running_efficiency_trend,
                    "avg_pace_sec_km": avg_run_pace,
                    "avg_hr": avg_run_hr,
                    "long_run_count": long_run_count
                },
                "hiking": {
                    "total_elevation_gain": hiking_elevation
                }
            },
            "health_trends": {
                "vo2_max": vo2_max_data,
                "recovery": recovery_stats
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching analytics summary: {e}")
        return jsonify({"error": str(e)}), 500

