# app/nutrition/adaptive_targets.py

import logging
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timezone, timedelta
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def calculate_bmr_tdee(profile: Dict[str, Any]) -> Tuple[float, float]:
    """
    Calculates Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE)
    using the Mifflin-St Jeor equation with fallback defaults.
    """
    weight_kg = float(profile.get("weight") or 75.0)
    height_cm = float(profile.get("height") or 175.0)
    age = int(profile.get("age") or 30)
    gender = str(profile.get("gender") or "male").lower()

    # Mifflin-St Jeor Equation:
    # BMR = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + s
    # s = +5 for males, -161 for females
    s = -161 if gender == "female" else 5
    bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + s

    # Physical Activity Level (PAL) multiplier
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
        protein_per_kg = 1.7  # 1.6 - 1.8 g/kg
        fat_ratio = 0.25      # 25% of calories
    elif any(g in primary_goal for g in ["hypertrophy", "muscle", "mass", "bulk"]):
        goal_category = "hypertrophy"
        cal_target = tdee + 300  # Lean surplus
        protein_per_kg = 2.2     # 2.0 - 2.4 g/kg
        fat_ratio = 0.25
    elif any(g in primary_goal for g in ["fat_loss", "cutting", "cut", "weight_loss"]):
        goal_category = "cutting"
        cal_target = max(tdee - 450, 1500)  # Deficit with safety floor
        protein_per_kg = 2.4               # Higher protein to preserve LBM
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
            # Training day adjustment: replace 60-80% of workout calories predominantly with carbohydrates
            if cal_burned > 0:
                training_bonus_cal = round(cal_burned * 0.7)
            elif dist_km > 0:
                training_bonus_cal = round(dist_km * 60 * 0.7)
            else:
                training_bonus_cal = 250

            # 75% of training bonus to carbs (4 kcal/g), 25% to healthy fat (9 kcal/g)
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
    
    # Calculate Macro Grams
    protein_g = round(weight_kg * protein_per_kg)
    protein_cals = protein_g * 4

    fat_cals = (cal_target * fat_ratio) + (bonus_fat * 9)
    fat_g = round(fat_cals / 9.0)

    # Remaining calories to Carbs
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
    Tolerances:
    - Calories: +/- 10%
    - Protein: +/- 15%
    - Carbs: +/- 20%
    - Fat: +/- 20%
    """
    act_cal = float(actual.get("calories") or 0)
    act_p = float(actual.get("protein") or actual.get("protein_g") or 0)
    act_c = float(actual.get("carbs") or actual.get("carbs_g") or 0)
    act_f = float(actual.get("fat") or actual.get("fat_g") or 0)

    tgt_cal = float(targets.get("calories") or 2500)
    tgt_p = float(targets.get("protein_g") or targets.get("protein") or 160)
    tgt_c = float(targets.get("carbs_g") or targets.get("carbs") or 250)
    tgt_f = float(targets.get("fat_g") or targets.get("fat") or 70)

    # Score components (each 0.0 to 1.0)
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

    # Weighted adherence: 35% Calories, 35% Protein, 15% Carbs, 15% Fat
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
    user_id: str,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Assembles multi-day nutritional logs, daily aggregates, goal-adaptive targets,
    and rolling compliance statistics.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id

    # 1. Fetch User Profile
    profile = {}
    try:
        u_res = supabase.table("users").select("*").eq("id", uid).execute()
        if u_res.data:
            profile = u_res.data[0]
    except Exception as e:
        logger.warning(f"Error fetching user profile for nutrition summary: {e}")

    # 2. Fetch Meal Logs (querying both meals & nutrition_logs tables for maximum resilience)
    raw_logs = []
    try:
        # Try canonical meals table first
        m_res = supabase.table("meals").select("*").eq("user_id", uid).execute()
        if m_res.data:
            for m in m_res.data:
                logged_date = m.get("date") or (m.get("logged_at") or "")[:10] or ""
                if start_date <= logged_date <= end_date:
                    raw_logs.append({
                        "id": m.get("id"),
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

    if not raw_logs:
        try:
            nl_res = supabase.table("nutrition_logs").select("*").eq("user_id", uid).execute()
            if nl_res.data:
                for nl in nl_res.data:
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
        act_res = supabase.table("garmin_activities").select("*").eq("user_id", uid).execute()
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

    # Generate dates in range
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

            # Adherence for logged days
            if d_str in daily_summaries:
                score, breakdown = calculate_adherence_score(daily_summaries[d_str], target)
                daily_adherence[d_str] = {"score": score, **breakdown}

            curr_dt += timedelta(days=1)
    except Exception as e:
        logger.warning(f"Date range generation error: {e}")

    # Period averages
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
