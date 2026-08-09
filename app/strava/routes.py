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

    # Default to 302 HTTP redirect for mobile deep-linking and browser flow
    return redirect(redirect_url, code=302)