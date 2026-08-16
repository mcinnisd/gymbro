# app/tools/nutrition_tools.py

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.supabase_client import supabase
from app.nutrition.adaptive_targets import (
    calculate_adaptive_nutrition_targets,
    get_multi_day_nutrition_summary,
    reevaluate_macros
)

logger = logging.getLogger(__name__)


def log_meal(
    user_id: str,
    meal_name: str,
    calories: Optional[float] = None,
    protein: Optional[float] = None,
    carbs: Optional[float] = None,
    fat: Optional[float] = None,
    meal_type: str = "meal",
    quality_score: int = 8,
    coach_notes: str = ""
) -> Dict[str, Any]:
    """
    Logs a meal for the user with specified macronutrients or automatic calculation.
    """
    try:
        # If macros missing, calculate dynamically
        if calories is None or protein is None or carbs is None or fat is None:
            re_est = reevaluate_macros(meal_name)
            cal_val = float(calories if calories is not None else re_est["calories"])
            p_val = float(protein if protein is not None else re_est["protein"])
            c_val = float(carbs if carbs is not None else re_est["carbs"])
            f_val = float(fat if fat is not None else re_est["fat"])
        else:
            cal_val = float(calories)
            p_val = float(protein)
            c_val = float(carbs)
            f_val = float(fat)

        now_iso = datetime.now(timezone.utc).isoformat()
        today_date = datetime.now(timezone.utc).date().isoformat()

        meal_doc = {
            "user_id": user_id,
            "date": today_date,
            "logged_at": now_iso,
            "meal_name": meal_name,
            "item_name": meal_name,
            "meal_type": meal_type,
            "calories": cal_val,
            "protein": p_val,
            "protein_g": p_val,
            "carbs": c_val,
            "carbs_g": c_val,
            "fat": f_val,
            "fat_g": f_val,
            "quality_score": quality_score,
            "coach_notes": coach_notes or f"Balanced fueling for {meal_name}.",
            "created_at": now_iso
        }

        # Attempt write to canonical meals and nutrition_logs tables
        try:
            supabase.table("meals").insert(meal_doc).execute()
        except Exception as me:
            logger.warning(f"Failed inserting into meals table in tool: {me}")

        try:
            supabase.table("nutrition_logs").insert(meal_doc).execute()
        except Exception as nle:
            logger.warning(f"Failed inserting into nutrition_logs table in tool: {nle}")

        obs = f"Successfully logged meal: '{meal_name}' ({int(cal_val)} kcal, P: {int(p_val)}g, C: {int(c_val)}g, F: {int(f_val)}g)"
        return {
            "success": True,
            "status": "success",
            "observation": obs,
            "message": obs,
            "data": meal_doc,
            "log": meal_doc
        }
    except Exception as e:
        logger.error(f"Error in log_meal tool: {e}")
        return {"success": False, "status": "error", "error": str(e), "message": str(e)}


def get_nutrition_history(
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves multi-day nutrition history with goal-adaptive targets and adherence statistics.
    """
    today_str = datetime.now(timezone.utc).date().isoformat()
    s_date = start_date or today_str
    e_date = end_date or today_str
    try:
        summary = get_multi_day_nutrition_summary(user_id=user_id, start_date=s_date, end_date=e_date)
        return {
            "success": True,
            "status": "success",
            "observation": summary.get("coach_summary", "Retrieved multi-day nutrition history."),
            "data": summary,
            **summary
        }
    except Exception as e:
        logger.error(f"Error in get_nutrition_history tool: {e}")
        return {"success": False, "status": "error", "error": str(e), "logs": [], "daily_summaries": {}}


def reevaluate_meal_macros(item_name: str) -> Dict[str, Any]:
    """
    Re-evaluates calories, protein, carbs, and fat dynamically from a food description text.
    """
    res = reevaluate_macros(item_name)
    return {
        "success": True,
        "status": "success",
        "observation": f"Estimated {item_name}: {int(res['calories'])} kcal (P: {int(res['protein'])}g, C: {int(res['carbs'])}g, F: {int(res['fat'])}g)",
        "data": res,
        **res
    }


def get_adaptive_nutrition_targets(
    user_id: str,
    target_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetches athlete profile and calculates dynamic goal-adaptive nutrition targets.
    """
    profile = {}
    try:
        u_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if u_res.data:
            profile = u_res.data[0]
    except Exception as e:
        logger.warning(f"Error fetching user profile in get_adaptive_nutrition_targets: {e}")

    t_date = target_date or datetime.now(timezone.utc).date().isoformat()
    targets = calculate_adaptive_nutrition_targets(profile=profile, target_date=t_date)
    return {
        "success": True,
        "status": "success",
        "observation": targets.get("target_note", "Calculated adaptive macro targets."),
        "data": targets,
        **targets
    }
