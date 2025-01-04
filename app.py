###############################################################################
# app.py
###############################################################################
from flask import Flask, redirect, request, jsonify
import requests
import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, UTC

###############################################################################
# 1) Basic Configuration
###############################################################################
app = Flask(__name__)

# Strava client info (preferably set via environment variables)
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "YOUR_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

# For local dev, set your Strava callback domain to 'localhost' or '127.0.0.1'
# in Strava's developer settings, and ensure this matches:
REDIRECT_URI = "http://127.0.0.1:5000/exchange_token"

# MongoDB setup
client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["gymbro_db"]
activities_collection = db["activities"]
users_collection = db["users"]  # We'll store user tokens here

#######################
# HTTP Endpoints
#######################
@app.route("/users", methods=["POST"])
def create_user():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    existing_user = users_collection.find_one({"user_id": user_id})
    if existing_user:
        return jsonify({"error": f"User '{user_id}' already exists"}), 400

    users_collection.insert_one({
        "user_id": user_id,
        "created_at": datetime.now(UTC),
        "access_token": None,
        "refresh_token": None,
        "scope": None
    })
    return jsonify({"message": f"Created user '{user_id}'"}), 201

###############################################################################
# 2) OAuth Flow with Strava
###############################################################################
@app.route("/connect_strava")
def connect_strava():
    user_id = request.args.get("user_id", "defaultuser")
    scope = "read,activity:read_all"
    # Now pass user_id along to Strava's URL in the "state" parameter:
    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&approval_prompt=force"
        f"&state={user_id}"
    )
    return redirect(url)

@app.route("/exchange_token")
def exchange_token():
    """
    Strava sends ?code=XYZ here after the user authorizes or denies.
    We exchange the code for an access token & refresh token and store them.
    """

    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return f"User denied access or error occurred: {error}", 400
    if not code:
        return "No code returned from Strava!", 400

    # Exchange the code for tokens
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        return f"Error exchanging token: {response.text}", 400

    token_data = response.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    scope = token_data.get("scope", "")
    athlete_info = token_data.get("athlete", {})

    # For simplicity, assume "one user" or store by user ID if multi-user
    # user_id = "mcinnisd"
    user_id = request.args.get("state", "defaultuser")

    # Upsert user info (if user already exists, update tokens)
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "scope": scope,
                "athlete_info": athlete_info,
                "last_updated": datetime.now(UTC)
            }
        },
        upsert=True
    )

    return jsonify({
        "message": "Authorization successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "scope": scope,
        "athlete_info": athlete_info
    })

###############################################################################
# 3) Syncing Activities
###############################################################################
@app.route("/sync_strava/<user_id>", methods=["GET"])
def manual_sync(user_id):
    """
    Example usage:
      curl http://127.0.0.1:5000/sync_strava/mynewuser
    """
    from strava_sync import sync_strava_activities
    sync_strava_activities(user_id)
    return f"Strava activities synced successfully for user {user_id}!", 200

@app.route("/sync_garmin/<user_id>")
def manual_sync_garmin(user_id):
    from garmin_sync import sync_all_garmin_data_for_user
    sync_all_garmin_data_for_user(user_id, days_back=7)
    return f"Garmin data synced for user {user_id}", 200

###############################################################################
# 4) CRUD Endpoints
###############################################################################
def mongo_to_dict(doc):
    """Helper to convert MongoDB document to JSON-serializable dict."""
    return {
        "id": str(doc["_id"]),
        "activity_id": doc.get("activity_id"),
        "name": doc.get("name"),
        "type": doc.get("type"),
        "distance": doc.get("distance"),
        "moving_time": doc.get("moving_time"),
        "elapsed_time": doc.get("elapsed_time"),
        "total_elevation_gain": doc.get("total_elevation_gain"),
        "start_date_local": doc.get("start_date_local"),
        "average_speed": doc.get("average_speed"),
        "max_speed": doc.get("max_speed"),
        "calories": doc.get("calories"),
        "user_id": doc.get("user_id"),
        "raw_data": doc.get("raw_data"),
    }

@app.route("/activities", methods=["POST"])
def create_activity():
    data = request.json
    if "activity_id" not in data or "user_id" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    result = activities_collection.insert_one(data)
    return jsonify({"message": "Activity created", "id": str(result.inserted_id)}), 201

@app.route("/activities", methods=["GET"])
def get_activities():
    docs = activities_collection.find({})
    return jsonify([mongo_to_dict(doc) for doc in docs]), 200

@app.route("/activities/<object_id>", methods=["GET"])
def get_activity_by_id(object_id):
    doc = activities_collection.find_one({"_id": ObjectId(object_id)})
    if not doc:
        return jsonify({"error": "Activity not found"}), 404
    return jsonify(mongo_to_dict(doc)), 200

@app.route("/activities/<object_id>", methods=["PUT"])
def update_activity(object_id):
    data = request.json
    result = activities_collection.update_one({"_id": ObjectId(object_id)}, {"$set": data})
    if result.matched_count == 0:
        return jsonify({"error": "Activity not found"}), 404
    return jsonify({"message": "Activity updated"}), 200

@app.route("/activities/<object_id>", methods=["DELETE"])
def delete_activity(object_id):
    result = activities_collection.delete_one({"_id": ObjectId(object_id)})
    if result.deleted_count == 0:
        return jsonify({"error": "Activity not found"}), 404
    return jsonify({"message": "Activity deleted"}), 200

###############################################################################
# Setting user goals
###############################################################################
@app.route("/users/<user_id>/goals", methods=["GET"])
def get_user_goals(user_id):
    """
    Retrieve a user's goals. Returns defaults if none are set.
    """
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        return jsonify({"error": f"User '{user_id}' not found"}), 404

    default_goals = {
        "steps": 10000,
        "active_calories": 500,
        "weekly_exercise_minutes": 150,
        "sleep_hours": 8
    }
    user_goals = user.get("goals", default_goals)
    return jsonify({
        "user_id": user_id,
        "goals": user_goals
    }), 200

@app.route("/users/<user_id>/goals", methods=["POST"])
def set_user_goals(user_id):
    """
    Allows users to update their goals.
    JSON body example:
    {
      "steps": 12000,
      "active_calories": 600,
      "weekly_exercise_minutes": 200,
      "sleep_hours": 7.5
    }
    """
    data = request.json
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        return jsonify({"error": f"User '{user_id}' not found"}), 404

    # Merge existing goals with updated ones
    existing_goals = user.get("goals", {})
    updated_goals = {**existing_goals, **data}

    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "goals": updated_goals,
            "last_updated_goals": datetime.now(UTC)
        }}
    )

    return jsonify({
        "message": f"Goals updated for user '{user_id}'",
        "goals": updated_goals
    }), 200

###############################################################################
# Summarize
###############################################################################
@app.route("/users/<user_id>/summaries/daily/<date_str>", methods=["POST"])
def generate_daily_summary(user_id, date_str):
    from summarize import create_daily_summary
    summary = create_daily_summary(user_id, date_str)
    return jsonify({"message": "Daily summary generated", "summary": summary}), 200

###############################################################################
# Run the Flask App
###############################################################################
if __name__ == "__main__":
    app.run(debug=True)