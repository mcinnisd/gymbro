# app/scheduler_jobs.py
import logging
import os
from app.garmin.sync import sync_all_garmin_data_for_user
from app.strava.sync import sync_strava_activities
from app.analytics.analytics_service import AnalyticsService
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def scheduled_telemetry_sync():
    """
    Scheduled task to orchestrate incremental telemetry synchronization across Garmin Connect
    and Strava accounts for all active users, updating baseline analytics.

    Must be called with mode="incremental". Default sync_all_garmin_data_for_user mode is
    all_time, which would re-backfill the entire archive on every tick.
    """
    if not supabase:
        return

    encryption_key = os.environ.get("ENCRYPTION_KEY")

    try:
        # 1. Sync Garmin users
        try:
            res = supabase.table("users").select(
                "id, garmin_email, garmin_password, garmin_sync_status"
            ).not_.is_("garmin_email", "null").execute()
            garmin_users = res.data or []
            from app.garmin.scope import apply_sync_user_allowlist, parse_sync_user_allowlist

            allow = parse_sync_user_allowlist()
            if allow:
                garmin_users = apply_sync_user_allowlist(garmin_users)
            elif len(garmin_users) > 1:
                ids = ", ".join(str(u.get("id")) for u in garmin_users)
                logger.warning(
                    "Scheduled Garmin sync found multiple connected users (%s). "
                    "Set GYMBRO_GARMIN_SYNC_USER_IDS=2 to scope to the real athlete.",
                    ids,
                )
            for user in garmin_users:
                user_id = str(user["id"])
                if not user.get("garmin_password"):
                    logger.info(f"Skipping scheduled Garmin sync for user {user_id}: credentials incomplete.")
                    continue
                if user.get("garmin_sync_status") == "syncing":
                    logger.info(f"Skipping scheduled Garmin sync for user {user_id}: already syncing.")
                    continue
                try:
                    sync_all_garmin_data_for_user(
                        user_id,
                        days_back=7,
                        encryption_key=encryption_key,
                        mode="incremental",
                    )
                    AnalyticsService.calculate_baselines(user_id)
                    logger.info(f"Scheduled Garmin sync completed for user {user_id}.")
                except Exception as e:
                    logger.error(f"Error during scheduled Garmin sync for user {user_id}: {e}")
        except Exception as ge:
            logger.error(f"Error querying Garmin users for scheduled sync: {ge}")

        # 2. Sync Strava users
        try:
            res_strava = supabase.table("users").select("id").not_.is_("strava_access_token", "null").execute()
            strava_users = res_strava.data or []
            for user in strava_users:
                user_id = str(user["id"])
                try:
                    sync_strava_activities(user_id)
                    AnalyticsService.calculate_baselines(user_id)
                    logger.info(f"Scheduled Strava sync completed for user {user_id}.")
                except Exception as se:
                    logger.error(f"Error during scheduled Strava sync for user {user_id}: {se}")
        except Exception as ste:
            logger.error(f"Error querying Strava users for scheduled sync: {ste}")

    except Exception as e:
        logger.error(f"Critical error in scheduled_telemetry_sync: {e}")

def scheduled_garmin_sync():
    """
    Legacy alias for scheduled telemetry sync.
    """
    scheduled_telemetry_sync()