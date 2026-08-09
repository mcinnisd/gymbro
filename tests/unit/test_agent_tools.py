import pytest
from app.mock_supabase import MockSupabaseClient
import app.coach.agent_tools as agent_tools

def test_agent_biomarker_history_tool(monkeypatch):
    monkeypatch.setattr(agent_tools, 'supabase', MockSupabaseClient())
    db = agent_tools.supabase
    db.table('biomarkers').insert({
        'user_id': 1, 'marker_name': 'Ferritin', 'value': 14.0, 'unit': 'ng/mL', 'status': 'flagged_low'
    }).execute()
    
    history = agent_tools.get_biomarker_history(user_id=1, marker_name='Ferritin')
    assert len(history) == 1
    assert history[0]['marker_name'] == 'Ferritin'

def test_generate_workout_routine_tool():
    routine = agent_tools.generate_workout_routine(split_type='Upper/Lower', fatigue_level='moderate')
    assert 'routine_name' in routine
    assert 'exercises' in routine

def test_coach_service_returns_ui_payload():
    from app.coach.service import process_coach_message
    res = process_coach_message(user_id="user_123", message="Generate a 4-day marathon plan")
    assert "response" in res
    assert "ui_payload" in res or "plan" in res
    if "ui_payload" in res and res["ui_payload"]:
        assert res["ui_payload"].get("type") in ["WORKOUT_PLAN", "CHART", "GOALS"]

def test_render_chart_tool_returns_ui_payload():
    from app.agent.tools import render_chart
    payload = render_chart(user_id="user_123", metric="pace", period_days=30)
    assert payload.get("type") == "CHART"
    assert "data" in payload

def test_update_user_goals_tool_returns_ui_payload():
    from app.agent.tools import update_user_goals
    payload = update_user_goals(user_id="user_123", goal_type="marathon_pace", target_value="4:30/km")
    assert payload.get("type") == "GOALS"
    assert "data" in payload
