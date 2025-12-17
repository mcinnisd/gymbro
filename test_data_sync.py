import os
from app import create_app
from app.extensions import mongo
from app.garmin.sync import sync_all_garmin_data_for_user, store_garmin_credentials
from app.strava.sync import sync_strava_activities
from app.utils.encryption import encrypt_data
from bson import ObjectId
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

def test_sync():
    with app.app_context():
        # 1. Get or Create Test User
        username = "sync_test_user"
        user = mongo.db.users.find_one({"username": username})
        if not user:
            logger.info(f"Creating test user: {username}")
            mongo.db.users.insert_one({"username": username})
            user = mongo.db.users.find_one({"username": username})
        
        user_id = str(user["_id"])
        logger.info(f"Test User ID: {user_id}")

        # 2. Test Garmin Sync
        garmin_email = os.getenv("GARMIN_EMAIL")
        garmin_password = os.getenv("GARMIN_PASSWORD")
        
        if garmin_email and garmin_password:
            logger.info("Found Garmin credentials in .env. Attempting sync...")
            # Store credentials (encrypted)
            encrypted_pw = encrypt_data(garmin_password)
            store_garmin_credentials(user_id, garmin_email, encrypted_pw)
            
            try:
                sync_all_garmin_data_for_user(user_id, days_back=3)
                logger.info("Garmin Sync: SUCCESS")
            except Exception as e:
                logger.error(f"Garmin Sync: FAILED - {e}")
        else:
            logger.warning("No GARMIN_EMAIL or GARMIN_PASSWORD in .env. Skipping Garmin test.")

        # 3. Test Strava Sync
        # Strava requires OAuth tokens. If they are in .env, we can try to inject them.
        strava_refresh = os.getenv("STRAVA_REFRESH_TOKEN")
        
        if strava_refresh:
            logger.info("Found STRAVA_REFRESH_TOKEN in .env. Attempting sync...")
            mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"strava_refresh_token": strava_refresh}}
            )
            
            try:
                sync_strava_activities(user_id)
                logger.info("Strava Sync: SUCCESS")
            except Exception as e:
                logger.error(f"Strava Sync: FAILED - {e}")
        else:
            logger.warning("No STRAVA_REFRESH_TOKEN in .env. Skipping Strava test.")

if __name__ == "__main__":
    test_sync()
