import pytest
import requests
import uuid
import time

BASE_URL = "http://127.0.0.1:5001/auth"


@pytest.fixture
def make_user():
    def _create_user():
        uid = uuid.uuid4().hex[:6]
        return {
            "username": f"athlete_{int(time.time())}_{uid}",
            "password": "SecretPassword123!",
            "email": f"athlete_{uid}@example.com",
            "name": f"Athlete {uid}"
        }
    return _create_user


def test_register_and_login_success(make_user):
    user_data = make_user()
    
    # 1. Register
    reg_resp = requests.post(f"{BASE_URL}/register", json=user_data)
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"
    reg_json = reg_resp.json()
    assert "token" in reg_json or "access_token" in reg_json
    assert reg_json["user"]["username"] == user_data["username"]

    # 2. Login
    login_resp = requests.post(f"{BASE_URL}/login", json={
        "username": user_data["username"],
        "password": user_data["password"]
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    login_json = login_resp.json()
    token = login_json.get("token") or login_json.get("access_token")
    assert token is not None


def test_register_duplicate_username_fails(make_user):
    user_data = make_user()
    
    # First registration
    resp1 = requests.post(f"{BASE_URL}/register", json=user_data)
    assert resp1.status_code == 201

    # Second registration with duplicate username
    resp2 = requests.post(f"{BASE_URL}/register", json=user_data)
    assert resp2.status_code == 400
    assert "already exists" in resp2.text.lower() or "error" in resp2.text.lower()


def test_register_missing_fields_fails():
    # Missing password
    resp = requests.post(f"{BASE_URL}/register", json={"username": "orphan_user"})
    assert resp.status_code == 400

    # Missing username
    resp = requests.post(f"{BASE_URL}/register", json={"password": "password123"})
    assert resp.status_code == 400

    # Empty payload
    resp = requests.post(f"{BASE_URL}/register", json={})
    assert resp.status_code == 400


def test_login_invalid_credentials_fails(make_user):
    user_data = make_user()
    reg_resp = requests.post(f"{BASE_URL}/register", json=user_data)
    assert reg_resp.status_code == 201

    # Wrong password
    resp_wrong_pw = requests.post(f"{BASE_URL}/login", json={
        "username": user_data["username"],
        "password": "WrongPassword999!"
    })
    assert resp_wrong_pw.status_code == 401

    # Non-existent user
    resp_no_user = requests.post(f"{BASE_URL}/login", json={
        "username": f"non_existent_{uuid.uuid4().hex[:8]}",
        "password": "AnyPassword123!"
    })
    assert resp_no_user.status_code == 401


def test_unauthenticated_protected_route_fails():
    # Calling /profile without Authorization header
    resp = requests.get(f"{BASE_URL}/profile")
    assert resp.status_code in [401, 422]


def test_multi_tenant_athlete_data_isolation(make_user):
    user_a = make_user()
    user_b = make_user()

    # Register Athlete A
    resp_a = requests.post(f"{BASE_URL}/register", json=user_a)
    assert resp_a.status_code == 201
    token_a = resp_a.json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register Athlete B
    resp_b = requests.post(f"{BASE_URL}/register", json=user_b)
    assert resp_b.status_code == 201
    token_b = resp_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Athlete A sets profile
    profile_a = {
        "age": 29,
        "weight": 82.5,
        "height": 185.0,
        "sport_history": "Rowing & Weightlifting",
        "goals": {"primary": "Hypertrophy"}
    }
    set_a = requests.put(f"{BASE_URL}/profile", json=profile_a, headers=headers_a)
    assert set_a.status_code == 200

    # Athlete B sets profile
    profile_b = {
        "age": 38,
        "weight": 64.0,
        "height": 172.0,
        "sport_history": "Marathon & Trail Running",
        "goals": {"primary": "Endurance"}
    }
    set_b = requests.put(f"{BASE_URL}/profile", json=profile_b, headers=headers_b)
    assert set_b.status_code == 200

    # Verify Athlete A sees ONLY Athlete A's profile
    get_a = requests.get(f"{BASE_URL}/profile", headers=headers_a)
    assert get_a.status_code == 200
    data_a = get_a.json()["profile"]
    assert data_a["sport_history"] == "Rowing & Weightlifting"
    assert data_a["weight"] == 82.5
    assert data_a.get("goals", {}).get("primary") == "Hypertrophy"

    # Verify Athlete B sees ONLY Athlete B's profile
    get_b = requests.get(f"{BASE_URL}/profile", headers=headers_b)
    assert get_b.status_code == 200
    data_b = get_b.json()["profile"]
    assert data_b["sport_history"] == "Marathon & Trail Running"
    assert data_b["weight"] == 64.0
    assert data_b.get("goals", {}).get("primary") == "Endurance"
