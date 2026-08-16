import pytest
from datetime import date
from app.nutrition.adaptive_targets import (
    calculate_bmr_tdee,
    calculate_adaptive_nutrition_targets,
    calculate_adherence_score,
    get_multi_day_nutrition_summary,
)

def test_calculate_bmr_tdee_defaults_and_custom():
    # Test with default fallback profile
    bmr, tdee = calculate_bmr_tdee({})
    assert 1500 <= bmr <= 2000
    assert tdee > bmr

    # Test with custom athlete profile (80kg, 180cm, 28yo male)
    profile = {
        "weight": 80.0,
        "height": 180.0,
        "age": 28,
        "lifestyle": "active"
    }
    bmr_custom, tdee_custom = calculate_bmr_tdee(profile)
    # Mifflin-St Jeor: 10*80 + 6.25*180 - 5*28 + 5 = 800 + 1125 - 140 + 5 = 1790
    assert round(bmr_custom) == 1790
    assert tdee_custom >= bmr_custom * 1.55


def test_adaptive_targets_marathon_endurance_training_day():
    profile = {
        "weight": 70.0,
        "height": 175.0,
        "age": 30,
        "goals": {
            "primary_goal": "marathon",
            "goal_type": "endurance"
        }
    }
    # Rest day vs hard training day (15km run, ~900 kcal burn)
    rest_targets = calculate_adaptive_nutrition_targets(
        profile=profile,
        target_date="2026-08-16",
        training_data={"workout_type": "rest", "calories_burned": 0, "distance_km": 0}
    )
    assert rest_targets["goal_type"] == "endurance"
    assert rest_targets["protein_g"] >= 70.0 * 1.6
    
    training_targets = calculate_adaptive_nutrition_targets(
        profile=profile,
        target_date="2026-08-16",
        training_data={"workout_type": "running", "calories_burned": 900, "distance_km": 15.0}
    )
    # Training day should boost calories and heavily boost carbs for fueling
    assert training_targets["calories"] > rest_targets["calories"]
    assert training_targets["carbs_g"] > rest_targets["carbs_g"] + 80
    assert "training_fueling_bonus" in training_targets["notes"].lower() or "training" in training_targets["target_note"].lower()


def test_adaptive_targets_hypertrophy_and_cutting():
    # Hypertrophy / Bulking
    hyper_profile = {
        "weight": 80.0,
        "height": 180.0,
        "age": 25,
        "goals": {
            "primary_goal": "hypertrophy",
            "goal_type": "muscle_gain"
        }
    }
    hyper_targets = calculate_adaptive_nutrition_targets(profile=hyper_profile, target_date="2026-08-16")
    assert hyper_targets["protein_g"] >= 80 * 2.0
    assert hyper_targets["calories"] > 2400

    # Fat Loss / Cutting
    cut_profile = {
        "weight": 80.0,
        "height": 180.0,
        "age": 25,
        "goals": {
            "primary_goal": "fat_loss",
            "goal_type": "cutting"
        }
    }
    cut_targets = calculate_adaptive_nutrition_targets(profile=cut_profile, target_date="2026-08-16")
    assert cut_targets["calories"] < hyper_targets["calories"]
    assert cut_targets["protein_g"] >= 80 * 2.0  # Protein stays high during cut


def test_adherence_score_calculation():
    targets = {
        "calories": 2500,
        "protein_g": 160,
        "carbs_g": 280,
        "fat_g": 70
    }
    # Perfect match
    score, breakdown = calculate_adherence_score(
        actual={"calories": 2500, "protein": 160, "carbs": 280, "fat": 70},
        targets=targets
    )
    assert score >= 95
    assert breakdown["calories_adherence_pct"] == 100.0

    # Undereating protein and overeating calories
    score_low, _ = calculate_adherence_score(
        actual={"calories": 3200, "protein": 90, "carbs": 400, "fat": 110},
        targets=targets
    )
    assert score_low < 75
