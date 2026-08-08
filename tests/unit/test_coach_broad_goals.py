import pytest
from app.coach.interview_service import STEP_MISSIONS

def test_start_interview_broad_goal_prompt():
    step1_mission = STEP_MISSIONS.get(1, "")
    assert "Build Muscle & Strength" in step1_mission
    assert "Fat Loss & Recomposition" in step1_mission
    assert "Custom Goal" in step1_mission
