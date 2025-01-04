###############################################################################
# app.py
###############################################################################
import os
import base64
import json
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Flask, redirect, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson import ObjectId
import requests
import jwt

from dotenv import load_dotenv
from openai import OpenAI  # Ensure you have the OpenAI Python package installed

###############################################################################
# 1) Basic Configuration
###############################################################################
# Load environment variables
load_dotenv()

app = Flask(__name__)

# Strava client info
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "YOUR_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_EXPIRATION_MINUTES = int(os.getenv("TOKEN_EXPIRATION_MINUTES", 60))

# Redirect URI for Strava OAuth
REDIRECT_URI = "http://127.0.0.1:5000/exchange_token"

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
client = MongoClient(MONGO_URI)
db = client["gymbro_db"]
activities_collection = db["activities"]
users_collection = db["users"]  # Users will store authentication and Strava tokens
food_logs = db["food_logs"]

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

###############################################################################
# 2) Utility Functions
###############################################################################
def token_required(f):
    """
    Decorator to ensure that the request contains a valid JWT.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # JWT is expected in the Authorization header as Bearer token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]

        if not token:
            return jsonify({"error": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            current_user = users_collection.find_one({"_id": ObjectId(data['user_id'])})
            if not current_user:
                return jsonify({"error": "User not found!"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token!"}), 401

        # Attach current_user to the request context
        request.current_user = current_user
        return f(*args, **kwargs)
    return decorated

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

###############################################################################
# 3) Authentication Endpoints
###############################################################################
@app.route("/register", methods=["POST"])
def register():
    """
    Endpoint: POST /register
    Body: JSON with 'username' and 'password'
    Returns: JSON with success message or error
    """
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400

    username = data["username"]
    password = data["password"]

    if users_collection.find_one({"username": username}):
        return jsonify({"error": "Username already exists."}), 400

    hashed_password = generate_password_hash(password)

    user_doc = {
        "username": username,
        "password": hashed_password,
        "created_at": datetime.now(timezone.utc),
        "access_token": None,
        "refresh_token": None,
        "scope": None,
        "goals": {},  # Initialize empty goals
        "last_updated_goals": None
    }

    try:
        insert_result = users_collection.insert_one(user_doc)
        return jsonify({"message": "User registered successfully."}), 201
    except Exception as e:
        print(f"Error registering user: {e}")
        return jsonify({"error": "Registration failed."}), 500

@app.route("/login", methods=["POST"])
def login():
    """
    Endpoint: POST /login
    Body: JSON with 'username' and 'password'
    Returns: JSON with JWT token or error
    """
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400

    username = data["username"]
    password = data["password"]

    user = users_collection.find_one({"username": username})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password."}), 401

    token_payload = {
        "user_id": str(user["_id"]),
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
    }

    token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return jsonify({"token": token}), 200

###############################################################################
# 4) Strava OAuth Flow
###############################################################################
@app.route("/connect_strava")
@token_required
def connect_strava():
    """
    Initiates the Strava OAuth flow.
    Requires a valid JWT token.
    """
    current_user = request.current_user
    user_id = str(current_user["_id"])
    scope = "read,activity:read_all"
    # Pass user_id along to Strava's URL in the "state" parameter:
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

    # Retrieve user_id from 'state' parameter
    user_id = request.args.get("state")
    if not user_id:
        return "Missing state parameter!", 400

    # Upsert user info (if user already exists, update tokens)
    try:
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "scope": scope,
                    "athlete_info": athlete_info,
                    "last_updated": datetime.now(timezone.utc)
                }
            }
        )
    except Exception as e:
        print(f"Error updating user tokens: {e}")
        return "Failed to update user tokens.", 500

    return jsonify({
        "message": "Authorization successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "scope": scope,
        "athlete_info": athlete_info
    }), 200

###############################################################################
# 5) Syncing Activities
###############################################################################
@app.route("/sync_strava", methods=["POST"])
@token_required
def sync_strava(user_id=None):
    """
    Sync Strava activities for the authenticated user.
    Example usage with cURL:
      curl -X POST -H "Authorization: Bearer <JWT>" http://127.0.0.1:5000/sync_strava
    """
    current_user = request.current_user
    user_id = str(current_user["_id"])
    
    from strava_sync import sync_strava_activities
    try:
        sync_strava_activities(user_id)
        return jsonify({"message": f"Strava activities synced successfully for user {current_user['username']}!"}), 200
    except Exception as e:
        print(f"Error syncing Strava activities: {e}")
        return jsonify({"error": "Failed to sync Strava activities."}), 500

@app.route("/sync_garmin", methods=["POST"])
@token_required
def sync_garmin(user_id=None):
    """
    Sync Garmin data for the authenticated user.
    Example usage with cURL:
      curl -X POST -H "Authorization: Bearer <JWT>" http://127.0.0.1:5000/sync_garmin
    """
    current_user = request.current_user
    user_id = str(current_user["_id"])
    
    from garmin_sync import sync_all_garmin_data_for_user
    try:
        sync_all_garmin_data_for_user(user_id, days_back=7)
        return jsonify({"message": f"Garmin data synced successfully for user {current_user['username']}!"}), 200
    except Exception as e:
        print(f"Error syncing Garmin data: {e}")
        return jsonify({"error": "Failed to sync Garmin data."}), 500

###############################################################################
# 6) CRUD Endpoints for Activities
###############################################################################
@app.route("/activities", methods=["POST"])
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
        result = activities_collection.insert_one(data)
        return jsonify({"message": "Activity created", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Error creating activity: {e}")
        return jsonify({"error": "Failed to create activity"}), 500

@app.route("/activities", methods=["GET"])
@token_required
def get_activities():
    """
    Endpoint: GET /activities
    Returns: JSON list of user's activities
    """
    current_user = request.current_user
    try:
        docs = activities_collection.find({"user_id": str(current_user["_id"])})
        return jsonify([mongo_to_dict(doc) for doc in docs]), 200
    except Exception as e:
        print(f"Error fetching activities: {e}")
        return jsonify({"error": "Failed to fetch activities"}), 500

@app.route("/activities/<object_id>", methods=["GET"])
@token_required
def get_activity_by_id(object_id):
    """
    Endpoint: GET /activities/<object_id>
    Returns: JSON with specific activity details
    """
    current_user = request.current_user
    try:
        doc = activities_collection.find_one({"_id": ObjectId(object_id), "user_id": str(current_user["_id"])})
        if not doc:
            return jsonify({"error": "Activity not found"}), 404
        return jsonify(mongo_to_dict(doc)), 200
    except Exception as e:
        print(f"Error fetching activity: {e}")
        return jsonify({"error": "Failed to fetch activity"}), 500

@app.route("/activities/<object_id>", methods=["PUT"])
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
        result = activities_collection.update_one(
            {"_id": ObjectId(object_id), "user_id": str(current_user["_id"])},
            {"$set": data}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Activity not found or unauthorized"}), 404
        return jsonify({"message": "Activity updated"}), 200
    except Exception as e:
        print(f"Error updating activity: {e}")
        return jsonify({"error": "Failed to update activity"}), 500

@app.route("/activities/<object_id>", methods=["DELETE"])
@token_required
def delete_activity(object_id):
    """
    Endpoint: DELETE /activities/<object_id>
    Returns: JSON with success message
    """
    current_user = request.current_user
    try:
        result = activities_collection.delete_one({"_id": ObjectId(object_id), "user_id": str(current_user["_id"])})
        if result.deleted_count == 0:
            return jsonify({"error": "Activity not found or unauthorized"}), 404
        return jsonify({"message": "Activity deleted"}), 200
    except Exception as e:
        print(f"Error deleting activity: {e}")
        return jsonify({"error": "Failed to delete activity"}), 500

###############################################################################
# 7) User Goals Management
###############################################################################
@app.route("/users/me/goals", methods=["GET"])
@token_required
def get_user_goals():
    """
    Retrieve the authenticated user's goals. Returns defaults if none are set.
    """
    current_user = request.current_user

    default_goals = {
        "steps": 10000,
        "active_calories": 500,
        "weekly_exercise_minutes": 150,
        "sleep_hours": 8
    }
    user_goals = current_user.get("goals", default_goals)
    return jsonify({
        "user_id": current_user["username"],
        "goals": user_goals
    }), 200

@app.route("/users/me/goals", methods=["POST"])
@token_required
def set_user_goals():
    """
    Allows the authenticated user to update their goals.
    JSON body example:
    {
      "steps": 12000,
      "active_calories": 600,
      "weekly_exercise_minutes": 200,
      "sleep_hours": 7.5
    }
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    current_user = request.current_user

    # Merge existing goals with updated ones
    existing_goals = current_user.get("goals", {})
    updated_goals = {**existing_goals, **data}

    try:
        users_collection.update_one(
            {"_id": current_user["_id"]},
            {"$set": {
                "goals": updated_goals,
                "last_updated_goals": datetime.now(timezone.utc)
            }}
        )
        return jsonify({
            "message": "Goals updated successfully.",
            "goals": updated_goals
        }), 200
    except Exception as e:
        print(f"Error updating goals: {e}")
        return jsonify({"error": "Failed to update goals."}), 500

