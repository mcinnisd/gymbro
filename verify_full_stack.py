import os
import logging
from app import create_app
from app.garmin.sync import sync_all_garmin_data_for_user, store_garmin_credentials
from app.utils.encryption import encrypt_data
from app.supabase_client import supabase
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_full_flow():
    app = create_app()
    with app.app_context():
        # 1. Verify Supabase Connection
        sb_url = os.getenv("SUPABASE_URL")
        logger.info(f"Testing Supabase Connection to: {sb_url}")
        try:
            # Simple query
            res = supabase.table("users").select("count", count="exact").execute()
            logger.info(f"Supabase Connection: SUCCESS (User count: {res.count})")
        except Exception as e:
            logger.error(f"Supabase Connection: FAILED - {e}")
            return

        # 2. Get Credentials
        email = os.getenv("GARMIN_ID") or os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        
        if not email or not password:
            logger.error("Missing GARMIN_ID/EMAIL or GARMIN_PASSWORD in .env")
            return

        # 3. Setup/Get Test User
        test_username = "garmin_integration_user"
        res = supabase.table("users").select("*").eq("username", test_username).execute()
        if res.data:
            user_id = res.data[0]["id"]
            logger.info(f"Using existing user ID: {user_id}")
        else:
            logger.info("Creating test user...")
            user_data = {
                "username": test_username,
                "password": "hashed_placeholder",
                "created_at": "now()",
                "goals": {}
            }
            res = supabase.table("users").insert(user_data).execute()
            user_id = res.data[0]["id"]
            logger.info(f"Created user ID: {user_id}")

        # 4. Store Credentials
        try:
            encrypted_pw = encrypt_data(password)
            store_garmin_credentials(user_id, email, encrypted_pw)
        except Exception as e:
            logger.error(f"Credential storage failed: {e}")
            return

        # 5. Run Sync
        try:
            logger.info("Starting Garmin Sync...")
            sync_all_garmin_data_for_user(user_id, days_back=3)
            logger.info("Garmin Sync: COMPLETED")
        except Exception as e:
            logger.error(f"Garmin Sync failed: {e}")
            return

        # 6. Check Data
        act_res = supabase.table("garmin_activities").select("count", count="exact").eq("user_id", user_id).execute()
        logger.info(f"Garmin Activities in DB: {act_res.count}")
        
        daily_res = supabase.table("garmin_daily").select("count", count="exact").eq("user_id", user_id).execute()
        logger.info(f"Garmin Daily Records in DB: {daily_res.count}")

if __name__ == "__main__":
    verify_full_flow()
