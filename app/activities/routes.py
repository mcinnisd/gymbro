# app/activities/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId

from app.extensions import mongo
from app.utils.helpers import mongo_to_dict

activities_bp = Blueprint('activities', __name__)

def token_required(f):
    """
    Custom decorator using Flask-JWT-Extended to protect routes.
    """
    from functools import wraps
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        current_user_id = get_jwt_identity()
        current_user = mongo.db.users.find_one({"_id": ObjectId(current_user_id)})
        if not current_user:
            return jsonify({"error": "User not found!"}), 401
        # Attach current_user to the request context
        request.current_user = current_user
        return f(*args, **kwargs)
    return decorated

@activities_bp.route("/activities", methods=["POST"])
@token_required
def create_activity():
    """
    Endpoint: POST /activities
    Body: JSON with activity details
    Returns: JSON with success message and activity ID
    """
    data = request.json
    required_fields = ["activity_id", "name", "type", "distance", "moving_time", "elapsed_time",
                       "total_elevation_gain", "start_date_local", "average_speed", "max_speed", "calories"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    current_user = request.current_user
    data["user_id"] = str(current_user["_id"])

    try:
        result = mongo.db.activities.insert_one(data)
        return jsonify({"message": "Activity created", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Error creating activity: {e}")
        return jsonify({"error": "Failed to create activity"}), 500

@activities_bp.route("/activities", methods=["GET"])
@token_required
def get_activities():
    """
    Endpoint: GET /activities
    Returns: JSON list of user's activities
    """
    current_user = request.current_user
    try:
        docs = mongo.db.activities.find({"user_id": str(current_user["_id"])})
        return jsonify([mongo_to_dict(doc) for doc in docs]), 200
    except Exception as e:
        print(f"Error fetching activities: {e}")
        return jsonify({"error": "Failed to fetch activities"}), 500

@activities_bp.route("/activities/<object_id>", methods=["GET"])
@token_required
def get_activity_by_id(object_id):
    """
    Endpoint: GET /activities/<object_id>
    Returns: JSON with specific activity details
    """
    current_user = request.current_user
    try:
        doc = mongo.db.activities.find_one({"_id": ObjectId(object_id), "user_id": str(current_user["_id"])})
        if not doc:
            return jsonify({"error": "Activity not found"}), 404
        return jsonify(mongo_to_dict(doc)), 200
    except Exception as e:
        print(f"Error fetching activity: {e}")
        return jsonify({"error": "Failed to fetch activity"}), 500

@activities_bp.route("/activities/<object_id>", methods=["PUT"])
@token_required
def update_activity(object_id):
    """
    Endpoint: PUT /activities/<object_id>
    Body: JSON with fields to update
    Returns: JSON with success message
    """
    data = request.json
    current_user = request.current_user
    try:
        result = mongo.db.activities.update_one(
            {"_id": ObjectId(object_id), "user_id": str(current_user["_id"])},
            {"$set": data}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Activity not found or unauthorized"}), 404
        return jsonify({"message": "Activity updated"}), 200
    except Exception as e:
        print(f"Error updating activity: {e}")
        return jsonify({"error": "Failed to update activity"}), 500

@activities_bp.route("/activities/<object_id>", methods=["DELETE"])
@token_required
def delete_activity(object_id):
    """
    Endpoint: DELETE /activities/<object_id>
    Returns: JSON with success message
    """
    current_user = request.current_user
    try:
        result = mongo.db.activities.delete_one({"_id": ObjectId(object_id), "user_id": str(current_user["_id"])})
        if result.deleted_count == 0:
            return jsonify({"error": "Activity not found or unauthorized"}), 404
        return jsonify({"message": "Activity deleted"}), 200
    except Exception as e:
        print(f"Error deleting activity: {e}")
        return jsonify({"error": "Failed to delete activity"}), 500
