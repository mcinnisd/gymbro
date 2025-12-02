# app/activities/routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.supabase_client import supabase
from app.utils.helpers import format_conversation

activities_bp = Blueprint('activities', __name__)

def token_required(f):
    from functools import wraps
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        current_user_id = get_jwt_identity()
        response = supabase.table("users").select("*").eq("id", current_user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found!"}), 401
        request.current_user = response.data[0]
        return f(*args, **kwargs)
    return decorated

@activities_bp.route("/activities", methods=["POST"])
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
        print(f"Error creating activity: {e}")
        return jsonify({"error": "Failed to create activity"}), 500

@activities_bp.route("/activities", methods=["GET"])
@token_required
def get_activities():
    current_user = request.current_user
    try:
        response = supabase.table("activities").select("*").eq("user_id", current_user["id"]).execute()
        activities = response.data if response.data else []
        return jsonify(activities), 200
    except Exception as e:
        print(f"Error fetching activities: {e}")
        return jsonify({"error": "Failed to fetch activities"}), 500

@activities_bp.route("/activities/<int:activity_id>", methods=["GET"])
@token_required
def get_activity_by_id(activity_id):
    current_user = request.current_user
    try:
        response = supabase.table("activities").select("*").eq("id", activity_id).eq("user_id", current_user["id"]).execute()
        if response.data and len(response.data) > 0:
            return jsonify(response.data[0]), 200
        else:
            return jsonify({"error": "Activity not found"}), 404
    except Exception as e:
        print(f"Error fetching activity: {e}")
        return jsonify({"error": "Failed to fetch activity"}), 500

@activities_bp.route("/activities/<int:activity_id>", methods=["PUT"])
@token_required
def update_activity(activity_id):
    data = request.get_json()
    current_user = request.current_user
    try:
        response = supabase.table("activities").update(data).eq("id", activity_id).eq("user_id", current_user["id"]).execute()
        if response.data:
            return jsonify({"message": "Activity updated"}), 200
        else:
            return jsonify({"error": "Activity not found or unauthorized"}), 404
    except Exception as e:
        print(f"Error updating activity: {e}")
        return jsonify({"error": "Failed to update activity"}), 500

@activities_bp.route("/activities/<int:activity_id>", methods=["DELETE"])
@token_required
def delete_activity(activity_id):
    current_user = request.current_user
    try:
        response = supabase.table("activities").delete().eq("id", activity_id).eq("user_id", current_user["id"]).execute()
        if response.data:
            return jsonify({"message": "Activity deleted"}), 200
        else:
            return jsonify({"error": "Activity not found or unauthorized"}), 404
    except Exception as e:
        print(f"Error deleting activity: {e}")
        return jsonify({"error": "Failed to delete activity"}), 500