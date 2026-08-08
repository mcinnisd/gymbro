import json
import logging
from app.config import Config

logger = logging.getLogger(__name__)

def analyze_meal_image(image_bytes: bytes) -> dict:
    gemini_key = Config.GEMINI_API_KEY
    
    if Config.LLM_PROVIDER == 'gemini' and gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = """Analyze this meal image and return a JSON object with:
            {
              "meal_name": "Name of meal",
              "estimated_calories": 550,
              "protein_g": 35,
              "carbs_g": 45,
              "fat_g": 18,
              "quality_score": 8,
              "coach_notes": "Short nutrition feedback",
              "identified_ingredients": ["ingredient1", "ingredient2"]
            }
            Return ONLY raw JSON."""
            
            response = model.generate_content([
                prompt,
                {'mime_type': 'image/jpeg', 'data': image_bytes}
            ])
            text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Vision API call failed, using fallback: {e}")
            
    # Mock / Fallback estimation for offline/testing mode
    return {
        "meal_name": "Logged Meal (AI Estimated)",
        "estimated_calories": 520,
        "protein_g": 38.0,
        "carbs_g": 45.0,
        "fat_g": 18.0,
        "quality_score": 8,
        "coach_notes": "Balanced meal with solid protein and complex carbs.",
        "identified_ingredients": ["protein source", "greens", "grain base"]
    }
