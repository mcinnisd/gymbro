import pytest
from app.coach.interview_service import ARCHETYPE_MISSIONS, get_mission

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
