# app/nutrition/adaptive_targets.py

import logging
import re
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timezone, timedelta
from app.supabase_client import supabase
from app.config import Config
from app.utils.helpers import extract_json_from_text
from app.utils.llm_utils import get_gemini_client

logger = logging.getLogger(__name__)


def reevaluate_macros(item_name: str) -> Dict[str, Any]:
    """
    Recalculates calories, protein, carbs, and fat dynamically based on item name,
    quantity, and portion size. Attempts LLM estimation if available, with robust sports nutrition
    density parsing heuristics as primary/fallback.
    """
    item_lower = item_name.lower().strip()

    # 1. LLM Structured Estimation if configured
    if Config.GEMINI_API_KEY or Config.USE_VERTEX_AI:
        try:
            client = get_gemini_client()
            prompt = f"""You are a sports nutritionist. Estimate calories and macronutrients for: "{item_name}".
Output ONLY valid JSON with keys "calories", "protein", "carbs", "fat" (all numeric values).
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
                    "fat": float(parsed["fat"]),
                    "item_name": item_name
                }
        except Exception as e:
            logger.warning(f"LLM macro re-evaluation fallback to heuristic: {e}")

    # 2. Heuristic Sports Nutrition Parser
    # Eggs
    if 'egg' in item_lower and 'white' not in item_lower:
        egg_match = re.search(r'(\d+)\s*(?:[a-z]+\s+)*egg', item_lower)
        num_eggs = int(egg_match.group(1)) if egg_match else 2
        return {
            "calories": float(num_eggs * 70),
            "protein": float(num_eggs * 6),
            "carbs": float(round(num_eggs * 0.5, 1)),
            "fat": float(num_eggs * 5),
            "item_name": item_name
        }
    elif 'egg white' in item_lower or 'egg whites' in item_lower:
        ew_match = re.search(r'(\d+)\s*(?:[a-z]+\s+)*white', item_lower)
        num_whites = int(ew_match.group(1)) if ew_match else 3
        return {
            "calories": float(num_whites * 17),
            "protein": float(round(num_whites * 3.6, 1)),
            "carbs": float(round(num_whites * 0.2, 1)),
            "fat": float(round(num_whites * 0.1, 1)),
            "item_name": item_name
        }

    # Whey / Protein Powder Scoops
    if 'scoop' in item_lower or 'whey' in item_lower or 'casein' in item_lower:
        scoop_match = re.search(r'(\d+(?:\.\d+)?)\s*scoop', item_lower)
        num_scoops = float(scoop_match.group(1)) if scoop_match else 1.0
        return {
            "calories": float(round(num_scoops * 120)),
            "protein": float(round(num_scoops * 25, 1)),
            "carbs": float(round(num_scoops * 2.5, 1)),
            "fat": float(round(num_scoops * 1.5, 1)),
            "item_name": item_name
        }

    # Bread / Slices
    if 'slice' in item_lower:
        slice_match = re.search(r'(\d+)\s*slice', item_lower)
        num_slices = int(slice_match.group(1)) if slice_match else 2
        return {
            "calories": float(num_slices * 80),
            "protein": float(num_slices * 3),
            "carbs": float(num_slices * 15),
            "fat": float(num_slices * 1),
            "item_name": item_name
        }

    # Tablespoons (Tbsp)
    if 'tbsp' in item_lower or 'tablespoon' in item_lower:
        tbsp_match = re.search(r'(\d+(?:\.\d+)?)\s*t(?:a)?b(?:le)?sp', item_lower)
        num_tbsp = float(tbsp_match.group(1)) if tbsp_match else 1.0
        if 'peanut butter' in item_lower or 'almond butter' in item_lower:
            return {
                "calories": float(round(num_tbsp * 95)),
                "protein": float(round(num_tbsp * 4, 1)),
                "carbs": float(round(num_tbsp * 3.5, 1)),
                "fat": float(round(num_tbsp * 8, 1)),
                "item_name": item_name
            }
        else: # Oil / butter
            return {
                "calories": float(round(num_tbsp * 120)),
                "protein": 0.0,
                "carbs": 0.0,
                "fat": float(round(num_tbsp * 14, 1)),
                "item_name": item_name
            }

    # Extract weight in grams or ounces
    grams_match = re.search(r'(\d+(?:\.\d+)?)\s*g(?:rams)?', item_lower)
    oz_match = re.search(r'(\d+(?:\.\d+)?)\s*oz', item_lower)
    
    if grams_match:
        weight_g = float(grams_match.group(1))
    elif oz_match:
        weight_g = float(oz_match.group(1)) * 28.35
    else:
        weight_g = None

    # Base density per gram defaults (cal/g, P/g, C/g, F/g)
    cal_per_g = 1.5
    p_per_g = 0.15
    c_per_g = 0.15
    f_per_g = 0.05

    if 'chicken breast' in item_lower or 'turkey breast' in item_lower:
        cal_per_g = 1.65
        p_per_g = 0.31
        c_per_g = 0.0
        f_per_g = 0.036
    elif 'chicken' in item_lower or 'turkey' in item_lower:
        cal_per_g = 1.85
        p_per_g = 0.27
        c_per_g = 0.0
        f_per_g = 0.075
    elif 'salmon' in item_lower or 'trout' in item_lower:
        cal_per_g = 2.08
        p_per_g = 0.22
        c_per_g = 0.0
        f_per_g = 0.13
    elif 'tuna' in item_lower or 'cod' in item_lower or 'shrimp' in item_lower or 'tilapia' in item_lower:
        cal_per_g = 1.1
        p_per_g = 0.24
        c_per_g = 0.0
        f_per_g = 0.015
    elif 'ribeye' in item_lower or '80/20' in item_lower:
        cal_per_g = 2.6
        p_per_g = 0.22
        c_per_g = 0.0
        f_per_g = 0.19
    elif 'steak' in item_lower or 'beef' in item_lower or 'sirloin' in item_lower or 'bison' in item_lower:
        cal_per_g = 2.2
        p_per_g = 0.26
        c_per_g = 0.0
        f_per_g = 0.12
    elif 'rice' in item_lower or 'jasmine' in item_lower or 'quinoa' in item_lower or 'pasta' in item_lower:
        cal_per_g = 1.30
        p_per_g = 0.027
        c_per_g = 0.28
        f_per_g = 0.004
    elif 'oat' in item_lower:
        cal_per_g = 3.8
        p_per_g = 0.13
        c_per_g = 0.68
        f_per_g = 0.07
    elif 'sweet potato' in item_lower or 'potato' in item_lower:
        cal_per_g = 0.9
        p_per_g = 0.02
        c_per_g = 0.21
        f_per_g = 0.002
    elif 'greek yogurt' in item_lower or 'cottage cheese' in item_lower:
        cal_per_g = 0.75
        p_per_g = 0.10
        c_per_g = 0.04
        f_per_g = 0.015
    elif 'avocado' in item_lower:
        cal_per_g = 1.6
        p_per_g = 0.02
        c_per_g = 0.09
        f_per_g = 0.15
    elif 'banana' in item_lower:
        return {"calories": 105.0, "protein": 1.3, "carbs": 27.0, "fat": 0.3, "item_name": item_name}

    effective_weight = weight_g if weight_g is not None else 200.0

    return {
        "calories": float(round(effective_weight * cal_per_g, 1)),
        "protein": float(round(effective_weight * p_per_g, 1)),
        "carbs": float(round(effective_weight * c_per_g, 1)),
        "fat": float(round(effective_weight * f_per_g, 1)),
        "item_name": item_name
    }


def calculate_bmr_tdee(profile: Dict[str, Any]) -> Tuple[float, float]:
    """
    Calculates Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE)
    using the Mifflin-St Jeor equation with fallback defaults.
    """
    weight_kg = float(profile.get("weight") or 75.0)
    height_cm = float(profile.get("height") or 175.0)
    age = int(profile.get("age") or 30)
    gender = str(profile.get("gender") or "male").lower()

    s = -161 if gender == "female" else 5
    bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + s

    lifestyle = str(profile.get("lifestyle") or "moderately_active").lower()
    if "sedentary" in lifestyle:
        activity_multiplier = 1.2
    elif "light" in lifestyle:
        activity_multiplier = 1.375
    elif "very_active" in lifestyle or "athlete" in lifestyle:
        activity_multiplier = 1.725
    elif "active" in lifestyle:
        activity_multiplier = 1.55
    else:
        activity_multiplier = 1.5

    tdee = bmr * activity_multiplier
    return bmr, tdee


def calculate_adaptive_nutrition_targets(
    profile: Dict[str, Any],
    target_date: Optional[str] = None,
    training_data: Optional[Dict[str, Any]] = None,
    goal_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculates goal-adaptive daily nutrition targets adapted to athlete profile,
    multi-objective Goal Set, and daily training load.
    """
    bmr, tdee = calculate_bmr_tdee(profile)
    weight_kg = float(profile.get("weight") or 75.0)

    goals = profile.get("goals") or {}
    primary_goal = (
        goal_override or 
        goals.get("primary_goal") or 
        goals.get("goal_type") or 
        profile.get("archetype") or 
        "maintenance"
    ).lower()

    # Determine Base Goal Modifiers
    if any(g in primary_goal for g in ["marathon", "endurance", "running", "cycling", "triathlon"]):
        goal_category = "endurance"
        cal_target = tdee
        protein_per_kg = 1.7
        fat_ratio = 0.25
    elif any(g in primary_goal for g in ["hypertrophy", "muscle", "mass", "bulk"]):
        goal_category = "hypertrophy"
        cal_target = tdee + 300
        protein_per_kg = 2.2
        fat_ratio = 0.25
    elif any(g in primary_goal for g in ["fat_loss", "cutting", "cut", "weight_loss"]):
        goal_category = "cutting"
        cal_target = max(tdee - 450, 1500)
        protein_per_kg = 2.4
        fat_ratio = 0.22
    elif any(g in primary_goal for g in ["recomp", "body_recomposition"]):
        goal_category = "recomp"
        cal_target = tdee
        protein_per_kg = 2.2
        fat_ratio = 0.25
    elif any(g in primary_goal for g in ["strength", "powerlifting"]):
        goal_category = "strength"
        cal_target = tdee + 150
        protein_per_kg = 2.0
        fat_ratio = 0.28
    else:
        goal_category = "maintenance"
        cal_target = tdee
        protein_per_kg = 1.8
        fat_ratio = 0.25

    # Check for Training Day Energy Adaptation
    training_bonus_cal = 0
    training_bonus_carbs = 0
    target_note = f"Base {goal_category.capitalize()} targets."

    if training_data:
        cal_burned = float(training_data.get("calories_burned") or 0)
        dist_km = float(training_data.get("distance_km") or 0)
        workout_type = str(training_data.get("workout_type") or "").lower()

        if cal_burned > 300 or dist_km > 5.0 or (workout_type not in ["rest", "none", ""]):
            if cal_burned > 0:
                training_bonus_cal = round(cal_burned * 0.7)
            elif dist_km > 0:
                training_bonus_cal = round(dist_km * 60 * 0.7)
            else:
                training_bonus_cal = 250

            training_bonus_carbs = round((training_bonus_cal * 0.75) / 4.0)
            bonus_fat = round((training_bonus_cal * 0.25) / 9.0)

            target_note = (
                f"Training Fueling Bonus active: +{training_bonus_cal} kcal "
                f"(+{training_bonus_carbs}g carbs) for {workout_type or 'workout'} performance & recovery."
            )
        else:
            bonus_fat = 0
    else:
        bonus_fat = 0

    total_calories = round(cal_target + training_bonus_cal)
    protein_g = round(weight_kg * protein_per_kg)
    protein_cals = protein_g * 4

    fat_cals = (cal_target * fat_ratio) + (bonus_fat * 9)
    fat_g = round(fat_cals / 9.0)

    carb_cals = max(total_calories - protein_cals - (fat_g * 9), 0)
    carbs_g = round(carb_cals / 4.0)

    return {
        "date": target_date or datetime.now(timezone.utc).date().isoformat(),
        "goal_type": goal_category,
        "primary_goal": primary_goal,
        "calories": total_calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "bmr": round(bmr),
        "tdee": round(tdee),
        "training_day": bool(training_bonus_cal > 0),
        "target_note": target_note,
        "notes": target_note
    }


