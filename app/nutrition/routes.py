# app/nutrition/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
import json
import base64
import logging
from app.supabase_client import supabase
from app.nutrition.adaptive_targets import (
    get_multi_day_nutrition_summary,
    calculate_adaptive_nutrition_targets,
    reevaluate_macros
)
from app.nutrition.barcode_service import lookup_barcode
from app.nutrition.recipe_service import (
    create_recipe,
    get_user_recipes,
    get_recipe,
    log_recipe_portion,
    delete_recipe,
    match_recipe
)

nutrition_bp = Blueprint('nutrition', __name__)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Barcode & Food Scanning Routes
# ------------------------------------------------------------------------------

@nutrition_bp.route("/barcode/<barcode>", methods=["GET"], strict_slashes=False)
def get_barcode_nutrition(barcode):
    """
    Looks up packaged food items by barcode / UPC.
    """
    result = lookup_barcode(barcode)
    return jsonify(result), 200


@nutrition_bp.route("/reevaluate", methods=["POST"], strict_slashes=False)
def reevaluate_food_item():
    """
    Recalculates calories and macronutrients for any food description text.
    """
    data = request.get_json() or {}
    item_name = data.get("item_name") or data.get("meal_name")
    if not item_name:
        return jsonify({"error": "Missing item_name in request body."}), 400

    result = reevaluate_macros(item_name)
    result["protein_g"] = result["protein"]
    result["carbs_g"] = result["carbs"]
    result["fat_g"] = result["fat"]
    result["estimated_calories"] = result["calories"]
    return jsonify(result), 200


# ------------------------------------------------------------------------------
# Saved Recipes & Batch Meal Prep Routes
# ------------------------------------------------------------------------------

