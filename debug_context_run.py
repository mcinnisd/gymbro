
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from app.supabase_client import supabase
from app.coach.interview_service import _get_garmin_summary

def debug_run():
    print("Fetching user 'testtest'...")
    res = supabase.table("users").select("id").eq("username", "testtest").execute()
    if not res.data:
        print("User not found.")
        return

    user = res.data[0]
    print(f"Testing for ID: {user['id']}")
    
    try:
        summary = _get_garmin_summary(user['id'])
        print("SUCCESS! Output:")
        print(summary)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_run()