def calculate_adherence_score(
    actual: Dict[str, float],
    targets: Dict[str, Any]
) -> Tuple[float, Dict[str, Any]]:
    """
    Computes daily nutrition adherence score (0-100%) against targets.
    """
    act_cal = float(actual.get("calories") or 0)
    act_p = float(actual.get("protein") or actual.get("protein_g") or 0)
    act_c = float(actual.get("carbs") or actual.get("carbs_g") or 0)
    act_f = float(actual.get("fat") or actual.get("fat_g") or 0)

    tgt_cal = float(targets.get("calories") or 2500)
    tgt_p = float(targets.get("protein_g") or targets.get("protein") or 160)
    tgt_c = float(targets.get("carbs_g") or targets.get("carbs") or 250)
    tgt_f = float(targets.get("fat_g") or targets.get("fat") or 70)

    def calc_comp(act, tgt, tolerance):
        if tgt <= 0:
            return 1.0
        ratio = act / tgt
        diff = abs(ratio - 1.0)
        if diff <= tolerance:
            return 1.0
        return max(0.0, 1.0 - (diff - tolerance))

    cal_pct = calc_comp(act_cal, tgt_cal, 0.10)
    p_pct = calc_comp(act_p, tgt_p, 0.15)
    c_pct = calc_comp(act_c, tgt_c, 0.20)
    f_pct = calc_comp(act_f, tgt_f, 0.20)

    total_score = (cal_pct * 35.0) + (p_pct * 35.0) + (c_pct * 15.0) + (f_pct * 15.0)
    total_score = round(total_score, 1)

    breakdown = {
        "overall_score": total_score,
        "calories_adherence_pct": round((act_cal / max(tgt_cal, 1)) * 100, 1),
        "protein_adherence_pct": round((act_p / max(tgt_p, 1)) * 100, 1),
        "carbs_adherence_pct": round((act_c / max(tgt_c, 1)) * 100, 1),
        "fat_adherence_pct": round((act_f / max(tgt_f, 1)) * 100, 1)
    }

    return total_score, breakdown