###############################################################################
# 8) Summaries
###############################################################################
@app.route("/users/me/summaries/daily/<date_str>", methods=["POST"])
@token_required
def generate_daily_summary(date_str):
    """
    Generates a daily summary for the authenticated user.
    """
    current_user = request.current_user
    user_id = str(current_user["_id"])

    from summarize import create_daily_summary
    try:
        summary = create_daily_summary(user_id, date_str)
        return jsonify({"message": "Daily summary generated", "summary": summary}), 200
    except Exception as e:
        print(f"Error generating daily summary: {e}")
        return jsonify({"error": "Failed to generate daily summary."}), 500

###############################################################################
# 9) Food Logging Endpoints
###############################################################################
def encode_image(image_bytes):
    """
    Encode image bytes to a base64 string.
    """
    try:
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def get_openai_prediction(encoded_image):
    """
    Send the encoded image to OpenAI and get macro predictions.
    """
    prompt = (
        "You are a professional at analyzing food and predicting the total calories, fat, carbohydrates, and protein within the meal. "
        "Use your superior skills to accurately predict what is contained in the meal in the following image. "
        "Please provide your response in a structured JSON format containing only the following fields without any units: calories, fat, "
        "carbohydrates, and protein. Do not include any additional text, explanations, or formatting."
    )
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Ensure this is the correct model name
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}",
                                "detail": "low"
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None

