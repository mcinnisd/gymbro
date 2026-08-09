# app/strava/routes.py
from flask import Blueprint, redirect, request, jsonify, render_template_string
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from app.supabase_client import supabase
from app.config import Config

strava_bp = Blueprint('strava', __name__)
logger = logging.getLogger(__name__)

def token_required(f):
    from functools import wraps
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
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

from app.strava.service import handle_strava_oauth_callback

@strava_bp.route("/exchange_token")
@strava_bp.route("/callback")
def exchange_token():
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    redirect_url = handle_strava_oauth_callback(code, state, error)

    # If requested via API / JSON
    if request.headers.get("Accept") == "application/json" or request.args.get("json") == "true":
        return jsonify({
            "redirect_url": redirect_url,
            "status": "success" if "status=success" in redirect_url else "error"
        }), 200

    # Render clean HTML landing page for web browsers (supports Expo Go and standalone app links)
    user_agent = request.headers.get("User-Agent", "").lower()
    if "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent:
        html_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Strava Connection - GYMBro</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    background-color: #F8FAFC;
                    color: #0F172A;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    padding: 20px;
                    box-sizing: border-box;
                }}
                .card {{
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 16px;
                    padding: 32px;
                    max-width: 440px;
                    text-align: center;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
                }}
                .icon {{
                    font-size: 48px;
                    margin-bottom: 16px;
                }}
                h1 {{
                    font-size: 22px;
                    font-weight: 700;
                    margin-bottom: 8px;
                }}
                p {{
                    color: #475569;
                    font-size: 14px;
                    line-height: 1.5;
                    margin-bottom: 24px;
                }}
                .btn {{
                    display: inline-block;
                    background-color: #FC4C02;
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 15px;
                    padding: 12px 24px;
                    border-radius: 10px;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">🏃‍♂️🔥</div>
                <h1>Strava Connected Successfully!</h1>
                <p>Your Strava workouts are now synced with <strong>GYMBro</strong>. You can close this window and return to your mobile app.</p>
                <a href="{redirect_url}" class="btn">Return to GYMBro App</a>
            </div>
            <script>
                setTimeout(function() {{
                    window.location.href = "{redirect_url}";
                }}, 1500);
            </script>
        </body>
        </html>
        """
        return render_template_string(html_page), 200

    return redirect(redirect_url, code=302)