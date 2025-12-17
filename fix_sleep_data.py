from app import create_app
from app.garmin.sync import init_garmin_api_for_user
from app.supabase_client import supabase
import json
import os
from datetime import datetime, timedelta

app = create_app()

def fix_sleep_data():
    with app.app_context():
        # Source User (has credentials)
        source_user_id = "9" 
        
        # Target User (needs data)
        # Get test1111 id
        res = supabase.table("users").select("id").eq("username", "test1111").execute()
        if not res.data:
            print("Target user not found")
            return
        target_user_id = res.data[0]["id"]
        print(f"Target User ID: {target_user_id}")

        encryption_key = app.config.get("ENCRYPTION_KEY")
        api = init_garmin_api_for_user(source_user_id, encryption_key)
        
        if api:
            # Fetch for last 5 days
            dates = ["2025-12-05", "2025-12-06", "2025-12-07"]
            
            for date in dates:
                print(f"Fetching sleep for {date}...")
                try:
                    sleep_data = api.get_sleep_data(date)
                    
                    if "sleepLevels" in sleep_data and len(sleep_data["sleepLevels"]) > 0:
                        print(f"  Found {len(sleep_data['sleepLevels'])} sleep levels.")
                        
                        # Upsert to target user
                        sleep_doc = {
                            "user_id": target_user_id,
                            "date": date,
                            "sleep_data": sleep_data,
                            "synced_at": datetime.now().isoformat(),
                        }
                        supabase.table("garmin_sleep").upsert(sleep_doc, on_conflict="user_id, date").execute()
                        print(f"  Updated DB for {date}")
                    else:
                        print(f"  No sleep levels found for {date}")
                        
                except Exception as e:
                    print(f"  Error fetching/saving for {date}: {e}")
            
        else:
            print("Failed to init API")

if __name__ == "__main__":
    fix_sleep_data()
