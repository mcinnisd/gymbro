import requests
import json
import sys

BASE_URL = "http://localhost:5001"
USERNAME = "test1111"
PASSWORD = "test"

def get_token():
    # Try login first
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code == 200:
        # Decode token to get user_id (or just fetch profile)
        token = resp.json()["token"]
        # Fetch profile to get ID
        headers = {"Authorization": f"Bearer {token}"}
        p_resp = requests.get(f"{BASE_URL}/auth/profile", headers=headers)
        # We don't get ID from profile endpoint easily, but we can assume it works if we get 200
        # Actually, let's just register if login fails
        return token, "unknown"

    # Register if login failed
    print("Login failed, trying to register...")
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code == 201:
        # Login again
        resp = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if resp.status_code == 200:
            return resp.json()["token"], resp.json().get("user_id", "unknown")
            
    print(f"Auth failed: {resp.text}")
    sys.exit(1)

def get_chat_id(token, user_id):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/chats", headers=headers)
    chats = resp.json().get("chats", [])
    if chats:
        return chats[0]["id"]
    
    # Create new chat
    resp = requests.post(f"{BASE_URL}/chats", headers=headers, json={"title": "Test Chat"})
    return resp.json()["chat_id"]

def test_streaming(token, chat_id, message):
    print(f"\nSending message: '{message}'")
    headers = {"Authorization": f"Bearer {token}"}
    
    with requests.post(
        f"{BASE_URL}/chats/{chat_id}/messages",
        headers=headers,
        json={"message": message},
        stream=True
    ) as r:
        if r.status_code != 200:
            print(f"Error: {r.status_code} - {r.text}")
            return

        print("--- Stream Start ---")
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data = json.loads(decoded_line[6:])
                    if "status" in data:
                        print(f"[STATUS] {data['status']}")
                    elif "token" in data:
                        print(f"{data['token']}", end="", flush=True)
                    elif "chart" in data:
                        print(f"\n[CHART] Generated {data['chart']['type']} chart")
                    elif "done" in data:
                        print("\n[DONE]")
                    elif "error" in data:
                        print(f"\n[ERROR] {data['error']}")
        print("\n--- Stream End ---")

if __name__ == "__main__":
    token, user_id = get_token()
    chat_id = get_chat_id(token, user_id)
    
    # Test 1: Normal question
    test_streaming(token, chat_id, "How was my last run?")
    
    # Test 2: Chart request (Pace)
    test_streaming(token, chat_id, "Show me a graph of my pace")

    # Test 3: Chart request (Heart Rate)
    test_streaming(token, chat_id, "Plot my heart rate")

    # Test 4: Chart request (Sleep)
    test_streaming(token, chat_id, "Graph my sleep score")

    # Test 5: Activity Chart request (Last Run)
    test_streaming(token, chat_id, "Show me a chart of my last run")
