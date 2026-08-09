from app.garmin.sync import sync_all_garmin_data_for_user
from app.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

def scheduled_garmin_sync():
    """
    Scheduled task to sync Garmin data for all users daily.
    """
    try:
        res = supabase.table("users").select("id").not_.is_("garmin_email", "null").execute()
        users = res.data or []

        for user in users:
            user_id = str(user["id"])
            try:
                sync_all_garmin_data_for_user(user_id, days_back=1)  # Sync last day's data
                logger.info(f"Scheduled Garmin sync completed for user {user_id}.")
            except Exception as e:
                logger.error(f"Error during scheduled Garmin sync for user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Error fetching users for Garmin sync: {e}")