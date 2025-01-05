# app/scheduler_jobs.py

from flask import current_app
from app.garmin.sync import sync_all_garmin_data_for_user
import logging

logger = logging.getLogger(__name__)

def scheduled_garmin_sync():
    """
    Scheduled task to sync Garmin data for all users daily.
    """
    with current_app.app_context():
        try:
            users = current_app.mongo.db.users.find({
                "garmin_email": {"$exists": True},
                "garmin_password": {"$exists": True}
            })

            for user in users:
                user_id = str(user["_id"])
                try:
                    sync_all_garmin_data_for_user(user_id, days_back=1)  # Sync last day's data
                    logger.info(f"Scheduled Garmin sync completed for user {user_id}.")
                except Exception as e:
                    logger.error(f"Error during scheduled Garmin sync for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Error fetching users for Garmin sync: {e}")