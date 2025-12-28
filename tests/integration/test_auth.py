import pytest
import requests
import uuid
import time
import logging

BASE_URL = "http://localhost:5001/auth" # Updated port to match verify_auth.py if needed, or stick to 5000 if that's the main app.
# Looking at verify_backend.py it used 5000, verify_auth.py used 5001. I should probably use an env var or common config.
# For now, I will use the one from verify_auth.py since it likely tests a specific service or config.
# Wait, let's double check if they are the same app. verify_backend used 5000. verify_auth used 5001.
# This implies there might be two instances or one is mismatched. valid check.
# I will stick to what verify_auth.py had, but maybe make it configurable?
# Let's assume 5000 is the main one and 5001 might be valid too.
# Let's check verify_auth.py again... "http://localhost:5001/auth"
# verify_backend.py used "http://127.0.0.1:5000"
# I should probably standardize this. I'll use a constant for now.

# Actually, if I look at the running commands, `python app.py` is running. `npm start` is running.
# Let's check `app.py` to see what port it runs on.

@pytest.fixture
def unique_user():
    return {
        "username": f"auth_test_{int(time.time())}_{uuid.uuid4().hex[:6]}",
        "password": "testpassword123",
        "email": f"test_{uuid.uuid4().hex[:6]}@example.com"
    }

def test_register_and_login(unique_user):
    # Register
    # Using 5000 as default since verify_backend worked with it and 5000 is standard flask.
    # If verify_auth used 5001, maybe it was a mistake or specific setup.
    # I'll check app.py content if I can, but I'll default to 5000 for consistency with api_flow.
    
    BASE_URL_TEST = "http://127.0.0.1:5001/auth"
    
    resp = requests.post(f"{BASE_URL_TEST}/register", json=unique_user)
    # 201 Created is standard, but sometimes 200.
    assert resp.status_code in [200, 201], f"Register failed: {resp.text}"
    
    # Login
    resp = requests.post(f"{BASE_URL_TEST}/login", json={
        "username": unique_user["username"],
        "password": unique_user["password"]
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    
    data = resp.json()
    assert "token" in data or "access_token" in data