@nutrition_bp.route("/recipes", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def list_recipes():
    """
    Retrieves all saved recipes / meal preps for the authenticated athlete.
    """
    user_id = get_jwt_identity() or "1"
    query = request.args.get("q") or request.args.get("query")
    recipes = get_user_recipes(user_id=user_id, search_query=query)
    return jsonify({"recipes": recipes, "count": len(recipes)}), 200


@nutrition_bp.route("/recipes", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def add_recipe():
    """
    Creates a new batch recipe or meal prep.
    """
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}
    name = data.get("name") or data.get("meal_name")
    if not name:
        return jsonify({"error": "Missing required field: name"}), 400

    servings = float(data.get("servings") or 1.0)
    ingredients = data.get("ingredients") or []
    
    result = create_recipe(
        user_id=user_id,
        name=name,
        servings=servings,
        ingredients=ingredients,
        total_calories=data.get("total_calories"),
        total_protein=data.get("total_protein"),
        total_carbs=data.get("total_carbs"),
        total_fat=data.get("total_fat"),
        per_serving_calories=data.get("per_serving_calories"),
        per_serving_protein=data.get("per_serving_protein"),
        per_serving_carbs=data.get("per_serving_carbs"),
        per_serving_fat=data.get("per_serving_fat"),
        image_url=data.get("image_url", ""),
        tags=data.get("tags"),
        notes=data.get("notes", "")
    )
    return jsonify(result), 201


@nutrition_bp.route("/recipes/<recipe_id>", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_single_recipe(recipe_id):
    """
    Fetches a single recipe by ID.
    """
    user_id = get_jwt_identity() or "1"
    recipe = get_recipe(user_id=user_id, recipe_id=recipe_id)
    if not recipe:
        return jsonify({"error": "Recipe not found."}), 404
    return jsonify({"recipe": recipe}), 200


@nutrition_bp.route("/recipes/<recipe_id>/log", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def log_recipe(recipe_id):
    """
    Quick-logs a chosen portion/serving of a saved recipe.
    """
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}
    servings = float(data.get("servings") or 1.0)
    date = data.get("date")
    meal_type = data.get("meal_type", "meal")
    notes = data.get("notes", "")

    result = log_recipe_portion(
        user_id=user_id,
        recipe_id=recipe_id,
        servings=servings,
        date=date,
        meal_type=meal_type,
        notes=notes
    )
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 201


@nutrition_bp.route("/recipes/<recipe_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required(optional=True)
def remove_recipe(recipe_id):
    """
    Deletes a saved recipe.
    """
    user_id = get_jwt_identity() or "1"
    result = delete_recipe(user_id=user_id, recipe_id=recipe_id)
    return jsonify(result), 200


@nutrition_bp.route("/recipes/match", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def match_saved_recipe():
    """
    Matches food item text / ingredients against the user's saved recipes.
    """
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}
    meal_name = data.get("meal_name") or data.get("item_name")
    ingredients = data.get("ingredients") or []

    matches = match_recipe(user_id=user_id, meal_name=meal_name, ingredients=ingredients)
    return jsonify({"matches": matches, "count": len(matches)}), 200


# ------------------------------------------------------------------------------
# Meal Logging & History Routes
# ------------------------------------------------------------------------------

@nutrition_bp.route("/log", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def log_meal():
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}
    
    meal_name = data.get("meal_name") or data.get("item_name")
    if not meal_name:
        return jsonify({"error": "Missing required field: meal_name"}), 400

    # Auto-calculate if not fully provided
    if not all(k in data for k in ["calories", "protein", "carbs", "fat"]):
        re_est = reevaluate_macros(meal_name)
        calories = float(data.get("calories", re_est["calories"]))
        protein = float(data.get("protein", re_est["protein"]))
        carbs = float(data.get("carbs", re_est["carbs"]))
        fat = float(data.get("fat", re_est["fat"]))
    else:
        calories = float(data["calories"])
        protein = float(data["protein"])
        carbs = float(data["carbs"])
        fat = float(data["fat"])
            
    log_date = data.get("date", datetime.now(timezone.utc).date().isoformat())
    created_ts = datetime.now(timezone.utc).isoformat()
    image_url = data.get("image_url", "")
    quality_score = int(data.get("quality_score", 8))
    coach_notes = data.get("coach_notes", "Fueling logged successfully.")
    meal_type = data.get("meal_type", "meal")

    meal_doc = {
        "user_id": user_id,
        "date": log_date,
        "logged_at": created_ts,
        "meal_name": meal_name,
        "item_name": meal_name,
        "meal_type": meal_type,
        "calories": calories,
        "protein": protein,
        "protein_g": protein,
        "carbs": carbs,
        "carbs_g": carbs,
        "fat": fat,
        "fat_g": fat,
        "quality_score": quality_score,
        "coach_notes": coach_notes,
        "image_url": image_url,
        "created_at": created_ts
    }
    
    saved_log = dict(meal_doc)
    try:
        m_res = supabase.table("meals").insert(meal_doc).execute()
        if m_res.data:
            saved_log = m_res.data[0]
    except Exception as me:
        logger.warning(f"Failed inserting into meals table, falling back to nutrition_logs: {me}")
        try:
            nl_res = supabase.table("nutrition_logs").insert(meal_doc).execute()
            if nl_res.data:
                saved_log = nl_res.data[0]
        except Exception as nle:
            logger.warning(f"Offline / mock fallback for meal insert: {nle}")

    return jsonify({"message": "Meal logged successfully.", "log": saved_log}), 201


@nutrition_bp.route("/history", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_nutrition_history():
    user_id = get_jwt_identity() or "1"
    today_str = datetime.now(timezone.utc).date().isoformat()
    start_date = request.args.get("start_date") or today_str
    end_date = request.args.get("end_date") or today_str
    
    try:
        summary = get_multi_day_nutrition_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Error fetching nutrition history: {e}")
        return jsonify({"error": str(e)}), 500


@nutrition_bp.route("/logs/<log_id>", methods=["GET"], strict_slashes=False)
@nutrition_bp.route("/meals/<log_id>", methods=["GET"], strict_slashes=False)
@jwt_required(optional=True)
def get_single_nutrition_log(log_id):
    user_id = get_jwt_identity() or "1"
    try:
        res = supabase.table("meals").select("*").eq("id", log_id).execute()
        if res.data and len(res.data) > 0:
            return jsonify({"log": res.data[0]}), 200
        res_nl = supabase.table("nutrition_logs").select("*").eq("id", log_id).execute()
        if res_nl.data and len(res_nl.data) > 0:
            return jsonify({"log": res_nl.data[0]}), 200
        return jsonify({"error": "Meal log not found."}), 404
    except Exception as e:
        logger.error(f"Error fetching log {log_id}: {e}")
        return jsonify({"error": str(e)}), 500


@nutrition_bp.route("/estimate", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def estimate_nutrition():
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}
    if not data.get("image_base64"):
        return jsonify({"error": "Missing image_base64 in request body."}), 400
        
    base64_str = data["image_base64"]
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
        
    try:
        image_data = base64.b64decode(base64_str)
        from .vision_service import analyze_meal_image
        analysis = analyze_meal_image(image_data)
        # Check for matched recipes
        matches = match_recipe(user_id=user_id, meal_name=analysis.get("meal_name"), ingredients=analysis.get("identified_ingredients"))
        analysis["matched_recipes"] = matches
        return jsonify(analysis), 200
    except Exception as e:
        logger.error(f"Error estimating nutrition: {e}")
        return jsonify({"error": str(e)}), 500


@nutrition_bp.route("/analyze-photo", methods=["POST"], strict_slashes=False)
@jwt_required(optional=True)
def analyze_photo():
    user_id = get_jwt_identity() or "1"
    image_bytes = None
    if 'image' in request.files:
        image_bytes = request.files['image'].read()
    elif request.is_json and request.json and 'image_base64' in request.json:
        base64_str = request.json['image_base64']
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        image_bytes = base64.b64decode(base64_str)
        
    if not image_bytes:
        return jsonify({'error': 'No image provided'}), 400
        
    from .vision_service import analyze_meal_image
    analysis = analyze_meal_image(image_bytes)
    # Check for matched recipes
    matches = match_recipe(user_id=user_id, meal_name=analysis.get("meal_name"), ingredients=analysis.get("identified_ingredients"))
    analysis["matched_recipes"] = matches
    return jsonify(analysis), 200


@nutrition_bp.route("/logs/<log_id>", methods=["PUT"], strict_slashes=False)
@nutrition_bp.route("/meals/<log_id>", methods=["PUT"], strict_slashes=False)
@jwt_required(optional=True)
def update_nutrition_log(log_id):
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}

    item_name = data.get("item_name") or data.get("meal_name")
    
    existing_log = None
    try:
        res = supabase.table("meals").select("*").eq("id", log_id).execute()
        if res.data and len(res.data) > 0:
            existing_log = res.data[0]
        else:
            res_nl = supabase.table("nutrition_logs").select("*").eq("id", log_id).execute()
            if res_nl.data and len(res_nl.data) > 0:
                existing_log = res_nl.data[0]
    except Exception as e:
        logger.warning(f"Could not query existing log {log_id}: {e}")

    final_meal_name = item_name or (existing_log.get("meal_name") if existing_log else "Updated Meal")

    if all(k in data for k in ["calories", "protein", "carbs", "fat"]):
        calories = float(data["calories"])
        protein = float(data["protein"])
        carbs = float(data["carbs"])
        fat = float(data["fat"])
    else:
        macros = reevaluate_macros(final_meal_name)
        calories = float(data.get("calories", macros["calories"]))
        protein = float(data.get("protein", macros["protein"]))
        carbs = float(data.get("carbs", macros["carbs"]))
        fat = float(data.get("fat", macros["fat"]))

    update_payload = {
        "meal_name": final_meal_name,
        "item_name": final_meal_name,
        "calories": calories,
        "protein": protein,
        "protein_g": protein,
        "carbs": carbs,
        "carbs_g": carbs,
        "fat": fat,
        "fat_g": fat,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if "date" in data:
        update_payload["date"] = data["date"]
    if "meal_type" in data:
        update_payload["meal_type"] = data["meal_type"]
    if "coach_notes" in data:
        update_payload["coach_notes"] = data["coach_notes"]

    updated_data = {**update_payload, "id": log_id, "user_id": user_id}
    try:
        supabase.table("meals").update(update_payload).eq("id", log_id).execute()
        supabase.table("nutrition_logs").update(update_payload).eq("id", log_id).execute()
    except Exception as e:
        logger.warning(f"Could not persist nutrition log update {log_id} to DB (mock fallback): {e}")

    response_body = {
        "message": "Log updated successfully.",
        "log": updated_data,
        "id": log_id,
        "meal_name": final_meal_name,
        "item_name": final_meal_name,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat
    }
    return jsonify(response_body), 200


@nutrition_bp.route("/logs/<log_id>", methods=["DELETE"], strict_slashes=False)
@nutrition_bp.route("/meals/<log_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required(optional=True)
def delete_nutrition_log(log_id):
    user_id = get_jwt_identity() or "1"
    try:
        supabase.table("meals").delete().eq("id", log_id).execute()
        supabase.table("nutrition_logs").delete().eq("id", log_id).execute()
        return jsonify({"message": "Log deleted successfully.", "id": log_id}), 200
    except Exception as e:
        logger.error(f"Error deleting nutrition log {log_id}: {e}")
        return jsonify({"error": str(e)}), 500
