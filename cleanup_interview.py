import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL or SUPABASE_KEY not found in .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def cleanup_user(username):
    # Get user ID
    res = supabase.table("users").select("id").eq("username", username).execute()
    if not res.data:
        print(f"User {username} not found.")
        return
    
    user_id = res.data[0]["id"]
    print(f"Cleaning up user {username} (ID: {user_id})...")

    # 1. Reset user interview state
    supabase.table("users").update({
        "interview_chat_id": None,
        "coach_status": "not_started",
        "interview_step": 1,
        "training_plan": None,
        "training_plan_phased": None
    }).eq("id", user_id).execute()
    print("- User status reset to 'not_started'.")

    # 2. Delete interview chats
    chats_res = supabase.table("chats").select("id").eq("user_id", user_id).eq("type", "interview").execute()
    if chats_res.data:
        for chat in chats_res.data:
            supabase.table("chats").delete().eq("id", chat["id"]).execute()
            print(f"- Deleted interview chat ID: {chat['id']}")
    else:
        print("- No interview chats found to delete.")

    print("\nCleanup complete! You can now start a fresh interview from the Coach page.")

if __name__ == "__main__":
    username = input("Enter the username to cleanup: ").strip()
    if username:
        cleanup_user(username)
    else:
        print("Username required.")
