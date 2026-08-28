# app/nutrition/recipe_service.py

import logging
import uuid
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

# In-memory recipe store for fast unit tests / offline mock environments
_MOCK_RECIPES: Dict[str, Dict[str, Any]] = {}


def create_recipe(
    user_id: Any,
    name: str,
    servings: float = 1.0,
    ingredients: Optional[List[Dict[str, Any]]] = None,
    total_calories: Optional[float] = None,
    total_protein: Optional[float] = None,
    total_carbs: Optional[float] = None,
    total_fat: Optional[float] = None,
    per_serving_calories: Optional[float] = None,
    per_serving_protein: Optional[float] = None,
    per_serving_carbs: Optional[float] = None,
    per_serving_fat: Optional[float] = None,
    image_url: str = "",
    tags: Optional[List[str]] = None,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Creates a batch recipe or meal prep definition, calculating total and per-serving macros.
    """
    clean_uid = str(user_id)
    ingredients_list = ingredients or []
    servings_count = max(float(servings or 1.0), 0.1)

    # 1. Sum up ingredients if totals are not explicitly passed
    calc_total_cals = 0.0
    calc_total_p = 0.0
    calc_total_c = 0.0
    calc_total_f = 0.0

    for ing in ingredients_list:
        calc_total_cals += float(ing.get("calories") or 0.0)
        calc_total_p += float(ing.get("protein") or ing.get("protein_g") or 0.0)
        calc_total_c += float(ing.get("carbs") or ing.get("carbs_g") or 0.0)
        calc_total_f += float(ing.get("fat") or ing.get("fat_g") or 0.0)

    final_tot_cals = float(total_calories) if total_calories is not None else calc_total_cals
    final_tot_p = float(total_protein) if total_protein is not None else calc_total_p
    final_tot_c = float(total_carbs) if total_carbs is not None else calc_total_c
    final_tot_f = float(total_fat) if total_fat is not None else calc_total_f

    # 2. Compute per-serving values
    final_serv_cals = float(per_serving_calories) if per_serving_calories is not None else round(final_tot_cals / servings_count, 1)
    final_serv_p = float(per_serving_protein) if per_serving_protein is not None else round(final_tot_p / servings_count, 1)
    final_serv_c = float(per_serving_carbs) if per_serving_carbs is not None else round(final_tot_c / servings_count, 1)
    final_serv_f = float(per_serving_fat) if per_serving_fat is not None else round(final_tot_f / servings_count, 1)

    recipe_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    recipe_doc = {
        "id": recipe_id,
        "user_id": clean_uid,
        "name": name.strip(),
        "servings": servings_count,
        "ingredients": ingredients_list,
        "total_calories": round(final_tot_cals, 1),
        "total_protein": round(final_tot_p, 1),
        "total_carbs": round(final_tot_c, 1),
        "total_fat": round(final_tot_f, 1),
        "per_serving_calories": round(final_serv_cals, 1),
        "per_serving_protein": round(final_serv_p, 1),
        "per_serving_carbs": round(final_serv_c, 1),
        "per_serving_fat": round(final_serv_f, 1),
        "image_url": image_url,
        "tags": tags or ["meal_prep"],
        "notes": notes,
        "created_at": now_iso,
        "updated_at": now_iso
    }

    # Store in memory for mock / fallback
    _MOCK_RECIPES[recipe_id] = recipe_doc

    # Attempt persist to database
    try:
        res = supabase.table("recipes").insert(recipe_doc).execute()
        if res.data and len(res.data) > 0:
            recipe_doc = res.data[0]
    except Exception as e:
        logger.warning(f"Could not persist recipe to Supabase (using mock store): {e}")

    return {
        "success": True,
        "message": f"Recipe '{name}' saved with {servings_count} servings.",
        "recipe": recipe_doc
    }


def get_user_recipes(user_id: Any, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all saved recipes / meal preps for a given user.
    """
    clean_uid = str(user_id)
    recipes: List[Dict[str, Any]] = []

    # Database query
    try:
        res = supabase.table("recipes").select("*").eq("user_id", clean_uid).execute()
        if res.data:
            recipes = list(res.data)
    except Exception as e:
        logger.warning(f"Supabase recipes query failed, falling back to mock store: {e}")

    # Merge mock store
    for r_id, r_doc in _MOCK_RECIPES.items():
        if str(r_doc.get("user_id")) == clean_uid:
            if not any(str(r.get("id")) == str(r_id) for r in recipes):
                recipes.append(r_doc)

    if search_query:
        q = search_query.lower().strip()
        recipes = [r for r in recipes if q in r.get("name", "").lower() or any(q in ing.get("name", "").lower() for ing in r.get("ingredients", []))]

    return sorted(recipes, key=lambda x: str(x.get("created_at") or ""), reverse=True)


def get_recipe(user_id: Any, recipe_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches a single recipe by ID with user authorization check.
    """
    clean_uid = str(user_id)
    rid_str = str(recipe_id)

    # 1. Check database
    try:
        res = supabase.table("recipes").select("*").eq("id", rid_str).eq("user_id", clean_uid).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        logger.warning(f"Error querying recipe {recipe_id} in DB: {e}")

    # 2. Check mock store
    mock_doc = _MOCK_RECIPES.get(rid_str)
    if mock_doc and str(mock_doc.get("user_id")) == clean_uid:
        return mock_doc

    return None


def log_recipe_portion(
    user_id: Any,
    recipe_id: str,
    servings: float = 1.0,
    date: Optional[str] = None,
    meal_type: str = "meal",
    notes: str = ""
) -> Dict[str, Any]:
    """
    Calculates calories and macronutrients for a chosen number of servings
    of a saved recipe, and writes it directly to the meal log.
    """
    clean_uid = str(user_id)
    recipe = get_recipe(user_id=clean_uid, recipe_id=recipe_id)
    if not recipe:
        return {"success": False, "error": f"Recipe with ID {recipe_id} not found."}

    serving_mult = max(float(servings or 1.0), 0.1)
    cal = round(recipe["per_serving_calories"] * serving_mult, 1)
    p = round(recipe["per_serving_protein"] * serving_mult, 1)
    c = round(recipe["per_serving_carbs"] * serving_mult, 1)
    f = round(recipe["per_serving_fat"] * serving_mult, 1)

    serving_label = f" ({serving_mult} serving{'s' if serving_mult != 1 else ''})"
    logged_name = f"{recipe['name']}{serving_label}"
    log_date = date or datetime.now(timezone.utc).date().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    meal_doc = {
        "id": str(uuid.uuid4()),
        "user_id": clean_uid,
        "date": log_date,
        "logged_at": now_iso,
        "meal_name": logged_name,
        "item_name": logged_name,
        "meal_type": meal_type,
        "calories": cal,
        "protein": p,
        "protein_g": p,
        "carbs": c,
        "carbs_g": c,
        "fat": f,
        "fat_g": f,
        "quality_score": 9,
        "coach_notes": notes or f"Logged from saved recipe '{recipe['name']}'.",
        "created_at": now_iso
    }

    try:
        supabase.table("meals").insert(meal_doc).execute()
    except Exception as e:
        logger.warning(f"Failed inserting recipe meal log to meals table: {e}")

    try:
        supabase.table("nutrition_logs").insert(meal_doc).execute()
    except Exception as e:
        logger.warning(f"Failed inserting recipe meal log to nutrition_logs table: {e}")

    return {
        "success": True,
        "message": f"Successfully logged {serving_mult} serving(s) of '{recipe['name']}' ({cal} kcal).",
        "log": meal_doc
    }


def delete_recipe(user_id: Any, recipe_id: str) -> Dict[str, Any]:
    """
    Deletes a saved recipe.
    """
    clean_uid = str(user_id)
    rid_str = str(recipe_id)

    if rid_str in _MOCK_RECIPES and str(_MOCK_RECIPES[rid_str].get("user_id")) == clean_uid:
        del _MOCK_RECIPES[rid_str]

    try:
        supabase.table("recipes").delete().eq("id", rid_str).eq("user_id", clean_uid).execute()
    except Exception as e:
        logger.warning(f"Error deleting recipe {recipe_id} in DB: {e}")

    return {"success": True, "message": "Recipe deleted successfully.", "id": rid_str}


def match_recipe(
    user_id: Any,
    meal_name: Optional[str] = None,
    ingredients: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Analyzes scanned food name and ingredients to find matching saved recipes.
    Returns matched recipes ranked by confidence.
    """
    recipes = get_user_recipes(user_id=user_id)
    if not recipes or (not meal_name and not ingredients):
        return []

    input_text = ((meal_name or "") + " " + " ".join(ingredients or [])).lower()
    input_tokens = set(re.findall(r'[a-z0-9]+', input_text)) - {"a", "an", "the", "with", "and", "of", "in", "for", "to", "cooked", "fresh"}

    matches = []
    for r in recipes:
        r_name = r.get("name", "").lower()
        r_tokens = set(re.findall(r'[a-z0-9]+', r_name)) - {"a", "an", "the", "with", "and", "of", "in", "for", "to", "prep", "batch", "weekly"}
        
        # Check ingredient overlap
        r_ing_tokens = set()
        for ing in r.get("ingredients", []):
            ing_n = str(ing.get("name", "")).lower()
            r_ing_tokens.update(re.findall(r'[a-z0-9]+', ing_n))
        r_ing_tokens -= {"a", "an", "the", "with", "and", "of", "in", "for", "to"}

        name_overlap = len(input_tokens.intersection(r_tokens))
        ing_overlap = len(input_tokens.intersection(r_ing_tokens))

        score = 0.0
        if name_overlap > 0:
            score += (name_overlap / max(len(r_tokens), 1)) * 0.65
        if ing_overlap > 0:
            score += min((ing_overlap / max(len(r_ing_tokens), 1)) * 0.35, 0.35)

        if score >= 0.35 or any(t in input_text for t in r_tokens if len(t) >= 4):
            confidence = "high" if score >= 0.6 or (len(r_tokens) > 0 and r_tokens.issubset(input_tokens)) else "medium"
            matches.append({
                "id": r["id"],
                "name": r["name"],
                "confidence": confidence,
                "score": round(score, 2),
                "servings": r.get("servings", 1.0),
                "per_serving_calories": r["per_serving_calories"],
                "per_serving_protein": r["per_serving_protein"],
                "per_serving_carbs": r["per_serving_carbs"],
                "per_serving_fat": r["per_serving_fat"],
                "suggested_servings": 1.0,
                "ingredients": r.get("ingredients", [])
            })

    return sorted(matches, key=lambda x: (x["confidence"] == "high", x.get("score", 0)), reverse=True)
