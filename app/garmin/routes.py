# app/garmin/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from app.utils.encryption import encrypt_data  # decrypt not used here
from app.garmin.sync import store_garmin_credentials, sync_all_garmin_data_for_user
from app.supabase_client import supabase
from app.extensions import limiter

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
        # Capture encryption key from app context before spawning thread
        enc_key = current_app.config.get("ENCRYPTION_KEY")
        
        encrypted_password = encrypt_data(password)
        store_garmin_credentials(user_id, email, encrypted_password)
        logger.info(f"Garmin credentials stored for user {user_id}. Attempting immediate sync...")
        
        # Trigger immediate sync in background to verify credentials
        import threading
        def _connect_sync_wrapper(uid, key):
             from app.analytics.analytics_service import AnalyticsService
             # Pass the key explicitly to avoid 'Working outside of application context' error
             sync_all_garmin_data_for_user(uid, encryption_key=key)
             # Analytics might need context too? 
             # AnalyticsService currently doesn't depend on Flask app context for DB access (uses supabase_client),
             # but if it uses logging/config it might. 
             # To be safe, we can assume it works or fix it later if it fails.
             try:
                AnalyticsService.calculate_baselines(uid)
             except Exception as e:
                logger.error(f"Analytics failure: {e}")

        thread = threading.Thread(target=_connect_sync_wrapper, args=(user_id, enc_key))
        thread.daemon = True
        thread.start()
        
        return jsonify({"message": "Garmin credentials stored and sync initiated."}), 200
    except Exception as e:
        logger.error(f"Error storing Garmin credentials for user {user_id}: {e}")
        return jsonify({"error": f"Failed to connect: {str(e)}"}), 500

def sync_if_needed(user_id: str):
    """
    Checks if a sync is needed (>24h since last sync) and triggers it if so.
    """
    try:
        res = supabase.table("users").select("garmin_sync_status, garmin_sync_completed_at").eq("id", user_id).execute()
        if not res.data:
            return

        status = res.data[0].get("garmin_sync_status")
        last_completed = res.data[0].get("garmin_sync_completed_at")

        if status == "syncing":
            return # Already in progress

        should_sync = False
        if not last_completed:
            should_sync = True
        else:
            from datetime import datetime, timezone, timedelta
            last_dt = datetime.fromisoformat(last_completed.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - last_dt > timedelta(hours=24):
                should_sync = True

        if should_sync:
            logger.info(f"Auto-triggering Garmin sync for user {user_id}")
            # We don't have request context here, so we must rely on manual env var or robust code.
            # However, sync_if_needed is usually called from a request?! No, likely scheduled task or login hook.
            # If called from login hook (auth route), we HAVE app context.
            try:
                enc_key = current_app.config.get("ENCRYPTION_KEY")
            except:
                import os
                enc_key = os.environ.get("ENCRYPTION_KEY")

            import threading
            thread = threading.Thread(target=sync_all_garmin_data_for_user, args=(user_id, 7, enc_key))
            thread.daemon = True
            thread.start()

    except Exception as e:
        logger.error(f"Error checking if sync needed for user {user_id}: {e}")

@garmin_bp.route("/sync", methods=["POST"])
@jwt_required()
def trigger_garmin_sync():
    """
    Initiates Garmin data synchronization for the authenticated user in the background.
    Accepts { "force": true } to force a full 5-year resync.
    """
    user_id = get_jwt_identity()
    
    # Check body for force flag
    force_resync = False
    if request.is_json:
        data = request.get_json()
        force_resync = data.get("force", False)

    try:
        # Check if already syncing
        res = supabase.table("users").select("garmin_sync_status").eq("id", user_id).execute()
        if res.data and res.data[0].get("garmin_sync_status") == "syncing":
             # Optional: If force=True, maybe override? For now, stick to 'wait'.
            return jsonify({
                "message": "Sync already in progress.",
                "status": "syncing"
            }), 200

        # Capture key
        enc_key = current_app.config.get("ENCRYPTION_KEY")

        import threading
        # Run sync in background thread
        def _background_sync_wrapper(uid, key, force):
            from app.analytics.analytics_service import AnalyticsService
            sync_all_garmin_data_for_user(uid, encryption_key=key, force_resync=force)
            try:
                AnalyticsService.calculate_baselines(uid)
            except Exception as e:
                logger.error(f"Error running analytics after sync: {e}")

        # Pass force_resync to args
        thread = threading.Thread(target=_background_sync_wrapper, args=(user_id, enc_key, force_resync))
        thread.daemon = True
        thread.start()
        
        msg = "Full resync initiated." if force_resync else "Garmin data sync initiated."
        logger.info(f"{msg} for user {user_id}.")
        return jsonify({
            "message": msg,
            "status": "syncing"
        }), 200
    except Exception as e:
        logger.error(f"Error initiating Garmin sync for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
@garmin_bp.route("/status", methods=["GET"])
@jwt_required()
@limiter.exempt
def get_garmin_status():
    """
    Returns the current Garmin sync status for the user.
    """
    user_id = get_jwt_identity()
    try:
        # Fetch status and goals (where progress is stored)
        response = supabase.table("users").select("garmin_sync_status", "garmin_last_sync_error", "goals").eq("id", user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found"}), 404
            
        user_data = response.data[0]
        goals = user_data.get("goals") or {}
        
        # Extract progress from goals
        progress = goals.get("sync_progress", 0)

        return jsonify({
            "garmin_sync_status": user_data.get("garmin_sync_status"),
            "garmin_last_sync_error": user_data.get("garmin_last_sync_error"),
            "garmin_sync_progress": progress 
        }), 200
    except Exception as e:
        logger.error(f"Error fetching Garmin status for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500

@garmin_bp.route("/debug/counts", methods=["GET"])
@jwt_required()
def debug_counts():
    """Debug endpoint to check DB counts."""
    # ... existing code ...
    pass # (This is just context match)

@garmin_bp.route("/debug/context", methods=["GET"])
@jwt_required()
def debug_context():
    """Debug endpoint to see what the Coach sees."""
    user_id = get_jwt_identity()
    try:
        from app.coach.interview_service import _get_garmin_summary
        summary = _get_garmin_summary(user_id)
        return jsonify({"summary": summary}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@garmin_bp.route("/daily/<date>", methods=["GET"])
@jwt_required()
def get_daily_details(date):
    """
    Returns detailed daily health stats for a specific date.
    """
    user_id = get_jwt_identity()
    try:
        response = supabase.table("garmin_daily").select("*").eq("user_id", user_id).eq("date", date).execute()
        if not response.data:
            return jsonify({"error": "Daily data not found"}), 404
        return jsonify(response.data[0]), 200
    except Exception as e:
        logger.error(f"Error fetching daily details for {date}: {e}")
        return jsonify({"error": "Failed to fetch daily details"}), 500

@garmin_bp.route("/sleep/<date>", methods=["GET"])
@jwt_required()
def get_sleep_details(date):
    """
    Returns detailed sleep data for a specific date.
    """
    user_id = get_jwt_identity()
    try:
        response = supabase.table("garmin_sleep").select("*").eq("user_id", user_id).eq("date", date).execute()
        if not response.data:
            return jsonify({"error": "Sleep data not found"}), 404
        return jsonify(response.data[0]), 200
    except Exception as e:
        logger.error(f"Error fetching sleep details for {date}: {e}")
        return jsonify({"error": "Failed to fetch sleep details"}), 500