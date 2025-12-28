import requests
from app.supabase_client import supabase
from app.config import Config

API_URL = "http://127.0.0.1:5001"

def check_db():
    print("--- Checking Database ---")
    try:
        users = supabase.table("users").select("*").execute()
        print(f"Users found: {len(users.data)}")
        for user in users.data:
            print(f"User: {user['username']} (ID: {user['id']})")
            print(f"  - Garmin Connected: {bool(user.get('garmin_email'))}")
            
            activities = supabase.table("garmin_activities").select("count", count="exact").eq("user_id", user['id']).execute()
            print(f"  - Activities Count: {activities.count}")
            
            dailies = supabase.table("garmin_daily").select("count", count="exact").eq("user_id", user['id']).execute()
            print(f"  - Daily Stats Count: {dailies.count}")

    except Exception as e:
        print(f"DB Check Error: {e}")

def test_login(username, password):
    print(f"\n--- Testing Login for {username} ---")
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={"username": username, "password": password})
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Login Successful!")
            return resp.json().get("token")
        else:
            print(f"Login Failed: {resp.text}")
    except Exception as e:
        print(f"Login Request Error: {e}")
    return None

if __name__ == "__main__":
    check_db()
    # Note: We don't know the password, so we can't fully test login unless we reset it or create a new user.
    # But checking the DB will tell us if the user exists and has data.
