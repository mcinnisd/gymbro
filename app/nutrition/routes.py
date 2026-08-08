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

