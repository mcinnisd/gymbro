import requests
import json
import time
from datetime import datetime, timedelta
from app.supabase_client import supabase

API_URL = "http://127.0.0.1:5001"
USERNAME = "test1111" # The user we saw earlier with some data
PASSWORD = "password" # Assuming a default password, or I might need to create a new user. 
# Actually, I don't know the password for 'test1111'. 
# I will create a NEW user to ensure I have control and can test the "fresh sync" aspect.
NEW_USER = f"debug_user_{int(time.time())}"
NEW_PASS = "password123"

def run_verification():
    print("--- Checking Database for Existing Users with Garmin Credentials ---")
    
    # Fetch users with garmin_email (simulated filter)
    users = supabase.table("users").select("*").execute()
    garmin_users = [u for u in users.data if u.get("garmin_email")]
    
    print(f"Found {len(garmin_users)} users with Garmin credentials.")
    
    for user in garmin_users:
        user_id = user['id']
        username = user.get('username', 'Unknown')
        goals = user.get('goals') or {}
        last_synced = goals.get('garmin_last_synced')
        
        print(f"\nUser: {username} (ID: {user_id})")
        print(f"  - Last Synced (from goals): {last_synced}")
        
        # Count activities
        activities = supabase.table("garmin_activities").select("count", count="exact").eq("user_id", user_id).execute()
        print(f"  - Total Activities: {activities.count}")
        
        # Count daily stats
        dailies = supabase.table("garmin_daily").select("count", count="exact").eq("user_id", user_id).execute()
        print(f"  - Total Daily Stats: {dailies.count}")
        
        # Check for recent data (last 7 days)
        recent_date = (datetime.now() - timedelta(days=7)).isoformat()
        recent_dailies = supabase.table("garmin_daily").select("*").eq("user_id", user_id).gte("date", recent_date[:10]).execute()
        print(f"  - Daily Stats (Last 7 Days): {len(recent_dailies.data)}")
        if recent_dailies.data:
            print(f"    - Sample Date: {recent_dailies.data[0]['date']}")
            print(f"    - Sample Steps: {recent_dailies.data[0].get('steps')}")

if __name__ == "__main__":
    run_verification()
