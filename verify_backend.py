import requests
import time
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_backend():
    # 1. Register
    username = f"testuser_{int(time.time())}"
    password = "password123"
    print(f"Registering user: {username}")
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    if resp.status_code != 201:
        print(f"Registration failed: {resp.text}")
        return
    print("Registration successful")

    # 2. Login
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful")

    # 3. Update Profile
    print("Updating profile...")
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
    resp = requests.put(f"{BASE_URL}/auth/profile", json=profile_data, headers=headers)
    if resp.status_code != 200:
        print(f"Update profile failed: {resp.text}")
        return
    print("Profile updated")

    # 4. Get Profile
    print("Fetching profile...")
    resp = requests.get(f"{BASE_URL}/auth/profile", headers=headers)
    if resp.status_code != 200:
        print(f"Get profile failed: {resp.text}")
        return
    fetched_profile = resp.json()["profile"]
    print(f"Fetched profile: {fetched_profile}")
    
    # Verify a field
    if fetched_profile["sport_history"] != "Running":
        print("Profile verification failed!")
        return
    print("Profile verification passed")

    # 5. Create Chat
    print("Creating chat...")
    resp = requests.post(f"{BASE_URL}/chats/", json={"title": "Test Chat"}, headers=headers)
    if resp.status_code != 201:
        print(f"Create chat failed: {resp.text}")
        return
    chat_id = resp.json()["chat_id"]
    print(f"Chat created: {chat_id}")

    # 6. Send Message
    print("Sending message...")
    # We expect the coach to know about the profile now
    msg = "What is my sport history?"
    resp = requests.post(f"{BASE_URL}/chats/{chat_id}/messages", json={"message": msg}, headers=headers)
    if resp.status_code != 200:
        print(f"Send message failed: {resp.text}")
        return
    reply = resp.json()["reply"]
    print(f"Bot reply: {reply}")

    # 7. Start Coach Interview
    print("Starting Coach Interview...")
    resp = requests.post(f"{BASE_URL}/coach/start_interview", headers=headers)
    if resp.status_code != 200:
        print(f"Start interview failed: {resp.text}")
        return
    interview_data = resp.json()
    interview_chat_id = interview_data["chat_id"]
    print(f"Interview started. Chat ID: {interview_chat_id}")
    print(f"Questions: {interview_data['questions']}")

    # 8. Answer Interview Questions
    print("Answering interview questions...")
    answers = "1. My goal is to run a marathon. 2. I run 3 times a week. 3. I eat healthy."
    resp = requests.post(f"{BASE_URL}/chats/{interview_chat_id}/messages", json={"message": answers}, headers=headers)
    if resp.status_code != 200:
        print(f"Answer questions failed: {resp.text}")
        return
    print("Answers submitted.")

    # 9. Generate Plan
    print("Generating Plan...")
    resp = requests.post(f"{BASE_URL}/coach/generate_plan", json={"chat_id": interview_chat_id}, headers=headers)
    if resp.status_code != 200:
        print(f"Generate plan failed: {resp.text}")
        return
    plan = resp.json()["plan"]
    print(f"Plan generated: {plan}")

    # 10. Organize Plan
    print("Organizing Plan into Phases...")
    resp = requests.post(f"{BASE_URL}/coach/organize_plan", headers=headers)
    if resp.status_code != 200:
        print(f"Organize plan failed: {resp.text}")
        return
    phased_plan = resp.json()["phased_plan"]
    print(f"Phased Plan generated: {phased_plan}")

    print("\nALL TESTS PASSED")

if __name__ == "__main__":
    try:
        test_backend()
    except Exception as e:
        print(f"An error occurred: {e}")
