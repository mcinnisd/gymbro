import pytest
from unittest.mock import MagicMock, patch
from app.coach.interview_service import ARCHETYPE_MISSIONS, get_mission, get_next_question, _detect_archetype_from_answer

def test_archetype_missions_registry_structure():
    expected_archetypes = [
        "muscle_strength", "fat_loss", "endurance_running",
        "longevity_energy", "hybrid_fitness", "custom_open_ended"
    ]
    for key in expected_archetypes:
        assert key in ARCHETYPE_MISSIONS
        assert "total_steps" in ARCHETYPE_MISSIONS[key]
        assert "missions" in ARCHETYPE_MISSIONS[key]
        assert len(ARCHETYPE_MISSIONS[key]["missions"]) == ARCHETYPE_MISSIONS[key]["total_steps"]

def test_get_mission_resolution():
    strength_m1 = get_mission("muscle_strength", 1)
    assert "Goal & Target Lifts" in strength_m1

    fat_loss_m3 = get_mission("fat_loss", 3)
    assert "Cardio & Daily Movement" in fat_loss_m3

    fallback = get_mission("unknown_archetype", 1)
    assert "Goal & Race" in fallback

def test_detect_archetype_from_answer():
    assert _detect_archetype_from_answer("🏋️ Build Muscle & Strength") == "muscle_strength"
    assert _detect_archetype_from_answer("🔥 Fat Loss & Recomposition") == "fat_loss"
    assert _detect_archetype_from_answer("🏃 Endurance & Speed PRs") == "endurance_running"
    assert _detect_archetype_from_answer("🌿 Longevity & Daily Energy") == "longevity_energy"
    assert _detect_archetype_from_answer("⚡ Hybrid / General Fitness") == "hybrid_fitness"
    assert _detect_archetype_from_answer("ACL rehab recovery") == "custom_open_ended"

def test_get_next_question_advancement():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
        "id": "user_456",
        "interview_step": 3,
        "archetype": "muscle_strength"
    }]

    with patch("app.coach.interview_service.supabase", mock_supabase), \
         patch("app.coach.interview_service._analyze_progress", return_value={"is_complete": True, "response": "Great work!"}), \
         patch("app.coach.interview_service._generate_dynamic_response", return_value="Next question: preview plan"), \
         patch("app.coach.plan_service.generate_baseline_plan") as mock_gen_plan:

        res = get_next_question("user_456", chat_id="chat_789")
        assert res["success"] is True
        assert res["step"] == 4
        assert res["is_complete"] is False
        mock_gen_plan.assert_called_once_with("user_456", archetype="muscle_strength")
