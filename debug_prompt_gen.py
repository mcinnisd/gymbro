
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getcwd())

from app.supabase_client import supabase
from app.coach.interview_service import _generate_dynamic_response, _get_garmin_summary

def debug_prompt():
    print("Fetching 'testtest'...")
    res = supabase.table("users").select("id").eq("username", "testtest").execute()
    if not res.data: return
    user_id = res.data[0]['id']
    
    print(f"User ID: {user_id}")
    
    # 1. Check Garmin Summary Content
    print("--- Checking Garmin Summary ---")
    summary = _get_garmin_summary(user_id)
    print(f"Summary Len: {len(summary)}")
    print(summary[:200] + "...")
    
    # 2. Check Prompt Context for Step 3
    print("\n--- Checking Step 3 Prompt ---")
    try:
        # This will trigger the print inside the function
        _generate_dynamic_response(user_id, 3, "Debug Context Trigger")
    except Exception as e:
        print(f"Error calling gen response: {e}")

if __name__ == "__main__":
    debug_prompt()
