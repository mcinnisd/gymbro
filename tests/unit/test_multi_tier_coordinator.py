import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock, patch
from flask_jwt_extended import create_access_token
from app import create_app
from app.supabase_client import supabase
from app.garmin.sync import discover_garmin_inception_date
from app.strava.sync import discover_strava_inception_date

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret-key-12345"
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_headers(app):
    with app.app_context():
        token = create_access_token(identity="1")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def test_discover_garmin_inception_date_from_activities():
    """Verify discover_garmin_inception_date finds the earliest activity date."""
    mock_api = MagicMock()
    mock_api.get_activities.side_effect = [
        [
            {"startTimeLocal": "2023-05-10 07:00:00", "activityId": 1},
            {"startTimeLocal": "2020-08-14 06:30:00", "activityId": 2},
        ],
        [
            {"startTimeLocal": "2018-03-22 09:15:00", "activityId": 3},
        ],
        [] # Empty end of pagination
    ]
    
    inception = discover_garmin_inception_date(mock_api, batch_size=2)
    assert inception == date(2018, 3, 22)

def test_discover_garmin_inception_date_fallback_when_empty():
    """Verify discover_garmin_inception_date provides a safe fallback when no activities exist."""
    mock_api = MagicMock()
    mock_api.get_activities.return_value = []
    
    inception = discover_garmin_inception_date(mock_api)
    # Default fallback should be approximately 5 years ago (1825 days)
    expected_fallback = (datetime.now(timezone.utc) - timedelta(days=1825)).date()
    assert abs((inception - expected_fallback).days) <= 1

def test_discover_strava_inception_date():
    """Verify discover_strava_inception_date extracts date from athlete profile."""
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 12345,
            "created_at": "2019-07-04T14:20:00Z"
        }
        mock_get.return_value = mock_resp
        
        inception = discover_strava_inception_date("test_strava_token")
        assert inception == date(2019, 7, 4)

def test_telemetry_sync_endpoint_supports_all_time_mode(client, auth_headers):
    """Verify /telemetry/sync accepts mode='all_time' and returns non-blocking response."""
    with patch("app.garmin.sync.sync_all_garmin_data_for_user") as mock_garmin_sync, \
         patch("app.strava.sync.sync_strava_activities") as mock_strava_sync:
        
        response = client.post(
            "/telemetry/sync",
            headers=auth_headers,
            json={"provider": "all", "mode": "all_time", "force": True}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "syncing"
        assert data["mode"] == "all_time"

def test_telemetry_status_reports_active_tier_and_inception(client, auth_headers):
    """Verify /telemetry/status exposes current stage, progress, and archive inception date."""
    supabase.table("users").upsert([{
        "id": 1,
        "username": "tier_athlete",
        "garmin_email": "athlete@garmin.com",
        "garmin_password": "encrypted_pass",
        "garmin_sync_status": "syncing",
        "goals": {
            "sync_stage": "deep_365d",
            "sync_progress": 45,
            "archive_inception_date": "2018-03-22"
        }
    }]).execute()
    
    response = client.get("/telemetry/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["garmin"]["connected"] is True
    assert data["garmin"]["stage"] == "deep_365d"
    assert data["garmin"]["progress"] == 45
    assert data["garmin"]["archive_inception_date"] == "2018-03-22"
