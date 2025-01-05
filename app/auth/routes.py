# app/auth/routes.py

from flask import Blueprint, request, jsonify, current_app  # Imported 'current_app'
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from datetime import datetime, timedelta, timezone, UTC
from bson import ObjectId

from app.extensions import mongo
from app.config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["POST"])
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

    if mongo.db.users.find_one({"username": username}):
        return jsonify({"error": "Username already exists."}), 400

    hashed_password = generate_password_hash(password)

    user_doc = {
        "username": username,
        "password": hashed_password,
        "created_at": datetime.now(UTC),
        "access_token": None,
        "refresh_token": None,
        "scope": None,
        "goals": {},  # Initialize empty goals
        "last_updated_goals": None
    }

    try:
        insert_result = mongo.db.users.insert_one(user_doc)
        # Optionally, you can return the user's ID or other info
        return jsonify({"message": "User registered successfully.", "user_id": str(insert_result.inserted_id)}), 201
    except Exception as e:
        current_app.logger.error(f"Error registering user: {e}")  # Use 'current_app' for logging
        return jsonify({"error": "Registration failed."}), 500

@auth_bp.route("/login", methods=["POST"])
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

    user = mongo.db.users.find_one({"username": username})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password."}), 401

    # Using Flask-JWT-Extended's create_access_token
    access_token = create_access_token(identity=str(user["_id"]), expires_delta=timedelta(minutes=Config.TOKEN_EXPIRATION_MINUTES))

    return jsonify({"token": access_token}), 200