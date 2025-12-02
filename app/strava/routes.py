# app/strava/routes.py
from flask import Blueprint, redirect, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import requests
from datetime import datetime, timezone
from app.supabase_client import supabase
from app.config import Config

strava_bp = Blueprint('strava', __name__)

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

@strava_bp.route("/connect_strava")
@token_required
def connect_strava():
    current_user = request.current_user
    user_id = current_user["id"]
    scope = "read,activity:read_all"
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
    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return f"User denied access or error occurred: {error}", 400
    if not code:
        return "No code returned from Strava!", 400

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
    user_id = request.args.get("state")
    if not user_id:
        return "Missing state parameter!", 400

    try:
        supabase.table("users").update({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scope": scope,
            "athlete_info": athlete_info,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
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