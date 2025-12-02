# app/auth/routes.py
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
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
    return jsonify({"token": access_token}), 200