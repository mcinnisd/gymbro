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
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "true":
        return jsonify({"url": url}), 200
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
        # Get existing goals to avoid overwriting
        user_res = supabase.table("users").select("goals").eq("id", user_id).execute()
        current_goals = {}
        if user_res.data:
            current_goals = user_res.data[0].get("goals") or {}
            
        current_goals["strava_scope"] = scope
        current_goals["strava_athlete"] = athlete_info

        supabase.table("users").update({
            "strava_access_token": access_token,
            "strava_refresh_token": refresh_token,
            "strava_last_updated": datetime.now(timezone.utc).isoformat(),
            "goals": current_goals
        }).eq("id", user_id).execute()
    except Exception as e:
        print(f"Error updating user tokens: {e}")
        return "Failed to update user tokens.", 500

    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Strava Connected</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0A0E17; color: #F8FAFC; text-align: center; padding: 50px 20px; }
        .card { background: #1E293B; border-radius: 16px; border: 1px solid #334155; padding: 32px; max-width: 400px; margin: 0 auto; }
        h1 { color: #FC4C02; margin-bottom: 12px; font-size: 22px; font-weight: bold; }
        p { color: #94A3B8; font-size: 14px; line-height: 1.5; margin-bottom: 20px; }
        .btn { display: inline-block; padding: 12px 24px; background: #FC4C02; color: #FFFFFF; text-decoration: none; font-weight: bold; border-radius: 8px; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>✅ Strava Account Connected!</h1>
        <p>Your Strava runs and activities are now linked with Coach Bro. You can return to the app.</p>
        <a class="btn" href="gymbro://">Return to GYMBro App</a>
      </div>
      <script>
        setTimeout(function() {
          try { window.location.href = "gymbro://"; } catch (e) {}
        }, 1500);
      </script>
    </body>
    </html>
    """, 200, {'Content-Type': 'text/html'}