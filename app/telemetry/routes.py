# app/telemetry/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import threading
from datetime import datetime, timezone, timedelta
from app.supabase_client import supabase
from app.health_hub.ingestion_service import (
    record_daily_biometrics,
    ingest_telemetry_payload,
    get_telemetry_status
)

telemetry_bp = Blueprint('telemetry', __name__)
logger = logging.getLogger(__name__)

@telemetry_bp.route("/sync", methods=["POST"])
@jwt_required()
def sync_telemetry():
    """
    Unified Telemetry Ingestion & Provider Sync Seam.
    Accepts:
    1. Direct Telemetry Payload: { "source": "apple_health", "biometrics": [...], "activities": [...] }
    2. Provider Trigger Sync: { "provider": "all" | "garmin" | "strava", "force": false }
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    # Case 1: Direct telemetry push (HealthKit / mobile client payload)
    if "biometrics" in data or "activities" in data or "resting_hr" in data or "sleep_hours" in data or "steps" in data:
        try:
            result = ingest_telemetry_payload(user_id, data)
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"Error ingesting direct telemetry payload for user {user_id}: {e}")
            return jsonify({"error": f"Failed to ingest telemetry: {str(e)}"}), 500

    # Case 2: Provider background sync trigger
    provider = data.get("provider", "all").lower()
    force_resync = data.get("force", False)
    mode = data.get("mode", "all_time" if force_resync else "deep_365")
    days_back = data.get("days_back", 365 if (force_resync or mode == "deep_365") else 7)
    synced_providers = []

    try:
        enc_key = current_app.config.get("ENCRYPTION_KEY")
        
        # Garmin sync
        if provider in ["all", "garmin"]:
            from app.garmin.sync import sync_all_garmin_data_for_user
            def _garmin_worker(uid, key, days, force, sync_mode):
                try:
                    sync_all_garmin_data_for_user(uid, days_back=days, encryption_key=key, force_resync=force, mode=sync_mode)
                    from app.analytics.analytics_service import AnalyticsService
                    AnalyticsService.calculate_baselines(uid)
                except Exception as g_err:
                    logger.error(f"Garmin background sync error: {g_err}")

            t_garmin = threading.Thread(target=_garmin_worker, args=(user_id, enc_key, days_back, force_resync, mode))
            t_garmin.daemon = True
            t_garmin.start()
            synced_providers.append("garmin")

        # Strava sync
        if provider in ["all", "strava"]:
            from app.strava.sync import sync_strava_activities
            def _strava_worker(uid):
                try:
                    sync_strava_activities(uid)
                    from app.analytics.analytics_service import AnalyticsService
                    AnalyticsService.calculate_baselines(uid)
                except Exception as s_err:
                    logger.error(f"Strava background sync error: {s_err}")

            t_strava = threading.Thread(target=_strava_worker, args=(user_id,))
            t_strava.daemon = True
            t_strava.start()
            synced_providers.append("strava")

        return jsonify({
            "message": "Telemetry synchronization initiated.",
            "status": "syncing",
            "mode": mode,
            "providers": synced_providers,
            "days_back": days_back,
            "force_resync": force_resync
        }), 200

    except Exception as e:
        logger.error(f"Error initiating provider sync for user {user_id}: {e}")
        return jsonify({"error": f"Failed to trigger sync: {str(e)}"}), 500

@telemetry_bp.route("/sync-if-needed", methods=["POST"])
@jwt_required()
def check_and_sync_if_needed():
    """
    Checks if telemetry data for any connected provider (Garmin, Strava) is stale (>15 mins)
    or has never been synced, and initiates non-blocking background synchronization.
    """
    user_id = get_jwt_identity()
    uid = int(user_id) if str(user_id).isdigit() else user_id
    triggered_providers = []

    try:
        # Check user integration status
        res = supabase.table("users").select(
            "id, garmin_email, garmin_password, garmin_sync_status, garmin_sync_completed_at, "
            "strava_access_token, strava_last_updated"
        ).eq("id", uid).execute()

        if not res.data:
            return jsonify({"status": "error", "error": "User not found"}), 404

        u = res.data[0]
        now = datetime.now(timezone.utc)
        debounce_window = timedelta(minutes=15)

        enc_key = current_app.config.get("ENCRYPTION_KEY")

        # 1. Garmin check
        garmin_email = u.get("garmin_email")
        garmin_pass = u.get("garmin_password")
        g_status = u.get("garmin_sync_status")
        g_completed = u.get("garmin_sync_completed_at")

        if garmin_email and garmin_pass and g_status != "syncing":
            should_sync_garmin = False
            is_first_sync = not bool(g_completed)
            if is_first_sync:
                should_sync_garmin = True
            else:
                try:
                    last_g_dt = datetime.fromisoformat(g_completed.replace("Z", "+00:00"))
                    if now - last_g_dt > debounce_window:
                        should_sync_garmin = True
                except Exception:
                    should_sync_garmin = True

            if should_sync_garmin:
                from app.garmin.sync import sync_all_garmin_data_for_user
                days_to_sync = 365 if is_first_sync else 7
                def _garmin_auto(u_id, key, days):
                    try:
                        sync_all_garmin_data_for_user(u_id, days_back=days, encryption_key=key)
                        from app.analytics.analytics_service import AnalyticsService
                        AnalyticsService.calculate_baselines(u_id)
                    except Exception as err:
                        logger.error(f"Auto-sync Garmin error for user {u_id}: {err}")

                t = threading.Thread(target=_garmin_auto, args=(user_id, enc_key, days_to_sync))
                t.daemon = True
                t.start()
                triggered_providers.append("garmin")

        # 2. Strava check
        strava_token = u.get("strava_access_token")
        strava_updated = u.get("strava_last_updated")
        if strava_token:
            should_sync_strava = False
            if not strava_updated:
                should_sync_strava = True
            else:
                try:
                    last_s_dt = datetime.fromisoformat(strava_updated.replace("Z", "+00:00"))
                    if now - last_s_dt > debounce_window:
                        should_sync_strava = True
                except Exception:
                    should_sync_strava = True

            if should_sync_strava:
                from app.strava.sync import sync_strava_activities
                def _strava_auto(u_id):
                    try:
                        sync_strava_activities(u_id)
                        from app.analytics.analytics_service import AnalyticsService
                        AnalyticsService.calculate_baselines(u_id)
                    except Exception as err:
                        logger.error(f"Auto-sync Strava error for user {u_id}: {err}")

                t = threading.Thread(target=_strava_auto, args=(user_id,))
                t.daemon = True
                t.start()
                triggered_providers.append("strava")

        if triggered_providers:
            return jsonify({
                "status": "syncing",
                "triggered": True,
                "providers": triggered_providers,
                "message": f"Auto-sync triggered for {', '.join(triggered_providers)}"
            }), 200
        else:
            return jsonify({
                "status": "fresh",
                "triggered": False,
                "providers": [],
                "message": "Telemetry data is already fresh and up to date."
            }), 200

    except Exception as e:
        logger.error(f"Error checking auto-sync for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500


@telemetry_bp.route("/status", methods=["GET"])
@jwt_required()
def get_status():
    """
    Returns multi-provider telemetry sync status and connection state.
    """
    user_id = get_jwt_identity()
    try:
        status = get_telemetry_status(user_id)
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error retrieving telemetry status for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500

@telemetry_bp.route("/daily", methods=["GET"])
@jwt_required()
def get_daily_biometrics():
    """
    Returns normalized daily biometrics time series from biometrics_daily table.
    Supports query parameters: 'date', 'start_date', 'end_date', 'days'.
    """
    user_id = get_jwt_identity()
    uid = int(user_id) if str(user_id).isdigit() else user_id

    single_date = request.args.get("date")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    days = request.args.get("days", type=int)

    if not supabase:
        return jsonify({"daily_biometrics": []}), 200

    try:
        if single_date:
            res = supabase.table("biometrics_daily").select("*").eq("user_id", uid).eq("date", single_date).execute()
            if res.data:
                return jsonify(res.data[0]), 200
            return jsonify({"error": "No biometric record for date"}), 404

        query = supabase.table("biometrics_daily").select("*").eq("user_id", uid)

        if not start_date and days:
            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        res = query.order("date", desc=False).limit(365).execute()
        return jsonify({"daily_biometrics": res.data or []}), 200

    except Exception as e:
        logger.error(f"Error fetching daily biometrics for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500

@telemetry_bp.route("/biometrics", methods=["POST"])
@jwt_required()
def post_single_biometrics():
    """
    Direct endpoint for posting a single day's biometric telemetry sample.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    try:
        saved = record_daily_biometrics(user_id, data)
        return jsonify({"message": "Biometrics recorded", "data": saved}), 201
    except Exception as e:
        logger.error(f"Error recording biometrics for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
