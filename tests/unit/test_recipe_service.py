import pytest
from app.nutrition.recipe_service import (
    create_recipe,
    get_user_recipes,
    get_recipe,
    log_recipe_portion,
    delete_recipe,
    match_recipe
)

def test_create_recipe_calculates_totals_and_per_serving():
    user_id = "test_user_100"
    recipe_data = {
        "name": "Weekly Ground Beef & Jasmine Rice Prep",
        "servings": 4.0,
        "ingredients": [
            {"name": "Extra Lean Ground Beef 93/7", "calories": 680, "protein": 88, "carbs": 0, "fat": 32},
            {"name": "Cooked Jasmine Rice (4 cups)", "calories": 800, "protein": 16, "carbs": 176, "fat": 2},
            {"name": "Olive Oil for cooking", "calories": 120, "protein": 0, "carbs": 0, "fat": 14}
        ],
        "notes": "Divided into 4 meal prep containers."
    }

    result = create_recipe(user_id=user_id, **recipe_data)
    assert result["success"] is True
    recipe = result["recipe"]
    assert recipe["name"] == "Weekly Ground Beef & Jasmine Rice Prep"
    assert recipe["servings"] == 4.0
    
    # Check total macros: 680+800+120 = 1600 kcal
    assert recipe["total_calories"] == 1600.0
    assert recipe["total_protein"] == 104.0
    assert recipe["total_carbs"] == 176.0
    assert recipe["total_fat"] == 48.0

    # Check per-serving macros: 1600/4 = 400 kcal
    assert recipe["per_serving_calories"] == 400.0
    assert recipe["per_serving_protein"] == 26.0
    assert recipe["per_serving_carbs"] == 44.0
    assert recipe["per_serving_fat"] == 12.0


def test_log_recipe_portion_scales_macros():
    user_id = "test_user_101"
    # Create recipe
    created = create_recipe(
        user_id=user_id,
        name="Post-Workout Protein Smoothie",
        servings=2.0,
        ingredients=[
            {"name": "Whey Protein Isolate", "calories": 240, "protein": 50, "carbs": 4, "fat": 2},
            {"name": "2 Bananas", "calories": 210, "protein": 2.6, "carbs": 54, "fat": 0.6},
            {"name": "Almond Milk", "calories": 60, "protein": 2, "carbs": 2, "fat": 5}
        ]
    )
    recipe_id = created["recipe"]["id"]

    # Log 1.5 servings
    log_res = log_recipe_portion(
        user_id=user_id,
        recipe_id=recipe_id,
        servings=1.5,
        date="2026-08-28"
    )
    assert log_res["success"] is True
    log = log_res["log"]
    assert "Post-Workout Protein Smoothie" in log["meal_name"]
    # Total for 2 servings was 510 kcal -> 1 serving = 255 kcal -> 1.5 servings = 382.5 kcal
    assert round(log["calories"]) == 382 or round(log["calories"]) == 383
    assert log["protein"] > 35


def test_match_recipe_finds_similar_saved_dish():
    user_id = "test_user_102"
    create_recipe(
        user_id=user_id,
        name="Chili Con Carne Batch Prep",
        servings=5.0,
        ingredients=[
            {"name": "Lean Ground Beef", "calories": 800, "protein": 90, "carbs": 0, "fat": 40},
            {"name": "Black Beans & Kidney Beans", "calories": 500, "protein": 30, "carbs": 80, "fat": 2},
            {"name": "Crushed Tomatoes", "calories": 100, "protein": 5, "carbs": 20, "fat": 0}
        ]
    )

    # Search with a scanned meal name
    matches = match_recipe(user_id=user_id, meal_name="Bowl of Homemade Chili with Beef and Beans")
    assert len(matches) >= 1
    best_match = matches[0]
    assert "Chili" in best_match["name"]
    assert best_match["confidence"] in ["high", "medium"]
    assert best_match["per_serving_calories"] == 280.0
    assert best_match["suggested_servings"] == 1.0


def test_delete_recipe():
    user_id = "test_user_103"
    created = create_recipe(
        user_id=user_id,
        name="Temporary Oats Prep",
        servings=1.0,
        ingredients=[{"name": "Rolled Oats", "calories": 300, "protein": 10, "carbs": 54, "fat": 5}]
    )
    recipe_id = created["recipe"]["id"]

    del_res = delete_recipe(user_id=user_id, recipe_id=recipe_id)
    assert del_res["success"] is True

    # Confirm it cannot be retrieved
    recipe = get_recipe(user_id=user_id, recipe_id=recipe_id)
    assert recipe is None
