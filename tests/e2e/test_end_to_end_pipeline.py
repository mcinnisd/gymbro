# tests/e2e/test_end_to_end_pipeline.py
import pytest
from unittest.mock import patch, MagicMock

@patch("app.coach.plan_service.supabase")
@patch("app.coach.interview_service.supabase")
@patch("app.auth.routes.supabase")
@patch("app.calendar.routes.supabase")
@patch("app.analytics.routes.supabase")
def test_full_user_lifecycle_end_to_end(mock_analytics_supa, mock_cal_supa, mock_auth_supa, mock_interview_supa, mock_plan_supa, client, auth_headers):
    # Mock Auth update profile
    mock_auth_supa.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "1"}]
    
    profile_res = client.put("/auth/profile", headers=auth_headers, json={
        "age": 30, "weight": 75, "height": 180, "sport_history": "Running 3 years"
    })
    assert profile_res.status_code == 200

    # Mock interview start
    mock_interview_supa.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"interview_chat_id": 123}]
    mock_interview_supa.table.return_value.insert.return_value.execute.return_value.data = [{"id": 123}]

    start_res = client.post("/coach/start_interview", headers=auth_headers)
    assert start_res.status_code == 200
    data = start_res.get_json()
    assert "chat_id" in data

    # Mock calendar query
    mock_cal_supa.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": 1, "title": "5km Run", "event_type": "run", "status": "planned"}
    ]

    cal_res = client.get("/calendar/events", headers=auth_headers)
    assert cal_res.status_code == 200
    events = cal_res.get_json().get("events", [])
    assert len(events) > 0
    assert events[0]["title"] == "5km Run"

    # Mock analytics summary
    mock_analytics_supa.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value.data = []
    
    analytics_res = client.get("/analytics/summary", headers=auth_headers)
    assert analytics_res.status_code == 200
    assert "sports" in analytics_res.get_json()
