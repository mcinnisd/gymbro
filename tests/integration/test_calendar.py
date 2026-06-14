import pytest
import requests
import time
import uuid

BASE_URL = "http://127.0.0.1:5001"

@pytest.fixture(scope="module")
def auth_info():
    username = f"cal_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    password = "password123"
    
    # Register
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    user_id = resp.json()["user_id"]
    
    # Login
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["token"]
    
    return {"Authorization": f"Bearer {token}"}, user_id

def test_calendar_lifecycle(auth_info):
    headers, user_id = auth_info
    
    # 1. Create Event
    event_data = {
        "date": "2026-07-01",
        "title": "Long Run 15km",
        "description": "Keep target pace at 5:30/km",
        "event_type": "run",
        "status": "planned"
    }
    
    resp = requests.post(f"{BASE_URL}/calendar/events", json=event_data, headers=headers)
    assert resp.status_code == 201, f"Failed to create event: {resp.text}"
    
    event = resp.json()["event"]
    event_id = event["id"]
    assert event["title"] == "Long Run 15km"
    assert event["event_type"] == "run"
    assert event["status"] == "planned"
    
    # 2. Get Events (Verify listing)
    resp = requests.get(f"{BASE_URL}/calendar/events?start_date=2026-07-01&end_date=2026-07-02", headers=headers)
    assert resp.status_code == 200, f"Failed to list events: {resp.text}"
    events = resp.json()["events"]
    assert len(events) >= 1
    assert any(e["id"] == event_id for e in events)
    
    # 3. Update Event
    update_data = {
        "status": "completed",
        "description": "Completed! Felt strong."
    }
    resp = requests.put(f"{BASE_URL}/calendar/events/{event_id}", json=update_data, headers=headers)
    assert resp.status_code == 200, f"Failed to update event: {resp.text}"
    updated_event = resp.json()["event"]
    assert updated_event["status"] == "completed"
    assert updated_event["description"] == "Completed! Felt strong."
    
    # 4. Delete Event
    resp = requests.delete(f"{BASE_URL}/calendar/events/{event_id}", headers=headers)
    assert resp.status_code == 200, f"Failed to delete event: {resp.text}"
    
    # 5. Verify Deleted
    resp = requests.get(f"{BASE_URL}/calendar/events?start_date=2026-07-01&end_date=2026-07-02", headers=headers)
    assert resp.status_code == 200
    events_after = resp.json()["events"]
    assert not any(e["id"] == event_id for e in events_after)
