import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

SOURCE_USER_ID = 9
TARGET_USERNAME = "auth_test_user_v2"

def copy_data():
    print(f"--- Copying Data from User {SOURCE_USER_ID} to {TARGET_USERNAME} ---")
    
    # 1. Get Target User ID
    resp = supabase.table("users").select("id").eq("username", TARGET_USERNAME).execute()
    if not resp.data:
        print(f"Target user {TARGET_USERNAME} not found!")
        return
    target_user_id = resp.data[0]['id']
    print(f"Target User ID: {target_user_id}")
    
    # 2. Copy Activities
    print("Copying Activities...")
    activities = supabase.table("garmin_activities").select("*").eq("user_id", SOURCE_USER_ID).limit(50).execute()
    if activities.data:
        new_activities = []
        for act in activities.data:
            new_act = act.copy()
            new_act['user_id'] = target_user_id
            del new_act['id'] # Let DB generate ID
            # Ensure unique activity_id if there's a constraint, or just append suffix
            new_act['activity_id'] = f"{act['activity_id']}_test"
            new_activities.append(new_act)
        
        # Insert in batches if needed, but 50 is fine
        try:
            supabase.table("garmin_activities").insert(new_activities).execute()
            print(f"Copied {len(new_activities)} activities.")
        except Exception as e:
            print(f"Error copying activities: {e}")

    # 3. Copy Daily Stats
    print("Copying Daily Stats...")
    dailies = supabase.table("garmin_daily").select("*").eq("user_id", SOURCE_USER_ID).limit(10).execute()
    if dailies.data:
        new_dailies = []
        for d in dailies.data:
            new_d = d.copy()
            new_d['user_id'] = target_user_id
            del new_d['id']
            new_dailies.append(new_d)
        try:
            supabase.table("garmin_daily").insert(new_dailies).execute()
            print(f"Copied {len(new_dailies)} daily stats.")
        except Exception as e:
            print(f"Error copying daily stats: {e}")

    # 4. Copy Sleep Data
    print("Copying Sleep Data...")
    sleeps = supabase.table("garmin_sleep").select("*").eq("user_id", SOURCE_USER_ID).limit(10).execute()
    if sleeps.data:
        new_sleeps = []
        for s in sleeps.data:
            new_s = s.copy()
            new_s['user_id'] = target_user_id
            del new_s['id']
            new_sleeps.append(new_s)
        try:
            supabase.table("garmin_sleep").insert(new_sleeps).execute()
            print(f"Copied {len(new_sleeps)} sleep records.")
        except Exception as e:
            print(f"Error copying sleep data: {e}")

if __name__ == "__main__":
    copy_data()
