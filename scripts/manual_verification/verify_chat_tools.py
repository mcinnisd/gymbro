import requests
import json
import time

BASE_URL = "http://localhost:5001"
USERNAME = "test1111"
PASSWORD = "test"

def get_token():
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if res.status_code == 200:
        return res.json()["token"]
    else:
        print(f"Login failed: {res.text}")
        return None

def create_chat(token):
    res = requests.post(f"{BASE_URL}/chats", headers={"Authorization": f"Bearer {token}"}, json={"title": "Calendar Test"})
    if res.status_code == 201:
        return res.json()["chat_id"]
    return None

def send_message(token, chat_id, message):
    print(f"\nUser: {message}")
    res = requests.post(
        f"{BASE_URL}/chats/{chat_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message},
        stream=True
    )
    
    full_response = ""
    for line in res.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "token" in data:
                    print(data["token"], end="", flush=True)
                    full_response += data["token"]
                elif "status" in data:
                    print(f"\n[Status: {data['status']}]")
                elif "error" in data:
                    print(f"\n[Error: {data['error']}]")
    print("\n")
    return full_response

def verify():
    token = get_token()
    if not token: return

    chat_id = create_chat(token)
    if not chat_id: return

    # Test 1: Create Event
    send_message(token, chat_id, "Schedule a 5k run for tomorrow called 'Morning Jog'")
    
    # Test 2: Get Events
    send_message(token, chat_id, "What do I have scheduled for tomorrow?")
    
    # Test 3: Update Event (Natural Language)
    send_message(token, chat_id, "Change my Morning Jog to a 10k run")

    # Test 4: Generate Plan (Auto-Planning)
    send_message(token, chat_id, "Create a 4-week marathon training plan for me starting next Monday")

if __name__ == "__main__":
    verify()
