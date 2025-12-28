import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def verify_db_state():
    print("--- Verifying DB State ---")
    
    # 1. Check Activity Details
    print("\n1. Checking 'garmin_activities' for 'details'...")
    try:
        response = supabase.table("garmin_activities").select("activity_id, activity_name, details").order("start_time_local", desc=True).limit(3).execute()
        if response.data:
            for row in response.data:
                has_details = row.get('details') is not None
                details_len = len(str(row.get('details'))) if has_details else 0
                print(f"Activity: {row.get('activity_name')} | ID: {row.get('activity_id')} | Has Details: {has_details} | Size: {details_len}")
                if has_details:
                    # Check for metrics key
                    details = row.get('details')
                    if isinstance(details, dict):
                        print(f"  - Keys: {list(details.keys())}")
                        if "metrics" in details:
                             print(f"  - Metrics Count: {len(details['metrics'])}")
        else:
            print("  No activities found.")
    except Exception as e:
        print(f"  Error querying details: {e}")

    # 2. Check Sleep Data
    print("\n2. Checking 'garmin_sleep'...")
    response = supabase.table("garmin_sleep").select("date, sleep_data").order("date", desc=True).limit(3).execute()
    if response.data:
        for row in response.data:
            print(f"Date: {row['date']} | Has Data: {row.get('sleep_data') is not None}")
    else:
        print("  No sleep data found.")

if __name__ == "__main__":
    verify_db_state()
