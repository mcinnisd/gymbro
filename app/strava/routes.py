# app/strava/routes.py

from flask import Blueprint, redirect, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import requests
from bson import ObjectId
from datetime import datetime, timezone, UTC

from app.extensions import mongo
from app.config import Config

strava_bp = Blueprint('strava', __name__)

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

@strava_bp.route("/connect_strava")
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
        f"?client_id={Config.STRAVA_CLIENT_ID}"
        f"&redirect_uri={Config.REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&approval_prompt=force"
        f"&state={user_id}"
    )
    return redirect(url)

@strava_bp.route("/exchange_token")
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
        "client_id": Config.STRAVA_CLIENT_ID,
        "client_secret": Config.STRAVA_CLIENT_SECRET,
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
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "scope": scope,
                    "athlete_info": athlete_info,
                    "last_updated": datetime.now(UTC)
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
