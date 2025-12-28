import requests
import json
import time

BASE_URL = "http://localhost:5001"
USERNAME = "test1111"
PASSWORD = "test"

def get_token():
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if response.status_code == 200:
            return response.json().get("token")
        print(f"Login failed: {response.text}")
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def create_chat(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/chats/", json={"title": "Council Test"}, headers=headers)
    if response.status_code == 201:
        return response.json()["chat_id"]
    print(f"Create chat failed: {response.text}")
    return None

def test_council(token, chat_id):
    headers = {"Authorization": f"Bearer {token}"}
    message = "/council How should I prepare for my first marathon?"
    
    print(f"Sending: '{message}'")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chats/{chat_id}/messages", 
            json={"message": message}, 
            headers=headers,
            stream=True
        )
        
        full_response = ""
        print("Streaming response:")
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    try:
                        data = json.loads(data_str)
                        if "token" in data:
                            print(data["token"], end="", flush=True)
                            full_response += data["token"]
                        elif "status" in data:
                            print(f"\n[STATUS]: {data['status']}")
                        elif "error" in data:
                            print(f"\n[ERROR]: {data['error']}")
                    except:
                        pass
        print("\n\nResponse complete.")
        
        if "Running Coach" in full_response or "Strength Coach" in full_response or "Nutrition Coach" in full_response:
            print("SUCCESS: Council response contains coach perspectives.")
        elif len(full_response) > 100:
            print("SUCCESS: Received a substantial response (likely synthesized).")
        else:
            print("WARNING: Response seems short or missing coach details.")
            
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    token = get_token()
    if token:
        chat_id = create_chat(token)
        if chat_id:
            test_council(token, chat_id)
