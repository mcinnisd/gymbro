import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:5001"
USERNAME = "test1111"
PASSWORD = "test"

def login():
    print(f"Logging in as {USERNAME}...")
    response = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if response.status_code == 200:
        token = response.json().get("token")
        print("Login successful.")
        return token
    else:
        print(f"Login failed: {response.text}")
        return None

def create_chat(token):
    print("Creating new chat...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/chats/", json={"title": "Context Test"}, headers=headers)
    if response.status_code == 201:
        chat_id = response.json().get("chat_id")
        print(f"Chat created: {chat_id}")
        return chat_id
    else:
        print(f"Failed to create chat: {response.text}")
        return None

def send_message_and_get_proposal(token, chat_id, message):
    print(f"Sending message: '{message}'")
    headers = {"Authorization": f"Bearer {token}"}
    
    # We need to handle the stream
    with requests.post(f"{BASE_URL}/chats/{chat_id}/messages", json={"message": message}, headers=headers, stream=True) as r:
        if r.status_code != 200:
            print(f"Error sending message: {r.status_code}")
            return None
            
        proposal = None
        full_text = ""
        
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        data = json.loads(decoded_line[6:])
                        if "token" in data:
                            full_text += data["token"]
                        if "proposal" in data:
                            print("Proposal received!")
                            proposal = data["proposal"]
                        if "error" in data:
                            print(f"Stream error: {data['error']}")
                    except Exception as e:
                        pass
        
        print(f"Full response: {full_text}")
        return proposal

def approve_proposal(token, chat_id, proposal):
    print("Approving proposal...")
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "action": proposal["action"],
        "data": proposal["data"]
    }
    
    response = requests.post(f"{BASE_URL}/chats/{chat_id}/actions", json=payload, headers=headers)
    if response.status_code == 200:
        print(f"Action success: {response.json()}")
        return True
    else:
        print(f"Action failed: {response.text}")
        return False

def verify_event(token, date, title):
    print(f"Verifying event '{title}' on {date}...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/calendar/events?start_date={date}&end_date={date}", headers=headers)
    
    if response.status_code == 200:
        events = response.json().get("events", [])
        for e in events:
            if e["title"] == title:
                print("Event found!")
                return True
        print("Event not found.")
        return False
    else:
        print(f"Failed to fetch events: {response.text}")
        return False

def main():
    token = login()
    if not token: return

    chat_id = create_chat(token)
    if not chat_id: return
    
    # 1. Test Proposal Generation
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    msg = f"Schedule a 5k run for tomorrow called 'Test Run'"
    
    proposal = send_message_and_get_proposal(token, chat_id, msg)
    
    if proposal:
        print(f"Proposal Details: {json.dumps(proposal, indent=2)}")
        
        # 2. Test Approval
        if approve_proposal(token, chat_id, proposal):
            # 3. Verify Event
            verify_event(token, tomorrow, "Test Run")
        else:
            print("Skipping verification due to approval failure.")
    else:
        print("No proposal generated. Check LLM output.")

if __name__ == "__main__":
    main()
