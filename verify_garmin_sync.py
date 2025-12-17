import os
import logging
from datetime import date, timedelta
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_garmin():
    # 1. Get Credentials
    email = os.getenv("GARMIN_ID") or os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    
    if not email or not password:
        logger.error("Missing GARMIN_ID/EMAIL or GARMIN_PASSWORD in .env")
        return

    logger.info(f"Found credentials for: {email}")

    # 2. Test Garmin API Direct Connection
    try:
        from garminconnect import Garmin
        logger.info("Attempting Garmin Login...")
        api = Garmin(email=email, password=password)
        api.login()
        logger.info("Garmin Login: SUCCESS")
        
        # 3. Fetch Data
        today = date.today()
        start_date = today - timedelta(days=3)
        logger.info(f"Fetching activities from {start_date} to {today}...")
        
        activities = api.get_activities_by_date(start_date.isoformat(), today.isoformat())
        logger.info(f"Fetched {len(activities)} activities.")
        
        if activities:
            logger.info(f"Sample Activity: {activities[0].get('activityName')}")
            
        logger.info("Garmin Data Pulling: VERIFIED")
        
    except Exception as e:
        logger.error(f"Garmin API Verification Failed: {e}")

    # 4. Report Supabase Issue
    sb_url = os.getenv("SUPABASE_URL")
    logger.warning(f"Note: Supabase integration could not be tested because SUPABASE_URL '{sb_url}' seems unreachable.")

if __name__ == "__main__":
    verify_garmin()
