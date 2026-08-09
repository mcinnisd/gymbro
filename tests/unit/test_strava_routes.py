# tests/unit/test_strava_routes.py
import pytest

def test_strava_connect_url_generation(client, auth_headers):
    res = client.get("/strava/connect_strava?json=true", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "url" in data
    assert "/strava/exchange_token" in data["url"] or "/strava/callback" in data["url"]

def test_strava_oauth_callback_redirect(client):
    res = client.get('/strava/callback?code=mock_code_123&state=mock_user_id')
    assert res.status_code == 302
    assert res.headers['Location'].startswith('gymbro://') or 'strava-callback' in res.headers['Location']

def test_strava_oauth_exchange_token_redirect(client):
    res = client.get('/strava/exchange_token?code=mock_code_123&state=mock_user_id')
    assert res.status_code == 302
    assert res.headers['Location'].startswith('gymbro://') or 'strava-callback' in res.headers['Location']

