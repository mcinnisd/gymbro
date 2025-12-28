import requests
import json
from datetime import datetime, timedelta
import time

BASE_URL = "http://localhost:5001"
USERNAME = f"testuser_{int(time.time())}"
PASSWORD = "test"

def get_token():
    # Try registering first
    reg_data = {"username": USERNAME, "password": PASSWORD, "email": "testXXX@example.com"}
    try:
        requests.post(f"{BASE_URL}/auth/register", json=reg_data)
        # Verify with login
        response = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if response.status_code == 200:
            return response.json().get("token")
        print(f"Login failed: {response.text}")
        return None
    except Exception as e:
        print(f"Login/Register error: {e}")
        return None

def test_calendar_crud(token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create Event
    today = datetime.now().strftime("%Y-%m-%d")
    event_data = {
        "date": today,
        "title": "Test Run",
        "description": "5km easy run",
        "event_type": "run",
        "status": "planned"
    }
    
    print(f"Creating event: {event_data}")
    res = requests.post(f"{BASE_URL}/calendar/events", json=event_data, headers=headers)
    if res.status_code != 201:
        print(f"FAILED to create event: {res.text}")
        return
    
    event_id = res.json()["event"]["id"]
    print(f"Created event ID: {event_id}")
    
    # 2. Get Events
    print("Fetching events...")
    res = requests.get(f"{BASE_URL}/calendar/events", headers=headers)
    events = res.json().get("events", [])
    found = any(e["id"] == event_id for e in events)
    if found:
        print("SUCCESS: Event found in list.")
    else:
        print("FAILURE: Event not found in list.")
        
    # 3. Update Event
    print("Updating event...")
    update_data = {"status": "completed", "description": "Run went great!"}
    res = requests.put(f"{BASE_URL}/calendar/events/{event_id}", json=update_data, headers=headers)
    if res.status_code == 200 and res.json()["event"]["status"] == "completed":
        print("SUCCESS: Event updated.")
    else:
        print(f"FAILURE to update event: {res.text}")
        
    # 4. Delete Event
    print("Deleting event...")
    res = requests.delete(f"{BASE_URL}/calendar/events/{event_id}", headers=headers)
    if res.status_code == 200:
        print("SUCCESS: Event deleted.")
    else:
        print(f"FAILURE to delete event: {res.text}")

if __name__ == "__main__":
    token = get_token()
    if token:
        test_calendar_crud(token)
