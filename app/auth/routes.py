# app/auth/routes.py
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required
from datetime import timedelta, timezone, datetime
from app.supabase_client import supabase
from app.config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400

    username = data["username"]
    password = data["password"]

    exists_resp = supabase.table("users").select("*").eq("username", username).execute()
    if exists_resp.data:
        return jsonify({"error": "Username already exists."}), 400

    hashed_password = generate_password_hash(password)
    user_doc = {
        "username": username,
        "password": hashed_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "goals": {}  # stored as JSONB
    }

    try:
        response = supabase.table("users").insert(user_doc).execute()
        if response.data:
            return jsonify({"message": "User registered successfully.", "user_id": response.data[0]["id"]}), 201
        else:
            return jsonify({"error": "Registration failed."}), 500
    except Exception as e:
        current_app.logger.error(f"Error registering user: {e}")
        return jsonify({"error": "Registration failed."}), 500

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400

    username = data["username"]
    password = data["password"]

    resp = supabase.table("users").select("*").eq("username", username).execute()
    if not resp.data:
        return jsonify({"error": "Invalid username or password."}), 401

    user = resp.data[0]
    if not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password."}), 401

    access_token = create_access_token(identity=str(user["id"]), expires_delta=timedelta(minutes=Config.TOKEN_EXPIRATION_MINUTES))
    
    # Background sync removed from login to prevent database gridlock
    # try:
    #     from threading import Thread
    #     from app.garmin.sync import sync_all_garmin_data_for_user
    #     ...
    # except Exception as e:
    #     current_app.logger.error(f"Failed to trigger background sync for user {user['id']}: {e}")

    return jsonify({"token": access_token}), 200

@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    from flask_jwt_extended import get_jwt_identity
    user_id = get_jwt_identity()
    
    try:
        # Update user profile
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided."}), 400
        
        # Extract fields to update
        updates = {}
        
        # Direct fields
        if "age" in data: updates["age"] = int(data["age"]) if data["age"] else None
        if "weight" in data: updates["weight"] = float(data["weight"]) if data["weight"] else None
        if "height" in data: updates["height"] = float(data["height"]) if data["height"] else None
        if "sport_history" in data: updates["sport_history"] = data["sport_history"]
        if "running_experience" in data: updates["running_experience"] = data["running_experience"]
        if "past_injuries" in data: updates["past_injuries"] = data["past_injuries"]
        if "lifestyle" in data: updates["lifestyle"] = data["lifestyle"]
        if "weekly_availability" in data: updates["weekly_availability"] = data["weekly_availability"]
        if "terrain_preference" in data: updates["terrain_preference"] = data["terrain_preference"]
        if "equipment" in data: updates["equipment"] = data["equipment"]
        
        # Nested JSONB fields (goals)
        user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
        current_goals = {}
        if user_response.data:
            current_goals = user_response.data[0].get("goals") or {}
            
        if "goals" in data and isinstance(data["goals"], dict):
            current_goals.update(data["goals"])
        
        # Handle 'units' and 'llm_model'
        if "units" in data:
            current_goals["units"] = data["units"]
        if "llm_model" in data:
            current_goals["llm_model"] = data["llm_model"]
            
        updates["goals"] = current_goals

        supabase.table("users").update(updates).eq("id", user_id).execute()
        
        return jsonify({"message": "Profile updated successfully."}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating profile for user {user_id}: {e}")
        return jsonify({"error": "Failed to update profile."}), 500

@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    from flask_jwt_extended import get_jwt_identity
    user_id = get_jwt_identity()

    try:
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found."}), 404
        
        user = response.data[0]
        
        # Extract profile fields
        profile_data = {
            "age": user.get("age"),
            "weight": user.get("weight"),
            "height": user.get("height"),
            "sport_history": user.get("sport_history"),
            "running_experience": user.get("running_experience"),
            "past_injuries": user.get("past_injuries"),
            "lifestyle": user.get("lifestyle"),
            "weekly_availability": user.get("weekly_availability"),
            "terrain_preference": user.get("terrain_preference"),
            "equipment": user.get("equipment"),
            "goals": user.get("goals", {}),
            "units": user.get("goals", {}).get("units", "metric"), # Default to metric
            "llm_model": user.get("goals", {}).get("llm_model", "local"), # Default to local
            "garmin_connected": bool(user.get("garmin_email") and user.get("garmin_password")),
            "strava_connected": bool(user.get("strava_access_token"))
        }
        
        return jsonify({"profile": profile_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching profile for user {user_id}: {e}")
        return jsonify({"error": "Failed to fetch profile."}), 500