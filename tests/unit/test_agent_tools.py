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
