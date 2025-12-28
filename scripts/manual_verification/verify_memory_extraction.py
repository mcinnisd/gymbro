import requests
import json
import time
import sys
from app.supabase_client import supabase

BASE_URL = "http://localhost:5001"
USERNAME = "test1111"
PASSWORD = "test"

def get_token():
    response = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if response.status_code == 200:
        return response.json()["token"]
    print(f"Login failed: {response.status_code} - {response.text}")
    return None

def send_message(token, chat_id, message):
    print(f"Sending: '{message}'")
    headers = {"Authorization": f"Bearer {token}"}
    with requests.post(f"{BASE_URL}/chats/{chat_id}/messages", json={"message": message}, headers=headers, stream=True) as r:
        for line in r.iter_lines():
            pass # Consume stream
    print("Message sent.")

def check_memories(user_id):
    print("Checking memories...")
    # Wait for background task
    for i in range(10):
        time.sleep(2)
        res = supabase.table("memories").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        if res.data:
            mem = res.data[0]
            print(f"Found memory: {mem['content']} (Type: {mem['memory_type']})")
            return True
        print(f"Waiting... ({i+1}/10)")
    return False

if __name__ == "__main__":
    token = get_token()
    if not token:
        sys.exit(1)
        
    # Get user ID (hack: decode token or fetch profile)
    # Fetch profile
    headers = {"Authorization": f"Bearer {token}"}
    # We don't have a direct "whoami" endpoint that returns ID easily without parsing, 
    # but create_chat returns chat_id, and we can query chats table to get user_id if we have supabase client.
    # Actually, we have supabase client here.
    # We need user_id for the check.
    # Let's just fetch the user by username since we know it.
    user_res = supabase.table("users").select("id").eq("username", USERNAME).execute()
    user_id = user_res.data[0]["id"]
    
    # Create chat
    chat_res = requests.post(f"{BASE_URL}/chats/", json={"title": "Extraction Test"}, headers=headers)
    chat_id = chat_res.json().get("chat_id")
    
    # Send a memorable message
    send_message(token, chat_id, "I absolutely love running on trails in the morning, it's my favorite thing.")
    
    # Check if extracted
    if check_memories(user_id):
        print("SUCCESS: Memory extracted!")
    else:
        print("FAILURE: No memory found.")