def clean_response(response_text):
    """
    Clean the response text to extract JSON by removing Markdown code block delimiters.
    """
    if response_text.startswith("```") and response_text.endswith("```"):
        lines = response_text.split('\n')
        if len(lines) >= 3:
            return '\n'.join(lines[1:-1])
    return response_text

def parse_openai_response(response_text):
    """
    Parse the OpenAI JSON response to extract macro estimates.
    """
    try:
        cleaned_response = clean_response(response_text)
        data = json.loads(cleaned_response)
        
        # Normalize keys
        normalized_data = {}
        for key, value in data.items():
            normalized_key = key.split('(')[0].strip().lower()
            normalized_data[normalized_key] = value
        
        # Extract required fields
        calories = normalized_data.get("calories")
        fat = normalized_data.get("fat")
        carbohydrates = normalized_data.get("carbohydrates")
        protein = normalized_data.get("protein")
        
        if None in (calories, fat, carbohydrates, protein):
            print("Missing one or more required fields in the response.")
            return None
        
        return {
            "calories": calories,
            "fat": fat,
            "carbohydrates": carbohydrates,
            "protein": protein
        }
    except json.JSONDecodeError:
        print("Failed to parse response as JSON.")
        return None
    except Exception as e:
        print(f"Error parsing OpenAI response: {e}")
        return None

@app.route("/food_analysis", methods=["POST"])
@token_required
def analyze_food():
    """
    Endpoint: POST /food_analysis
    Headers: Authorization: Bearer <JWT>
    Body: multipart/form-data with 'image' file
    Returns: JSON with estimated macros/calories
    """
    current_user = request.current_user

    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    image_file = request.files["image"]
    image_bytes = image_file.read()
    encoded_image = encode_image(image_bytes)
    
    if not encoded_image:
        return jsonify({"error": "Failed to encode image"}), 500

    # Get prediction from OpenAI
    openai_response = get_openai_prediction(encoded_image)
    
    if not openai_response:
        return jsonify({"error": "Failed to get prediction from OpenAI"}), 500

    # Parse the response to extract macros
    macros = parse_openai_response(openai_response)
    
    if not macros:
        return jsonify({"error": "Failed to parse OpenAI response"}), 500

    # Prepare the document to store in MongoDB
    food_doc = {
        "user_id": str(current_user["_id"]),
        # "image_name": image_file.filename,  # Optionally store the image name
        # "image_data_b64": encoded_image,    # Optionally store the image data
        "analysis_result": macros,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        insert_result = food_logs.insert_one(food_doc)
    except Exception as e:
        print(f"Error inserting into MongoDB: {e}")
        return jsonify({"error": "Failed to store analysis result"}), 500

    return jsonify({
        "message": "Food analysis complete",
        "food_id": str(insert_result.inserted_id),
        "analysis_result": macros
    }), 200

@app.route("/food_logs", methods=["GET"])
@token_required
def get_food_logs():
    """
    Endpoint: GET /food_logs
    Headers: Authorization: Bearer <JWT>
    Returns: JSON list of user's food logs
    """
    current_user = request.current_user
    try:
        logs_cursor = food_logs.find({"user_id": str(current_user["_id"])})
        logs = []
        for log in logs_cursor:
            logs.append({
                "food_id": str(log["_id"]),
                "analysis_result": log["analysis_result"],
                "created_at": log["created_at"]
            })
        return jsonify({"food_logs": logs}), 200
    except Exception as e:
        print(f"Error fetching food logs: {e}")
        return jsonify({"error": "Failed to fetch food logs"}), 500

@app.route("/food_logs/<food_id>", methods=["GET"])
@token_required
def get_food_log(food_id):
    """
    Endpoint: GET /food_logs/<food_id>
    Headers: Authorization: Bearer <JWT>
    Returns: JSON with specific food log details
    """
    current_user = request.current_user
    try:
        log = food_logs.find_one({"_id": ObjectId(food_id), "user_id": str(current_user["_id"])})
        if not log:
            return jsonify({"error": "Food log not found."}), 404
        
        return jsonify({
            "food_id": str(log["_id"]),
            "analysis_result": log["analysis_result"],
            "created_at": log["created_at"]
        }), 200
    except Exception as e:
        print(f"Error fetching food log: {e}")
        return jsonify({"error": "Failed to fetch food log"}), 500

###############################################################################
# 10) Food Logging Utility Functions (Optional: Modularize)
###############################################################################
# For better maintainability, consider moving the following utility functions
# to a separate module (e.g., food_logging.py) and importing them here.

###############################################################################
# 11) Run the Flask App
###############################################################################
if __name__ == "__main__":
    app.run(debug=True)