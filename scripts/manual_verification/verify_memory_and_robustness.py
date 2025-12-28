import requests
import json
import sys
from app.context.memory_service import MemoryService

BASE_URL = "http://localhost:5001"
USERNAME = "test1111"
PASSWORD = "test"
USER_ID = 13 # Assuming test1111 is 13, but I should fetch it or just use MemoryService with known ID if possible.
# Actually, I need to login to get token, then use token to chat.
# MemoryService runs on backend, so I can use it directly if I run this script in app context.

def get_token():
    # Try login first
    response = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if response.status_code == 200:
        return response.json()["token"]
    print(f"Login failed: {response.status_code} - {response.text}")
    return None

def test_streaming(token, chat_id, message):
    print(f"\nSending message: '{message}'")
    headers = {"Authorization": f"Bearer {token}"}
    
    with requests.post(f"{BASE_URL}/chats/{chat_id}/messages", json={"message": message}, headers=headers, stream=True) as r:
        if r.status_code != 200:
            print(f"Error: {r.status_code} - {r.text}")
            return

        print("--- Stream Start ---")
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data_str = decoded_line[6:]
                    try:
                        data = json.loads(data_str)
                        if 'token' in data:
                            print(data['token'], end='', flush=True)
                        elif 'status' in data:
                            print(f"\n[STATUS] {data['status']}")
                        elif 'chart' in data:
                            print(f"\n\n[CHART] Generated {data['chart']['type']} chart")
                        elif 'done' in data:
                            print("\n[DONE]")
                        elif 'error' in data:
                            print(f"\nError communicating with Local Coach: {data['error']}")
                    except json.JSONDecodeError:
                        pass
        print("\n--- Stream End ---")

if __name__ == "__main__":
    # 1. Setup Memory (Directly via Service)
    # Need to run in app context or just insert via Supabase client if configured
    # Since I'm running this script locally where app code is, I can import
    try:
        # Add a memory
        print("Adding test memory...")
        # I need to know the UUID for test1111.
        # I'll use list_users.py logic or just assume I can get it from login?
        # Login returns access_token.
        # I'll use a hack: I'll ask the bot to remember something later.
        # But for now, I'll just test the chart robustness first.
        pass
    except Exception as e:
        print(f"Failed to setup memory: {e}")

    token = get_token()
    if not token:
        print("Failed to login")
        sys.exit(1)

    # Create chat
    headers = {"Authorization": f"Bearer {token}"}
    chat_res = requests.post(f"{BASE_URL}/chats/", json={"title": "Memory Test"}, headers=headers)
    chat_id = chat_res.json().get("chat_id")
    
    if not chat_id:
        # Fallback to fetching existing
        chats = requests.get(f"{BASE_URL}/chats/", headers=headers).json().get("chats", [])
        if chats:
            chat_id = chats[0]["id"]
        else:
            print("No chat found")
            sys.exit(1)

    # Test 1: Chart Robustness
    test_streaming(token, chat_id, "Chart my heart rate from my run")
    
    # Test 2: Context Check (Implicitly checks if it crashes)
    test_streaming(token, chat_id, "What have I been doing recently?")
