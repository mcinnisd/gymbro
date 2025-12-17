import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:5001/auth"

def verify_auth():
    # 1. Register
    username = "auth_test_user_v2"
    password = "testpassword123"
    
    logger.info(f"Testing Register for {username}...")
    try:
        resp = requests.post(f"{BASE_URL}/register", json={
            "username": username,
            "password": password,
            "email": "test@example.com" # Added email just in case, though schema might not enforce it yet for auth
        })
        logger.info(f"Register Status: {resp.status_code}")
        logger.info(f"Register Response: {resp.text}")
    except Exception as e:
        logger.error(f"Register Request Failed: {e}")
        return

    # 2. Login
    logger.info(f"Testing Login for {username}...")
    try:
        resp = requests.post(f"{BASE_URL}/login", json={
            "username": username,
            "password": password
        })
        logger.info(f"Login Status: {resp.status_code}")
        logger.info(f"Login Response: {resp.text}")
        
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                logger.info("Login SUCCESS: Token received.")
            else:
                logger.error("Login FAILED: No token in response.")
    except Exception as e:
        logger.error(f"Login Request Failed: {e}")

if __name__ == "__main__":
    verify_auth()
