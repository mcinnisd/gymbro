# app/activities/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.supabase_client import supabase
from app.utils.helpers import format_conversation

activities_bp = Blueprint('activities', __name__)

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
        response = supabase.table("users").select("*").eq("id", current_user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found!"}), 401
        request.current_user = response.data[0]
        return f(*args, **kwargs)
    return decorated

@activities_bp.route("/", methods=["POST"])
@token_required
def create_activity():
    data = request.get_json()
    required_fields = [
        "activity_id", "name", "type", "distance", "moving_time", "elapsed_time",
        "total_elevation_gain", "start_date_local", "average_speed", "max_speed", "calories"
    ]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    current_user = request.current_user
    data["user_id"] = current_user["id"]

    try:
        response = supabase.table("activities").insert(data).execute()
        if response.data:
            return jsonify({"message": "Activity created", "id": response.data[0]["id"]}), 201
        else:
            return jsonify({"error": "Failed to create activity"}), 500
    except Exception as e:
        current_app.logger.error(f"Error creating activity: {e}")
        return jsonify({"error": "Failed to create activity"}), 500

@activities_bp.route("/", methods=["GET"])
@token_required
def get_activities():
    current_user = request.current_user
    try:
        # Fetch from garmin_activities
        response = supabase.table("garmin_activities").select("*").eq("user_id", current_user["id"]).order("start_time_local", desc=True).execute()
        activities = response.data if response.data else []
        return jsonify({"activities": activities}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching activities: {e}")
        return jsonify({"error": "Failed to fetch activities"}), 500

@activities_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_activity_stats():
    user_id = get_jwt_identity()
    try:
        # Fetch all activities to calculate stats
        # In a real app with many activities, we might want to use SQL aggregation (RPC) or limit the range.
        # For now, fetching all is fine for a prototype.
        response = supabase.table("garmin_activities").select("distance,duration,start_time_local,activity_type").eq("user_id", user_id).execute()
        activities = response.data if response.data else []
        
        if not activities:
             return jsonify({"message": "No activities found."}), 200

        total_distance = sum((a.get("distance") or 0) for a in activities) # meters
        total_duration = sum((a.get("duration") or 0) for a in activities) # seconds
        count = len(activities)
        
        # Calculate averages
        avg_distance = total_distance / count if count else 0
        avg_duration = total_duration / count if count else 0
        
        # Group by type
        by_type = {}
        for a in activities:
            atype = a.get("activity_type", "Unknown")
            by_type[atype] = by_type.get(atype, 0) + 1

        stats = {
            "total_activities": count,
            "total_distance_km": round(total_distance / 1000, 2),
            "total_duration_hours": round(total_duration / 3600, 2),
            "avg_distance_km": round(avg_distance / 1000, 2),
            "avg_duration_min": round(avg_duration / 60, 2),
            "activities_by_type": by_type
        }
        
        return jsonify(stats), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching activity stats: {e}")
        return jsonify({"error": "Failed to fetch stats."}), 500

@activities_bp.route("/<activity_id>", methods=["GET"])
@token_required
def get_activity(activity_id):
    current_user = request.current_user
    try:
        # Fetch activity with details
        response = supabase.table("garmin_activities").select("*").eq("activity_id", activity_id).eq("user_id", current_user["id"]).execute()
        
        if not response.data:
            return jsonify({"error": "Activity not found"}), 404
            
        activity = response.data[0]
        
        # Ensure details is a dict (it should be from Supabase, but just in case)
        if activity.get("details") and isinstance(activity["details"], str):
            import json
            try:
                activity["details"] = json.loads(activity["details"])
            except:
                pass

        # DEBUG: Check details structure
        if activity.get("details"):
            current_app.logger.info(f"DEBUG: Activity {activity_id} details keys: {activity['details'].keys()}")
            if "metricDescriptors" in activity["details"]:
                 current_app.logger.info(f"DEBUG: metricDescriptors found. Count: {len(activity['details']['metricDescriptors'])}")
            else:
                 current_app.logger.info("DEBUG: metricDescriptors NOT found in details.")
        
        return jsonify(activity), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching activity {activity_id}: {e}")
        return jsonify({"error": "Failed to fetch activity"}), 500

@activities_bp.route("/summary", methods=["GET"])
@token_required
def get_activities_summary():
    current_user = request.current_user
    try:
        # Fetch all activities for summary calculation
        # In a real app, you might want to limit this to a date range or use a database aggregation function if available
        response = supabase.table("garmin_activities").select("*").eq("user_id", current_user["id"]).order("start_time_local", desc=True).execute()
        activities = response.data if response.data else []
        
        total_workouts = len(activities)
        total_calories = sum((act.get("calories") or 0) for act in activities)
        
        # Calculate active days
        dates = set()
        for act in activities:
            start_time = act.get("start_time_local")
            if start_time:
                dates.add(start_time[:10]) # YYYY-MM-DD
        active_days = len(dates)
        
        summary = {
            "workouts": total_workouts,
            "calories_burned": int(total_calories),
            "active_days": active_days,
            "recent_activities": activities[:5] # Add recent activities here for the dashboard list
        }
        return jsonify(summary), 200
    except Exception as e:
        print(f"Error fetching activity summary: {e}")
        return jsonify({"error": "Failed to fetch summary"}), 500

@activities_bp.route("/daily_stats", methods=["GET"])
@token_required
def get_daily_stats():
    current_user = request.current_user
    try:
        # Fetch daily metrics for the last 7 days
        # We need to fetch both daily stats and sleep data.
        # Since Supabase-py doesn't support complex joins easily in one go without foreign keys setup perfectly or using raw sql,
        # we'll fetch both independently and merge in python (efficient enough for 7 items).
        
        # 1. Fetch Daily Stats
        daily_resp = supabase.table("garmin_daily").select("*").eq("user_id", current_user["id"]).order("date", desc=True).limit(7).execute()
        dailies = daily_resp.data if daily_resp.data else []
        
        # 2. Fetch Sleep Data (for the same dates roughly)
        # We'll just fetch the last 7 records as well.
        sleep_resp = supabase.table("garmin_sleep").select("*").eq("user_id", current_user["id"]).order("date", desc=True).limit(7).execute()
        sleeps = {item["date"]: item for item in (sleep_resp.data or [])}
        
        # Format for Recharts (reverse to show oldest to newest)
        stats = []
        for day in reversed(dailies):
            date_str = day.get("date") # YYYY-MM-DD
            
            # --- Steps ---
            steps = day.get("steps")
            step_count = 0
            if isinstance(steps, int):
                step_count = steps
            elif isinstance(steps, dict):
                step_count = steps.get("totalSteps", 0)
            elif isinstance(steps, list):
                # Sum up steps from intraday list
                step_count = sum((item.get("steps") or 0) for item in steps)
                
            # --- Heart Rate ---
            # Extract Resting, Min, Max if available
            hr_data = day.get("heartrate") or {}
            rhr_data = day.get("resting_hr") or {}
            
            resting_hr = 0
            if isinstance(rhr_data, int):
                resting_hr = rhr_data
            elif isinstance(rhr_data, dict):
                resting_hr = rhr_data.get("restingHeartRate", 0)
            
            # Try to get min/max from heartrate field if it's a dict
            min_hr = None
            max_hr = None
            if isinstance(hr_data, dict):
                min_hr = hr_data.get("minHeartRate")
                max_hr = hr_data.get("maxHeartRate")
            
            # --- Sleep ---
            sleep_rec = sleeps.get(date_str)
            sleep_hours = 0
            if sleep_rec:
                s_data = sleep_rec.get("sleep_data") or {}
                # Check for dailySleepDTO
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
        current_app.logger.error(f"Error fetching activity stats: {e}")
        return jsonify({"error": "Failed to fetch stats"}), 500

@activities_bp.route('/<activity_id>/sync', methods=['POST'])
@token_required
def sync_activity_details_route(activity_id):
    """
    Force sync details for a specific activity.
    """
    current_user = request.current_user # Access current_user from request context
    try:
        from app.garmin.sync import init_garmin_api_for_user
        
        # Initialize Garmin API
        api = init_garmin_api_for_user(current_user["id"], current_app.config.get("ENCRYPTION_KEY"))
        if not api:
             return jsonify({"error": "Garmin not connected"}), 400
             
        # Fetch details
        try:
            details = api.get_activity_details(activity_id)
        except Exception as e:
            current_app.logger.error(f"Error fetching details from Garmin: {e}")
            return jsonify({"error": "Failed to fetch details from Garmin"}), 500
        
        if details:
            # Update DB
            # Ensure details is a dict
            if isinstance(details, str):
                import json
                details = json.loads(details)
                
            supabase.table("garmin_activities").update({"details": details}).eq("activity_id", activity_id).execute()
            return jsonify({"message": "Details synced", "details": details}), 200
        else:
            return jsonify({"error": "Details not found on Garmin"}), 404

    except Exception as e:
        current_app.logger.error(f"Error syncing activity details: {e}")
        return jsonify({"error": str(e)}), 500

@activities_bp.route("/sleep/<date>", methods=["GET"])
@token_required
def get_sleep_details(date):
    current_user = request.current_user
    try:
        response = supabase.table("garmin_sleep").select("*").eq("user_id", current_user["id"]).eq("date", date).execute()
        if not response.data:
            return jsonify({"error": "Sleep data not found"}), 404
        return jsonify(response.data[0]), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching sleep details for {date}: {e}")
        return jsonify({"error": "Failed to fetch sleep details"}), 500