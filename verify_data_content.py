import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def verify_data():
    print("--- Verifying Garmin Data Content ---")
    
    # 1. Check Daily Data (Steps, HR)
    print("\n1. Checking 'garmin_daily' table...")
    response = supabase.table("garmin_daily").select("*").order("date", desc=True).limit(3).execute()
    if response.data:
        for row in response.data:
            print(f"Date: {row['date']}")
            print(f"  - Steps Raw: {type(row.get('steps'))} - {str(row.get('steps'))[:100]}...")
            print(f"  - HR Raw: {type(row.get('heartrate'))} - {str(row.get('heartrate'))[:100]}...")
    else:
        print("  No data found in 'garmin_daily'.")

    # 2. Check Sleep Data
    print("\n2. Checking 'garmin_sleep' table...")
    response = supabase.table("garmin_sleep").select("*").order("date", desc=True).limit(3).execute()
    if response.data:
        for row in response.data:
            print(f"Date: {row['date']}")
            print(f"  - Sleep Data Raw: {type(row.get('sleep_data'))} - {str(row.get('sleep_data'))[:100]}...")
    else:
        print("  No data found in 'garmin_sleep'.")

    # 3. Check Activities (Details)
    print("\n3. Checking 'garmin_activities' table...")
    # Find "Santa Monica"
    response = supabase.table("garmin_activities").select("*").ilike("activity_name", "%Santa Monica%").execute()
    if response.data:
        row = response.data[0]
        print(f"Activity: {row.get('activity_name')} (ID: {row.get('activity_id')})")
    else:
        print("  Activity 'Santa Monica' not found.")

    # Check Sleep
    print("\n4. Checking 'garmin_sleep' table...")
    # Check for user 9
    response = supabase.table("garmin_sleep").select("*").eq("user_id", 9).order("date", desc=True).limit(3).execute()
    if response.data:
        for row in response.data:
            print(f"Date: {row['date']}")
            sleep_data = row.get("sleep_data") or {}
            dto = sleep_data.get("dailySleepDTO") or {}
            levels = dto.get("sleepLevels") or []
            print(f"  - Sleep Levels Count: {len(levels)}")
            if levels:
                print(f"  - Sample Level: {levels[0]}")
    else:
        print("  No sleep data found.")

if __name__ == "__main__":
    verify_data()
