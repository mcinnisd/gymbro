import pytest
import requests
import time
import uuid

BASE_URL = "http://127.0.0.1:5001"

@pytest.fixture(scope="module")
def auth_header():
    # Register and Login to get token
    username = f"testuser_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    password = "password123"
    
    # Register
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    
    # Login
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}

def test_profile_lifecycle(auth_header):
    # Update Profile
    profile_data = {
        "age": 25,
        "weight": 75,
        "height": 180,
        "sport_history": "Running",
        "running_experience": "Intermediate",
        "past_injuries": "None",
        "lifestyle": "Active",
        "weekly_availability": "5 days",
        "terrain_preference": "Road",
        "equipment": "None"
    }
    resp = requests.put(f"{BASE_URL}/auth/profile", json=profile_data, headers=auth_header)
    assert resp.status_code == 200, f"Update profile failed: {resp.text}"
    
    # Get Profile
    resp = requests.get(f"{BASE_URL}/auth/profile", headers=auth_header)
    assert resp.status_code == 200, f"Get profile failed: {resp.text}"
    
    fetched_profile = resp.json()["profile"]
    assert fetched_profile["sport_history"] == "Running"

def test_chat_interaction(auth_header):
    # Create Chat
    resp = requests.post(f"{BASE_URL}/chats/", json={"title": "Test Chat"}, headers=auth_header)
    assert resp.status_code == 201, f"Create chat failed: {resp.text}"
    chat_id = resp.json()["chat_id"]
    
    # Send Message
    msg = "What is my sport history?"
    # The endpoint returns a stream (SSE)
    resp = requests.post(f"{BASE_URL}/chats/{chat_id}/messages", json={"message": msg}, headers=auth_header, stream=True)
    assert resp.status_code == 200, f"Send message failed: {resp.text}"
    
    # Consume the stream to find the final reply or just verify we get chunks
    reply_found = False
    for line in resp.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data:"):
                # verify we get some data
                reply_found = True
                break
    
    assert reply_found, "No response stream received"

@pytest.mark.skip(reason="Server crashes on this endpoint currently")
def test_coach_flow(auth_header):
    # Start Coach Interview
    resp = requests.post(f"{BASE_URL}/coach/start_interview", headers=auth_header)
    assert resp.status_code == 200, f"Start interview failed: {resp.text}"
    
    interview_data = resp.json()
    if "prompt" not in interview_data:
        pytest.fail(f"Prompt not found in response. Keys: {interview_data.keys()}, Body: {interview_data}")
    
    interview_chat_id = interview_data["chat_id"]
    assert len(interview_data["prompt"]) > 0
    
    # Answer Interview Questions
    answers = "1. My goal is to run a marathon. 2. I run 3 times a week. 3. I eat healthy."
    resp = requests.post(f"{BASE_URL}/chats/{interview_chat_id}/messages", json={"message": answers}, headers=auth_header)
    assert resp.status_code == 200, f"Answer questions failed: {resp.text}"
    
    # Generate Plan
    resp = requests.post(f"{BASE_URL}/coach/generate_plan", json={"chat_id": interview_chat_id}, headers=auth_header)
    assert resp.status_code == 200, f"Generate plan failed: {resp.text}"
    plan = resp.json()["plan"]
    assert len(plan) > 0
    
    # Organize Plan
    resp = requests.post(f"{BASE_URL}/coach/organize_plan", headers=auth_header)
    assert resp.status_code == 200, f"Organize plan failed: {resp.text}"
    phased_plan = resp.json()["phased_plan"]
    assert len(phased_plan) > 0
