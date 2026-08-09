# tests/unit/test_strava_routes.py
import pytest

def test_strava_connect_url_generation(client, auth_headers):
    res = client.get("/strava/connect_strava?json=true", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "url" in data
    assert "/strava/exchange_token" in data["url"]
