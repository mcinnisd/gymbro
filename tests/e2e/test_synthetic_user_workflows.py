import pytest
import io
import json
from app import create_app
from app.supabase_client import supabase

@pytest.fixture
def test_app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(test_app):
    return test_app.test_client()

def get_auth_token(client, email="synthetic_runner@example.com", password="password123", name="Runner Alex"):
    # Attempt register
    reg_res = client.post('/auth/register', json={
        'email': email,
        'password': password,
        'name': name
    })
    if reg_res.status_code in [200, 201]:
        data = reg_res.get_json() or {}
        token = data.get('access_token') or data.get('token')
        if token:
            return token

    # Fallback to login
    login_res = client.post('/auth/login', json={
        'email': email,
        'password': password
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.get_data(as_text=True)}"
    data = login_res.get_json() or {}
    return data.get('access_token') or data.get('token')


def test_synthetic_user_registration_and_login(client):
    email = "synthetic_runner_reg@example.com"
    password = "password123"
    name = "Runner Alex"

    # 1. Register user
    res = client.post('/auth/register', json={
        'email': email,
        'password': password,
        'name': name
    })
    assert res.status_code in [200, 201], f"Register failed: {res.get_data(as_text=True)}"
    reg_data = res.get_json()
    assert "user_id" in reg_data
    assert "token" in reg_data or "access_token" in reg_data

    # 2. Login user
    login_res = client.post('/auth/login', json={
        'email': email,
        'password': password
    })
    assert login_res.status_code == 200
    login_data = login_res.get_json()
    assert "token" in login_data
    assert login_data["user"]["email"] == email


def test_synthetic_user_profile_management(client):
    token = get_auth_token(client, email="synthetic_profile@example.com")
    headers = {'Authorization': f'Bearer {token}'}

    # Update profile
    profile_payload = {
        "age": 32,
        "weight": 74.5,
        "height": 182.0,
        "sport_history": "Marathoner 4 years",
        "running_experience": "Advanced",
        "past_injuries": "Minor Achilles tendinitis in 2024",
        "lifestyle": "Active engineer",
        "weekly_availability": "5 days per week",
        "terrain_preference": "Road and trail",
        "equipment": "GPS Watch, HR Strap, Carbon Racers"
    }

    put_res = client.put('/auth/profile', headers=headers, json=profile_payload)
    assert put_res.status_code == 200
    assert put_res.get_json().get("message") == "Profile updated successfully."

    # Fetch profile
    get_res = client.get('/auth/profile', headers=headers)
    assert get_res.status_code == 200
    profile = get_res.get_json().get("profile") or {}
    assert profile.get("age") == 32
    assert profile.get("weight") == 74.5
    assert profile.get("sport_history") == "Marathoner 4 years"


def test_synthetic_user_bloodwork_pdf_upload(client):
    token = get_auth_token(client, email="synthetic_bloodwork@example.com")
    headers = {'Authorization': f'Bearer {token}'}

    # Simulate PDF upload
    pdf_content = b"%PDF-1.4 Mock Lab Blood Test PDF Content for Ferritin and hs-CRP"
    data = {
        'file': (io.BytesIO(pdf_content), 'lab_results_aug2026.pdf')
    }

    res = client.post('/biomarkers/upload-pdf', headers=headers, data=data, content_type='multipart/form-data')
    assert res.status_code == 200
    res_data = res.get_json()
    assert "panel_id" in res_data
    assert "extracted_biomarkers" in res_data
    assert len(res_data["extracted_biomarkers"]) > 0

    # Verify flagged biomarkers endpoint
    flagged_res = client.get('/biomarkers/flagged', headers=headers)
    assert flagged_res.status_code == 200
    flagged_data = flagged_res.get_json()
    assert "flagged_biomarkers" in flagged_data


def test_synthetic_user_journal_logging(client):
    token = get_auth_token(client, email="synthetic_journal@example.com")
    headers = {'Authorization': f'Bearer {token}'}

    # Save journal entry
    journal_payload = {
        "date": "2026-08-09",
        "answers": {
            "energy_level": 8,
            "felt_sore": False,
            "journal_text": "Felt strong during 10k tempo run. Good energy levels."
        }
    }

    post_res = client.post('/journal/', headers=headers, json=journal_payload)
    assert post_res.status_code == 200
    assert "journal" in post_res.get_json()

    # Get list of journals
    list_res = client.get('/journal/', headers=headers)
    assert list_res.status_code == 200
    journals = list_res.get_json().get("journals", [])
    assert len(journals) >= 1

    # Get journal by date
    date_res = client.get('/journal/2026-08-09', headers=headers)
    assert date_res.status_code == 200
    journal_entry = date_res.get_json().get("journal")
    assert journal_entry["date"] == "2026-08-09"
    assert journal_entry["answers"]["energy_level"] == 8


def test_synthetic_user_garmin_data_sync(client):
    token = get_auth_token(client, email="synthetic_garmin@example.com")
    headers = {'Authorization': f'Bearer {token}'}

    # Connect Garmin
    conn_res = client.post('/garmin/connect', headers=headers, json={
        "email": "synthetic_runner@garmin.com",
        "password": "garminpassword123"
    })
    assert conn_res.status_code == 200

    # Get Garmin status
    status_res = client.get('/garmin/status', headers=headers)
    assert status_res.status_code == 200

    # Seed mock Garmin daily and sleep records for the authenticated user
    login_res = client.post('/auth/login', json={
        'email': "synthetic_garmin@example.com",
        'password': "password123"
    })
    user_id = login_res.get_json()["user"]["id"]

    supabase.table("garmin_daily").insert({
        "user_id": user_id,
        "date": "2026-08-09",
        "hrv_avg": 68,
        "resting_heart_rate": 48,
        "steps": 12500
    }).execute()

    supabase.table("garmin_sleep").insert({
        "user_id": user_id,
        "date": "2026-08-09",
        "total_sleep_seconds": 28800,
        "sleep_score": 85
    }).execute()

    # Query daily and sleep details
    daily_res = client.get('/garmin/daily/2026-08-09', headers=headers)
    assert daily_res.status_code == 200
    assert daily_res.get_json()["hrv_avg"] == 68

    sleep_res = client.get('/garmin/sleep/2026-08-09', headers=headers)
    assert sleep_res.status_code == 200
    assert sleep_res.get_json()["sleep_score"] == 85


def test_synthetic_user_coach_and_training_plan_generation(client):
    token = get_auth_token(client, email="synthetic_coach@example.com")
    headers = {'Authorization': f'Bearer {token}'}

    # Start interview
    interview_res = client.post('/coach/start_interview', headers=headers)
    assert interview_res.status_code == 200
    chat_id = interview_res.get_json().get("chat_id")
    assert chat_id is not None

    # Generate training plan
    plan_res = client.post('/coach/generate_plan', headers=headers, json={"chat_id": chat_id})
    assert plan_res.status_code == 200
    assert "plan" in plan_res.get_json()

    # Verify calendar events populated
    cal_res = client.get('/calendar/events', headers=headers)
    assert cal_res.status_code == 200
    assert "events" in cal_res.get_json()


def test_synthetic_user_full_journey(client):
    """
    Executes complete end-to-end user journey for synthetic_runner@example.com.
    """
    email = "synthetic_runner@example.com"
    password = "password123"
    name = "Runner Alex"

    # 1. Register / Auth
    reg_res = client.post('/auth/register', json={
        'email': email,
        'password': password,
        'name': name
    })
    assert reg_res.status_code in [200, 201]
    token = reg_res.get_json().get("access_token") or reg_res.get_json().get("token")
    if not token:
        login_res = client.post('/auth/login', json={'email': email, 'password': password})
        token = login_res.get_json().get("access_token")
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Profile Setup
    client.put('/auth/profile', headers=headers, json={
        "age": 30, "weight": 70.0, "height": 178.0, "sport_history": "5k & 10k runner"
    })

    # 3. Bloodwork PDF Upload
    pdf_bytes = b"%PDF-1.4 Synthetic Lab Panel PDF"
    client.post('/biomarkers/upload-pdf', headers=headers, data={
        'file': (io.BytesIO(pdf_bytes), 'synthetic_bloodwork.pdf')
    }, content_type='multipart/form-data')

    # 4. Manual Journal Entry
    j_res = client.post('/journal/', headers=headers, json={
        "date": "2026-08-09",
        "answers": {"energy_level": 9, "felt_sore": False, "journal_text": "Peak week preparation"}
    })
    assert j_res.status_code == 200

    # 5. Garmin Sync Simulation
    client.post('/garmin/connect', headers=headers, json={
        "email": email, "password": "garminpass123"
    })

    # 6. Coach Interview & Plan Generation
    start_res = client.post('/coach/start_interview', headers=headers)
    assert start_res.status_code == 200
    chat_id = start_res.get_json().get("chat_id")

    plan_res = client.post('/coach/generate_plan', headers=headers, json={"chat_id": chat_id})
    assert plan_res.status_code == 200
    assert "plan" in plan_res.get_json()

    # 7. Calendar Check
    cal_res = client.get('/calendar/events', headers=headers)
    assert cal_res.status_code == 200
