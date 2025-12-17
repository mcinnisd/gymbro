from app import create_app
from app.garmin.sync import init_garmin_api_for_user
import json
import os

app = create_app()

with app.app_context():
    # res = supabase.table("users").select("id").eq("username", "test1111").execute()
    # if res.data:
    #     user_id = res.data[0]["id"]
    user_id = "9" # auth_test_user_v2
    print(f"User ID: {user_id}")
    
    encryption_key = app.config.get("ENCRYPTION_KEY")
    api = init_garmin_api_for_user(user_id, encryption_key)
    
    if api:
        # Fetch sleep for a known date
        date = "2025-12-06" 
        print(f"Fetching sleep for {date}...")
        sleep_data = api.get_sleep_data(date)
        
        print("Top Level Keys:", sleep_data.keys())
        if "sleepLevels" in sleep_data:
            print("Sleep Levels Count:", len(sleep_data["sleepLevels"]))
            if len(sleep_data["sleepLevels"]) > 0:
                print("Sample Level:", sleep_data["sleepLevels"][0])
                
        if "dailySleepDTO" in sleep_data:
            print("DTO Keys:", sleep_data["dailySleepDTO"].keys())
            
        # Check available methods
        print("\nAPI Methods:")
        print([m for m in dir(api) if "sleep" in m.lower()])
            
    else:
        print("User not found")
