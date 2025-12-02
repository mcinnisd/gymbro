# app/garmin/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from app.utils.encryption import encrypt_data  # decrypt not used here
from app.garmin.sync import store_garmin_credentials, sync_all_garmin_data_for_user
from app.supabase_client import supabase

garmin_bp = Blueprint('garmin', __name__)
logger = logging.getLogger(__name__)

@garmin_bp.route("/connect", methods=["POST"])
@jwt_required()
def connect_garmin():
    """
    Stores Garmin credentials for the authenticated user.
    Credentials are encrypted before storage.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Garmin email and password are required."}), 400

    email = data["email"]
    password = data["password"]

    try:
        encrypted_password = encrypt_data(password)
        store_garmin_credentials(user_id, email, encrypted_password)
        logger.info(f"Garmin credentials stored for user {user_id}.")
        return jsonify({"message": "Garmin credentials stored successfully."}), 200
    except Exception as e:
        logger.error(f"Error storing Garmin credentials for user {user_id}: {e}")
        return jsonify({"error": "Failed to store Garmin credentials."}), 500

@garmin_bp.route("/sync", methods=["POST"])
@jwt_required()
def trigger_garmin_sync():
    """
    Initiates Garmin data synchronization for the authenticated user.
    """
    user_id = get_jwt_identity()
    try:
        sync_all_garmin_data_for_user(user_id)
        logger.info(f"Garmin data sync initiated for user {user_id}.")
        return jsonify({"message": "Garmin data sync initiated."}), 200
    except Exception as e:
        logger.error(f"Error initiating Garmin sync for user {user_id}: {e}")
        return jsonify({"error": "Failed to initiate Garmin sync."}), 500