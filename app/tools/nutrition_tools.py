# app/tools/nutrition_tools.py

import logging
from datetime import datetime, timezone
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def log_meal(user_id: str, meal_name: str, calories: float, protein: float, carbs: float, fat: float) -> dict:
    """
    Logs a meal for the user with specified macronutrients.
    """
    try:
        meal_doc = {
            "user_id": int(user_id),
            "date": datetime.now(timezone.utc).date().isoformat(),
            "meal_name": meal_name,
            "calories": float(calories),
            "protein": float(protein),
            "carbs": float(carbs),
            "fat": float(fat),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        res = supabase.table("nutrition_logs").insert(meal_doc).execute()
        if res.data:
            return {
                "status": "success",
                "message": f"Successfully logged meal: '{meal_name}' ({int(calories)} kcal, P: {int(protein)}g, C: {int(carbs)}g, F: {int(fat)}g)"
            }
        return {"status": "error", "message": "Failed to log meal to database."}
    except Exception as e:
        logger.error(f"Error in log_meal tool: {e}")
        return {"status": "error", "message": str(e)}