def get_multi_day_nutrition_summary(
    user_id: Any,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Assembles multi-day nutritional logs, daily aggregates, goal-adaptive targets,
    and rolling compliance statistics.
    """
    # 1. Fetch User Profile
    profile = {}
    try:
        u_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if u_res.data:
            profile = u_res.data[0]
    except Exception as e:
        logger.warning(f"Error fetching user profile for nutrition summary: {e}")

    # 2. Fetch Meal Logs
    raw_logs = []
    seen_log_ids = set()

    # Query canonical meals table
    try:
        m_res = supabase.table("meals").select("*").eq("user_id", user_id).execute()
        if m_res.data:
            for m in m_res.data:
                logged_date = str(m.get("date") or (m.get("logged_at") or "")[:10] or "")[:10]
                if start_date <= logged_date <= end_date:
                    lid = m.get("id")
                    if lid:
                        seen_log_ids.add(str(lid))
                    raw_logs.append({
                        "id": lid,
                        "date": logged_date,
                        "meal_name": m.get("item_name") or m.get("meal_name") or "Logged Meal",
                        "item_name": m.get("item_name") or m.get("meal_name") or "Logged Meal",
                        "calories": float(m.get("calories") or 0),
                        "protein": float(m.get("protein_g") or m.get("protein") or 0),
                        "carbs": float(m.get("carbs_g") or m.get("carbs") or 0),
                        "fat": float(m.get("fat_g") or m.get("fat") or 0),
                        "quality_score": m.get("quality_score", 8),
                        "coach_notes": m.get("coach_notes", ""),
                        "image_url": m.get("image_url", ""),
                        "meal_type": m.get("meal_type", "meal"),
                        "created_at": m.get("logged_at") or m.get("created_at")
                    })
    except Exception as e:
        logger.warning(f"Error querying meals table: {e}")

    # Query nutrition_logs table (merging without duplicates)
    try:
        nl_res = supabase.table("nutrition_logs").select("*").eq("user_id", user_id).execute()
        if nl_res.data:
            for nl in nl_res.data:
                lid = str(nl.get("id") or "")
                if lid and lid in seen_log_ids:
                    continue
                d = str(nl.get("date") or "")[:10]
                if start_date <= d <= end_date:
                    raw_logs.append({
                        "id": nl.get("id"),
                        "date": d,
                        "meal_name": nl.get("meal_name") or "Logged Meal",
                        "item_name": nl.get("meal_name") or "Logged Meal",
                        "calories": float(nl.get("calories") or 0),
                        "protein": float(nl.get("protein") or 0),
                        "carbs": float(nl.get("carbs") or 0),
                        "fat": float(nl.get("fat") or 0),
                        "quality_score": nl.get("quality_score", 8),
                        "coach_notes": nl.get("coach_notes", ""),
                        "image_url": nl.get("image_url", ""),
                        "meal_type": nl.get("meal_type", "meal"),
                        "created_at": nl.get("created_at")
                    })
    except Exception as e:
        logger.warning(f"Error querying nutrition_logs table: {e}")

    # 3. Fetch Daily Activities / Training Load for adaptive adjustments
    activities_by_date: Dict[str, Dict[str, Any]] = {}
    try:
        act_res = supabase.table("garmin_activities").select("*").eq("user_id", user_id).execute()
        if act_res.data:
            for act in act_res.data:
                ad = str(act.get("start_time_local") or "")[:10]
                if start_date <= ad <= end_date:
                    if ad not in activities_by_date:
                        activities_by_date[ad] = {"calories_burned": 0, "distance_km": 0, "workout_type": act.get("activity_type", "workout")}
                    activities_by_date[ad]["calories_burned"] += float(act.get("calories") or 0)
                    activities_by_date[ad]["distance_km"] += float(act.get("distance") or 0) / 1000.0
    except Exception as e:
        logger.warning(f"Error fetching activities for adaptive nutrition: {e}")

    # 4. Aggregate daily totals & compute adaptive targets
    daily_summaries: Dict[str, Dict[str, float]] = {}
    for log in raw_logs:
        d = log["date"]
        if d not in daily_summaries:
            daily_summaries[d] = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "meal_count": 0}
        daily_summaries[d]["calories"] += log["calories"]
        daily_summaries[d]["protein"] += log["protein"]
        daily_summaries[d]["carbs"] += log["carbs"]
        daily_summaries[d]["fat"] += log["fat"]
        daily_summaries[d]["meal_count"] += 1

    daily_targets: Dict[str, Any] = {}
    daily_adherence: Dict[str, Any] = {}
    
    try:
        s_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        curr_dt = s_dt
        while curr_dt <= e_dt:
            d_str = curr_dt.isoformat()
            t_data = activities_by_date.get(d_str)
            target = calculate_adaptive_nutrition_targets(
                profile=profile,
                target_date=d_str,
                training_data=t_data
            )
            daily_targets[d_str] = target

            if d_str in daily_summaries:
                score, breakdown = calculate_adherence_score(daily_summaries[d_str], target)
                daily_adherence[d_str] = {"score": score, **breakdown}

            curr_dt += timedelta(days=1)
    except Exception as e:
        logger.warning(f"Date range generation error: {e}")

    num_days_logged = len(daily_summaries)
    if num_days_logged > 0:
        avg_cal = sum(s["calories"] for s in daily_summaries.values()) / num_days_logged
        avg_p = sum(s["protein"] for s in daily_summaries.values()) / num_days_logged
        avg_c = sum(s["carbs"] for s in daily_summaries.values()) / num_days_logged
        avg_f = sum(s["fat"] for s in daily_summaries.values()) / num_days_logged
        period_averages = {
            "avg_calories": round(avg_cal, 1),
            "avg_protein": round(avg_p, 1),
            "avg_carbs": round(avg_c, 1),
            "avg_fat": round(avg_f, 1),
            "days_logged": num_days_logged
        }
    else:
        period_averages = {"avg_calories": 0, "avg_protein": 0, "avg_carbs": 0, "avg_fat": 0, "days_logged": 0}

    coach_summary = (
        f"Tracking {num_days_logged} days. Goal: {profile.get('goals', {}).get('primary_goal', 'Athletic Fueling')}. "
        "Macros are dynamically adjusted for training load and recovery."
    )

    return {
        "logs": sorted(raw_logs, key=lambda x: str(x.get("created_at") or ""), reverse=True),
        "daily_summaries": daily_summaries,
        "daily_targets": daily_targets,
        "daily_adherence": daily_adherence,
        "period_averages": period_averages,
        "coach_summary": coach_summary
    }
