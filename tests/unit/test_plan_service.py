import pytest
from unittest.mock import MagicMock, patch
from app.coach.plan_service import generate_baseline_plan

def test_generate_baseline_plan_muscle_strength():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
        "id": "user_123",
        "age": 25,
        "weight": "75kg",
        "height": "178cm",
        "goals": {"current_goal": "Build Muscle"}
    }]

    with patch("app.coach.plan_service.supabase", mock_supabase), \
         patch("app.coach.interview_service.get_interview_context", return_value="Goal: Bench PR"), \
         patch("app.coach.plan_service.generate_chat_response", return_value='{"plan_type": "strength", "split": "Push/Pull/Legs", "weeks": []}'):
        
        plan = generate_baseline_plan("user_123", archetype="muscle_strength")
        assert plan is not None
        assert plan.get("plan_type") == "strength" or "split" in plan
