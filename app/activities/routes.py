# app/activities/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
import json
import logging
from app.supabase_client import supabase
from app.health_hub.ingestion_service import get_unified_activities

activities_bp = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

def token_required(f):
    from functools import wraps
    @wraps(f)
    @jwt_required(optional=True)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"}), 200
            
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        
        current_user_id = get_jwt_identity()
        try:
            response = supabase.table("users").select("*").eq("id", current_user_id).execute()
            if response.data:
                request.current_user = response.data[0]
            else:
                request.current_user = {"id": current_user_id}
        except Exception:
            request.current_user = {"id": current_user_id}
        return f(*args, **kwargs)
    return decorated

@activities_bp.route("", methods=["POST"])
@activities_bp.route("/", methods=["POST"])
@token_required
def create_activity():
    data = request.get_json() or {}
    
    # Flexible field support (both legacy payload and mobile/HealthKit workouts)
    activity_type = data.get("type") or data.get("activity_type") or "workout"
    name = data.get("name") or data.get("activity_name") or "Workout"
    start_time = data.get("start_date_local") or data.get("start_time_local") or data.get("start_time") or datetime.now(timezone.utc).isoformat()
    distance = data.get("distance") or data.get("distance_m") or 0.0
    duration = data.get("duration") or data.get("duration_s") or data.get("moving_time") or data.get("elapsed_time") or 0.0
    calories = data.get("calories") or 0.0

    current_user = request.current_user
    uid = current_user["id"]

    insert_record = {
        "user_id": uid,
        "activity_type": activity_type,
        "name": name,
        "start_time_local": start_time,
        "distance": float(distance),
        "duration": float(duration),
        "calories": float(calories),
        "average_hr": data.get("average_hr") or data.get("average_heartrate"),
        "max_hr": data.get("max_hr") or data.get("max_heartrate"),
        "elevation_gain": data.get("elevation_gain") or data.get("total_elevation_gain"),
        "notes": data.get("notes") or ("Apple HealthKit" if "apple" in str(data.get("source", "")).lower() else "Manual Entry"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        response = supabase.table("activities").insert(insert_record).execute()
        if response.data:
            act_id = response.data[0].get("id")
            return jsonify({"message": "Activity created", "id": act_id}), 201
        else:
            return jsonify({"error": "Failed to create activity"}), 500
    except Exception as e:
        logger.error(f"Error creating activity: {e}")
        return jsonify({"error": "Failed to create activity"}), 500

@activities_bp.route("", methods=["GET"])
@activities_bp.route("/", methods=["GET"])
@token_required
def get_activities():
    """
    Unified Activity Stream endpoint.
    Queries Garmin, Strava, and Apple HealthKit/Manual activities, deduplicating
    overlapping workouts with deterministic source hierarchy (Garmin > Strava > HealthKit > Manual).
    """
    current_user = request.current_user
    user_id = current_user["id"]
    
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    activity_type = request.args.get("type") or request.args.get("activity_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    try:
        activities = get_unified_activities(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            activity_type=activity_type,
            limit=limit,
            offset=offset
        )
        return jsonify({"activities": activities}), 200
    except Exception as e:
        logger.error(f"Error fetching unified activities for user {user_id}: {e}")
        return jsonify({"error": "Failed to fetch activities"}), 500

@activities_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_activity_stats():
    """
    Computes aggregate activity statistics across the unified, deduplicated activity lake.
    """
    user_id = get_jwt_identity()
    try:
        activities = get_unified_activities(user_id=user_id, limit=2000)
        
        if not activities:
            return jsonify({"message": "No activities found."}), 200

        total_distance = sum((a.get("distance") or a.get("distance_m") or 0) for a in activities)
        total_duration = sum((a.get("duration") or a.get("duration_s") or 0) for a in activities)
        count = len(activities)
        
        avg_distance = total_distance / count if count else 0
        avg_duration = total_duration / count if count else 0
        
        by_type = {}
        for a in activities:
            atype = a.get("activity_type") or a.get("type") or "Unknown"
            by_type[atype] = by_type.get(atype, 0) + 1

        stats = {
            "total_activities": count,
            "total_distance_km": round(total_distance / 1000, 2) if total_distance > 100 else round(total_distance, 2),
            "total_duration_hours": round(total_duration / 3600, 2) if total_duration > 300 else round(total_duration / 60, 2),
            "avg_distance_km": round(avg_distance / 1000, 2) if avg_distance > 100 else round(avg_distance, 2),
            "avg_duration_min": round(avg_duration / 60, 2) if avg_duration > 300 else round(avg_duration, 2),
            "activities_by_type": by_type
        }
        
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error fetching activity stats for user {user_id}: {e}")
        return jsonify({"error": "Failed to fetch stats."}), 500

@activities_bp.route("/details/<activity_id>", methods=["GET"])
@token_required
def get_activity_details(activity_id):
    """
    Alias for get_activity to match drill-down plan.
    """
    return get_activity(activity_id)

@activities_bp.route("/<activity_id>", methods=["GET"])
@token_required
def get_activity(activity_id):
    """
    Retrieves detailed workout metrics looking up Garmin, Strava, or manual/HealthKit tables.
    """
    current_user = request.current_user
    uid = current_user["id"]
    
    try:
        activity = None

        # 1. Check garmin_activities
        try:
            g_res = supabase.table("garmin_activities").select("*").eq("activity_id", str(activity_id)).eq("user_id", uid).execute()
            if g_res.data:
                activity = dict(g_res.data[0])
                activity["source"] = "garmin"
        except Exception:
            pass

        # 2. Check strava_activities if not found
        if not activity:
            try:
                s_res = supabase.table("strava_activities").select("*").eq("activity_id", str(activity_id)).eq("user_id", uid).execute()
                if s_res.data:
                    activity = dict(s_res.data[0])
                    activity["source"] = "strava"
            except Exception:
                pass

        # 3. Check activities table if not found
        if not activity:
            try:
                a_query = supabase.table("activities").select("*").eq("user_id", uid)
                if str(activity_id).isdigit():
                    a_query = a_query.eq("id", int(activity_id))
                a_res = a_query.execute()
                if a_res.data:
                    activity = dict(a_res.data[0])
                    activity["source"] = "apple_health" if "apple" in str(activity.get("notes", "")).lower() else "manual"
            except Exception:
                pass

        if not activity:
            return jsonify({"error": "Activity not found"}), 404
            
        # Ensure details is a dict if string
        if activity.get("details") and isinstance(activity["details"], str):
            try:
                activity["details"] = json.loads(activity["details"])
            except Exception:
                pass
        
        # Ensure raw_data is a dict if string
        if activity.get("raw_data") and isinstance(activity["raw_data"], str):
            try:
                activity["raw_data"] = json.loads(activity["raw_data"])
            except Exception:
                pass

        return jsonify(activity), 200
    except Exception as e:
        logger.error(f"Error fetching activity {activity_id}: {e}")
        return jsonify({"error": "Failed to fetch activity"}), 500

@activities_bp.route("/summary", methods=["GET"])
@token_required
def get_activities_summary():
    """
    Returns workout summary (counts, active days, calories, recent 5 activities) across all sources.
    """
    current_user = request.current_user
    user_id = current_user["id"]
    try:
        activities = get_unified_activities(user_id=user_id, limit=500)
        
        total_workouts = len(activities)
        total_calories = sum((act.get("calories") or 0) for act in activities)
        
        dates = set()
        for act in activities:
            start_time = act.get("start_time_local") or act.get("start_time")
            if start_time:
                dates.add(str(start_time)[:10])
        active_days = len(dates)
        
        summary = {
            "workouts": total_workouts,
            "calories_burned": int(total_calories),
            "active_days": active_days,
            "recent_activities": activities[:5]
        }
        return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Error fetching activity summary for user {user_id}: {e}")
        return jsonify({"error": "Failed to fetch summary"}), 500

@activities_bp.route("/daily_stats", methods=["GET"])
@token_required
def get_daily_stats():
    """
    Returns daily stats (steps, resting_hr, min/max hr, sleep_hours) for recent days.
    """
    current_user = request.current_user
    uid = current_user["id"]
    
    try:
        # First attempt: biometrics_daily as canonical source
        bio_resp = supabase.table("biometrics_daily").select("*").eq("user_id", uid).order("date", desc=True).limit(7).execute()
        bio_rows = bio_resp.data if bio_resp.data else []

        stats = []
        if bio_rows:
            for b in reversed(bio_rows):
                stats.append({
                    "date": b.get("date"),
                    "steps": b.get("steps") or 0,
                    "resting_hr": b.get("resting_hr") or 0,
                    "min_hr": None,
                    "max_hr": None,
                    "sleep_hours": float(b.get("sleep_hours") or 0.0),
                    "hrv": b.get("hrv") or b.get("hrv_ms"),
                    "sleep_score": b.get("sleep_score"),
                    "body_battery": b.get("body_battery")
                })
        else:
            # Fallback to garmin_daily and garmin_sleep
            daily_resp = supabase.table("garmin_daily").select("*").eq("user_id", uid).order("date", desc=True).limit(7).execute()
            dailies = daily_resp.data if daily_resp.data else []
            
            sleep_resp = supabase.table("garmin_sleep").select("*").eq("user_id", uid).order("date", desc=True).limit(7).execute()
            sleeps = {item["date"]: item for item in (sleep_resp.data or [])}
            
            for day in reversed(dailies):
                date_str = day.get("date")
                
                steps = day.get("steps")
                step_count = 0
                if isinstance(steps, int):
                    step_count = steps
                elif isinstance(steps, dict):
                    step_count = steps.get("totalSteps", 0)
                elif isinstance(steps, list):
                    step_count = sum((item.get("steps") or 0) for item in steps)
                    
                hr_data = day.get("heartrate") or {}
                rhr_data = day.get("resting_hr") or {}
                
                resting_hr = 0
                if isinstance(rhr_data, int):
                    resting_hr = rhr_data
                elif isinstance(rhr_data, dict):
                    resting_hr = rhr_data.get("restingHeartRate", 0)
                
                min_hr = None
                max_hr = None
                if isinstance(hr_data, dict):
                    min_hr = hr_data.get("minHeartRate")
                    max_hr = hr_data.get("maxHeartRate")
                
                sleep_rec = sleeps.get(date_str)
                sleep_hours = 0
                if sleep_rec:
                    s_data = sleep_rec.get("sleep_data") or {}
                    dto = s_data.get("dailySleepDTO")
                    if dto:
                        duration_sec = dto.get("sleepTimeSeconds") or dto.get("sleepDurationSeconds") or 0
                    else:
                        duration_sec = s_data.get("durationInSeconds") or s_data.get("totalSleepSeconds") or 0
                    
                    sleep_hours = round(duration_sec / 3600, 1)

                stats.append({
                    "date": date_str,
                    "steps": step_count,
                    "resting_hr": resting_hr,
                    "min_hr": min_hr,
                    "max_hr": max_hr,
                    "sleep_hours": sleep_hours
                })
                
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error fetching daily stats: {e}")
        return jsonify({"error": "Failed to fetch stats"}), 500

@activities_bp.route('/<activity_id>/sync', methods=['POST'])
@token_required
def sync_activity_details_route(activity_id):
    """
    Force sync details for a specific Garmin activity.
    """
    current_user = request.current_user
    try:
        from app.garmin.sync import init_garmin_api_for_user
        
        api = init_garmin_api_for_user(current_user["id"], current_app.config.get("ENCRYPTION_KEY"))
        if not api:
             return jsonify({"error": "Garmin not connected"}), 400
             
        try:
            details = api.get_activity_details(activity_id)
        except Exception as e:
            logger.error(f"Error fetching details from Garmin: {e}")
            return jsonify({"error": "Failed to fetch details from Garmin"}), 500
        
        if details:
            if isinstance(details, str):
                details = json.loads(details)
                
            supabase.table("garmin_activities").update({"details": details}).eq("activity_id", activity_id).execute()
            return jsonify({"message": "Details synced", "details": details}), 200
        else:
            return jsonify({"error": "Details not found on Garmin"}), 404

    except Exception as e:
        logger.error(f"Error syncing activity details: {e}")
        return jsonify({"error": str(e)}), 500
