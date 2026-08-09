# app/nutrition/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
import json
import base64
from app.supabase_client import supabase
from google.genai import types as google_genai_types
from app.config import Config
from app.utils.helpers import extract_json_from_text
from app.utils.llm_utils import get_gemini_client
import logging

nutrition_bp = Blueprint('nutrition', __name__)
logger = logging.getLogger(__name__)

@nutrition_bp.route("/log", methods=["POST"], strict_slashes=False)
@jwt_required()
def log_meal():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required = ["meal_name", "calories", "protein", "carbs", "fat"]
    for r in required:
        if r not in data:
            return jsonify({"error": f"Missing required field: {r}"}), 400
            
    meal_doc = {
        "user_id": int(user_id),
        "date": data.get("date", datetime.now(timezone.utc).date().isoformat()),
        "meal_name": data["meal_name"],
        "calories": float(data["calories"]),
        "protein": float(data["protein"]),
        "carbs": float(data["carbs"]),
        "fat": float(data["fat"]),
        "image_url": data.get("image_url", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        res = supabase.table("nutrition_logs").insert(meal_doc).execute()
        if res.data:
            return jsonify({"message": "Meal logged successfully.", "log": res.data[0]}), 201
        return jsonify({"error": "Failed to log meal."}), 500
    except Exception as e:
        logger.error(f"Error logging meal: {e}")
        return jsonify({"error": str(e)}), 500

@nutrition_bp.route("/history", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_nutrition_history():
    user_id = get_jwt_identity()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    try:
        query = supabase.table("nutrition_logs").select("*").eq("user_id", user_id)
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
            
        res = query.order("created_at", desc=True).execute()
        logs = res.data or []
        
        # Calculate daily aggregates
        daily_sums = {}
        for log in logs:
            d = log["date"]
            if d not in daily_sums:
                daily_sums[d] = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
            daily_sums[d]["calories"] += float(log["calories"])
            daily_sums[d]["protein"] += float(log["protein"])
            daily_sums[d]["carbs"] += float(log["carbs"])
            daily_sums[d]["fat"] += float(log["fat"])
            
        return jsonify({
            "logs": logs,
            "daily_summaries": daily_sums
        }), 200
    except Exception as e:
        logger.error(f"Error fetching nutrition history: {e}")
        return jsonify({"error": str(e)}), 500

@nutrition_bp.route("/estimate", methods=["POST"], strict_slashes=False)
@jwt_required()
def estimate_nutrition():
    if not Config.USE_VERTEX_AI and not Config.GEMINI_API_KEY:
        return jsonify({"error": "Gemini/Vertex AI is not configured on backend."}), 500
        
    data = request.get_json()
    if not data or not data.get("image_base64"):
        return jsonify({"error": "Missing image_base64 in request body."}), 400
        
    base64_str = data["image_base64"]
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
        
    try:
        image_data = base64.b64decode(base64_str)
        
        # Build prompt
        prompt = """
You are an expert nutritionist. Analyze this meal photo.
Estimate the name of the meal, ingredients, portion size, total calories, and macronutrients (protein, carbs, fat in grams).
Additionally, evaluate your confidence level (low, medium, high).
If your confidence is low/medium, provide 3 multiple choice questions that will help clarify the ingredients or portion sizes (e.g. "What type of milk was used?" or "How many slices of bread?").

Output your response strictly in the following JSON format:
{
  "meal_name": "Meal Name",
  "estimated_ingredients": ["ingredient 1", "ingredient 2"],
  "calories": 450,
  "protein": 25,
  "carbs": 40,
  "fat": 15,
  "confidence": "high",
  "clarifying_questions": [
    {
      "id": "q1",
      "question": "Question text?",
      "options": ["Option A", "Option B", "Option C"]
    }
  ]
}
"""
        # Call Gemini via unified client
        client = get_gemini_client()
        image_part = google_genai_types.Part.from_bytes(
            data=image_data,
            mime_type="image/jpeg"
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image_part, prompt]
        )
        text = response.text
        
        parsed = extract_json_from_text(text)
        if not parsed:
            return jsonify({"error": "Failed to parse nutrition estimation JSON from LLM response.", "raw": text}), 500
            
        return jsonify(parsed), 200
        
    except Exception as e:
        logger.error(f"Error estimating nutrition: {e}")
        return jsonify({"error": str(e)}), 500

@nutrition_bp.route("/analyze-photo", methods=["POST"], strict_slashes=False)
def analyze_photo():
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
    return jsonify(analysis), 200


def reevaluate_macros(item_name: str) -> dict:
    """
    Recalculates calories, protein, carbs, and fat dynamically based on item name and portion/quantity.
    Uses LLM if configured/available, with robust heuristic parsing fallback.
    """
    import re
    item_lower = item_name.lower()
    
    if Config.GEMINI_API_KEY or Config.USE_VERTEX_AI:
        try:
            client = get_gemini_client()
            prompt = f"""Estimate calories and macronutrients for this food item: "{item_name}".
Output ONLY valid JSON with keys: "calories", "protein", "carbs", "fat" (all numeric).
Example: {{"calories": 330, "protein": 62, "carbs": 0, "fat": 7.2}}
"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt]
            )
            parsed = extract_json_from_text(response.text)
            if parsed and all(k in parsed for k in ["calories", "protein", "carbs", "fat"]):
                return {
                    "calories": float(parsed["calories"]),
                    "protein": float(parsed["protein"]),
                    "carbs": float(parsed["carbs"]),
                    "fat": float(parsed["fat"])
                }
        except Exception as e:
            logger.warning(f"LLM macro re-evaluation failed, using heuristic: {e}")

    # Heuristic estimation parser
    grams_match = re.search(r'(\d+(?:\.\d+)?)\s*g(?:rams)?', item_lower)
    weight_g = float(grams_match.group(1)) if grams_match else None

    # Base density per gram defaults
    cal_per_g = 1.5
    p_per_g = 0.15
    c_per_g = 0.15
    f_per_g = 0.05

    if 'chicken' in item_lower or 'turkey' in item_lower:
        cal_per_g = 1.65
        p_per_g = 0.31
        c_per_g = 0.0
        f_per_g = 0.036
    elif 'steak' in item_lower or 'beef' in item_lower:
        cal_per_g = 2.5
        p_per_g = 0.26
        c_per_g = 0.0
        f_per_g = 0.15
    elif 'salmon' in item_lower or 'fish' in item_lower or 'tuna' in item_lower:
        cal_per_g = 2.0
        p_per_g = 0.22
        c_per_g = 0.0
        f_per_g = 0.13
    elif 'rice' in item_lower or 'oats' in item_lower or 'pasta' in item_lower or 'quinoa' in item_lower:
        cal_per_g = 1.3
        p_per_g = 0.03
        c_per_g = 0.28
        f_per_g = 0.005
    elif 'egg' in item_lower:
        egg_match = re.search(r'(\d+)\s*egg', item_lower)
        num_eggs = int(egg_match.group(1)) if egg_match else 2
        return {
            "calories": float(num_eggs * 70),
            "protein": float(num_eggs * 6),
            "carbs": float(num_eggs * 0.5),
            "fat": float(num_eggs * 5)
        }

    if weight_g is not None:
        return {
            "calories": round(weight_g * cal_per_g, 1),
            "protein": round(weight_g * p_per_g, 1),
            "carbs": round(weight_g * c_per_g, 1),
            "fat": round(weight_g * f_per_g, 1)
        }
    else:
        return {
            "calories": round(200 * cal_per_g, 1),
            "protein": round(200 * p_per_g, 1),
            "carbs": round(200 * c_per_g, 1),
            "fat": round(200 * f_per_g, 1)
        }


@nutrition_bp.route("/logs/<log_id>", methods=["PUT"], strict_slashes=False)
@jwt_required(optional=True)
def update_nutrition_log(log_id):
    user_id = get_jwt_identity() or "1"
    data = request.get_json() or {}

    item_name = data.get("item_name") or data.get("meal_name")
    
    existing_log = None
    try:
        res = supabase.table("nutrition_logs").select("*").eq("id", log_id).execute()
        if res.data and len(res.data) > 0:
            existing_log = res.data[0]
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
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        res = supabase.table("nutrition_logs").update(update_payload).eq("id", log_id).execute()
        updated_data = res.data[0] if (res.data and len(res.data) > 0) else {**update_payload, "id": log_id, "user_id": user_id}
        
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
    except Exception as e:
        logger.error(f"Error updating nutrition log {log_id}: {e}")
        return jsonify({"error": str(e)}), 500


@nutrition_bp.route("/logs/<log_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required(optional=True)
def delete_nutrition_log(log_id):
    user_id = get_jwt_identity() or "1"
    try:
        supabase.table("nutrition_logs").delete().eq("id", log_id).execute()
        return jsonify({"message": "Log deleted successfully.", "id": log_id}), 200
    except Exception as e:
        logger.error(f"Error deleting nutrition log {log_id}: {e}")
        return jsonify({"error": str(e)}), 500


