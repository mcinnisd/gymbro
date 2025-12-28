from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.supabase_client import supabase
import logging

analytics_bp = Blueprint('analytics', __name__)
logger = logging.getLogger(__name__)

@analytics_bp.route("/baselines", methods=["GET"])
@jwt_required()
def get_user_baselines():
    """
    Fetch calculated fitness baselines for the user.
    """
    user_id = get_jwt_identity()
    try:
        res = supabase.table("user_baselines").select("baselines").eq("user_id", user_id).eq("metric_category", "running").execute()
        if res.data:
            return jsonify(res.data[0]["baselines"]), 200
        else:
            return jsonify({}), 200 # Return empty object if no baselines yet
    except Exception as e:
        logger.error(f"Error fetching baselines for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
@analytics_bp.route("/summary", methods=["GET"])
@jwt_required()
def get_analytics_summary():
    user_id = get_jwt_identity()
    try:
        from datetime import datetime, timedelta, timezone
        
        # 1. Fetch Activities (Last 90 days for trends)
        ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
        
        act_res = supabase.table("garmin_activities")\
            .select("start_time_local, distance, duration, activity_type, average_hr, average_speed, elevation_gain")\
            .eq("user_id", user_id)\
            .gte("start_time_local", ninety_days_ago)\
            .order("start_time_local", desc=True)\
            .execute()
        
        activities = act_res.data or []

        # 2. Breakdown (All time? Or last 90 days? Frontend seems to imply general stats, let's use 90 days for relevance)
        breakdown = {}
        for act in activities:
            atype = act.get('activity_type', 'other')
            if atype not in breakdown:
                breakdown[atype] = {"count": 0, "distance": 0, "duration": 0}
            breakdown[atype]["count"] += 1
            breakdown[atype]["distance"] += (act.get("distance") or 0)
            breakdown[atype]["duration"] += (act.get("duration") or 0)

        # 3. Weekly Volume (Running only basically, or all? Let's do all for summary)
        weekly_volume = {}
        for act in activities:
            dt = datetime.fromisoformat(act['start_time_local'])
            # ISO format YYYY-Www
            year, week, _ = dt.isocalendar()
            week_key = f"{year}-{week:02d}"
            
            if week_key not in weekly_volume:
                weekly_volume[week_key] = {"distance": 0, "duration": 0}
            
            weekly_volume[week_key]["distance"] += (act.get("distance") or 0)
            weekly_volume[week_key]["duration"] += (act.get("duration") or 0)

        # 4. Efficiency Trend (Running)
        efficiency_trend = []
        # 4. Efficiency Trend (Running)
        efficiency_trend = []
        for act in activities:
            if act.get('activity_type') in ['running', 'treadmill_running', 'street_running', 'track_running']:
                speed = act.get('average_speed')
                hr = act.get('average_hr')
                
                # Defensive float conversion
                try:
                    speed = float(speed) if speed is not None else 0.0
                    hr = float(hr) if hr is not None else 0.0
                except:
                    speed, hr = 0, 0

                if speed > 0 and hr > 0:
                    efficiency_trend.append({
                        "date": act['start_time_local'][:10],
                        "efficiency": (speed * 100) / hr, 
                        "speed": speed,
                        "hr": hr
                    })
        efficiency_trend.reverse() # Oldest first

        # 5. VO2 Max (from Max Metrics)
        vo2_res = supabase.table("garmin_maxmetrics")\
            .select("date, max_metrics")\
            .eq("user_id", user_id)\
            .gte("date", ninety_days_ago)\
            .order("date", asc=True)\
            .execute()
        
        vo2_max = []
        for row in (vo2_res.data or []):
            try:
                # Structure depends on Garmin API response
                # Usually: metric['vo2MaxPreciseValue'] or similar
                 mm = row.get('max_metrics', [])
                 # mm is likely a list of metrics
                 for m in mm:
                     if m.get('genericMetric') == 'vo2MaxPreciseValue':
                         vo2_max.append({"date": row['date'], "value": m.get('value')})
                         break
            except: 
                pass

        # 6. Recovery (RHR/HRV from Daily)
        daily_res = supabase.table("garmin_daily")\
            .select("date, resting_hr, stress")\
            .eq("user_id", user_id)\
            .gte("date", ninety_days_ago)\
            .order("date", asc=True)\
            .execute()
            
        recovery = []
        for row in (daily_res.data or []):
            recovery.append({
                "date": row['date'],
                "rhr": row.get('resting_hr'),
                "hrv": 0 # We don't have HRV yet in garmin_daily schema? Check schema. 
                # Actually we store 'stress' which has stress scores. 
                # Let's assume we lack HRV for now unless it's in stress data.
            })

        # Calculate Averages for Breakdown Cards
        total_elev = sum(a.get('elevation_gain') or 0 for a in activities if a.get('activity_type') in ['hiking', 'running', 'trail_running'])
        
        # Calculate Avg Pace for Running
        runs = [a for a in activities if a.get('activity_type') in ['running', 'street_running']]
        avg_pace = 0
        if runs:
            total_dur = sum(r.get('duration') or 0 for r in runs)
            total_dist_km = sum((r.get('distance') or 0) / 1000.0 for r in runs)
            if total_dist_km > 0:
                avg_pace = total_dur / total_dist_km # sec/km

        response_data = {
            "breakdown": breakdown,
            "weekly_volume": weekly_volume,
            "performance": {
                "running": {
                    "efficiency_trend": efficiency_trend,
                    "avg_pace_sec_km": avg_pace
                },
                "hiking": {
                    "total_elevation_gain": total_elev
                }
            },
            "health_trends": {
                "vo2_max": vo2_max,
                "recovery": recovery
            }
        }

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error fetching analytics summary for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
