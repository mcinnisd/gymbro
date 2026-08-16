# app/onboarding/service.py
"""
Onboarding State Machine & Lifecycle Coordination Service.

Governs the 5-step interactive onboarding flow:
1. Wearable Connection & Hardware Linking
2. Smart Profile & Baseline Biometrics Confirmation
3. Ranked Multi-Goal Set & Schedule Availability
4. Data Reality Check & Horizon Selection
5. Interactive Plan Preview & 1-Tap Calendar Commitment
"""

import logging
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from app.supabase_client import supabase
from app.onboarding.prepopulate_service import TelemetryPrepopulateService
from app.health_hub.ingestion_service import record_daily_biometrics

logger = logging.getLogger(__name__)


def compute_reality_check(
    primary_goal: str,
    acute_weekly_volume_km: float,
    days_count: int,
    secondary_goals: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compares the athlete's composite Goal Set against historical 14-day acute workload.
    """
    goal = (primary_goal or "").lower()
    vol = float(acute_weekly_volume_km or 0.0)
    secondaries = [str(g).lower() for g in (secondary_goals or [])]

    if "marathon" in goal or "endurance" in goal:
        target_weekly_km = max(25.0, days_count * 8.0)
        if vol == 0:
            status = "ramp_needed"
            feedback = "No recent running volume detected. We will start with a safe 4-week aerobic base building cycle before ramping high mileage."
            recommendation = "Begin with 3–4 runs/week, keeping 80% of volume at conversational Zone 2 effort."
        elif vol < 20:
            status = "caution"
            feedback = f"Your current rolling average is {vol:.1f} km/week. We will progressively scale up volume by 10% weekly to prevent overuse injury."
            recommendation = "Progressive overload with a dedicated deload week on Week 4."
        else:
            status = "aligned"
            feedback = f"Strong baseline detected ({vol:.1f} km/week). Your engine is ready for structured speed intervals and progressive long runs."
            recommendation = "Target race pace workouts and weekend progressive long runs."
    elif "muscle" in goal or "strength" in goal or "hypertrophy" in goal:
        target_weekly_km = max(0.0, days_count * 2.0)
        status = "aligned"
        feedback = "Strength focus selected. Calendar will prioritize progressive lifting splits (Push/Pull/Legs or Upper/Lower) with adequate neuromuscular recovery."
        recommendation = "Maintain 48h recovery between working the same major muscle groups."
    elif "fat_loss" in goal or "recomp" in goal:
        target_weekly_km = max(10.0, days_count * 3.0)
        status = "aligned"
        feedback = "Recomposition focus selected. Program balances daily energy expenditure with lean muscle retention."
        recommendation = "Daily movement baseline + 3 strength sessions + Zone 2 cardio."
    elif "hybrid" in goal:
        target_weekly_km = max(15.0, days_count * 5.0)
        status = "aligned" if vol >= 10 else "ramp_needed"
        feedback = "Hybrid athletic balance selected. Workouts will alternate strength training blocks and Zone 2 running sessions."
        recommendation = "3 lifting sessions + 2 aerobic runs per week."
    else:
        target_weekly_km = max(15.0, days_count * 4.0)
        status = "aligned"
        feedback = "Balanced athletic routine tailored to your weekly availability."
        recommendation = "Consistent schedule with planned recovery days."

    # Secondary goal adjustments
    if any("strength" in s or "muscle" in s for s in secondaries) and "marathon" in goal:
        feedback += " Secondary strength goals included: 2 cross-training strength sessions integrated without conflicting with key running workouts."

    return {
        "status": status,
        "historical_weekly_volume_km": vol,
        "target_weekly_volume_km": round(target_weekly_km, 1),
        "feedback": feedback,
        "recommendation": recommendation
    }


def get_onboarding_state(user_id: Any) -> Dict[str, Any]:
    """
    Returns the comprehensive onboarding state snapshot for the athlete.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id

    # Fallback state if database is unpopulated
    default_state = {
        "user_id": uid,
        "step": 1,
        "coach_status": "not_started",
        "is_completed": False,
        "athlete_profile": {
            "age": None,
            "weight": None,
            "height": None,
            "biological_sex": None,
            "sport_history": None,
            "running_experience": None,
            "past_injuries": None,
            "lifestyle": None,
            "weekly_availability": None,
            "terrain_preference": None,
            "equipment": None
        },
        "prepopulated_biometrics": {},
        "goal_set": {
            "primary_goal": "marathon_endurance",
            "secondary_goals": [],
            "days_available": ["Monday", "Wednesday", "Friday", "Saturday"],
            "horizon": "4_week_foundation",
            "units": "metric"
        },
        "reality_check": {},
        "proposal": None
    }

    if not supabase:
        return default_state

    try:
        user_res = supabase.table("users").select("*").eq("id", uid).execute()
        if not user_res.data:
            return default_state

        user = user_res.data[0]
        coach_status = user.get("coach_status") or "not_started"
        step = user.get("interview_step") or 1
        is_completed = (coach_status == "active")

        # 1. Profile Extraction
        goals = user.get("goals") or {}
        athlete_profile = {
            "age": user.get("age") or goals.get("age"),
            "weight": float(user.get("weight")) if user.get("weight") else (float(goals.get("weight")) if goals.get("weight") else None),
            "height": float(user.get("height")) if user.get("height") else (float(goals.get("height")) if goals.get("height") else None),
            "biological_sex": user.get("biological_sex") or goals.get("biological_sex"),
            "sport_history": user.get("sport_history") or goals.get("sport_history"),
            "running_experience": user.get("running_experience") or goals.get("running_experience"),
            "past_injuries": user.get("past_injuries") or goals.get("past_injuries"),
            "lifestyle": user.get("lifestyle") or goals.get("lifestyle"),
            "weekly_availability": user.get("weekly_availability") or goals.get("weekly_availability"),
            "terrain_preference": user.get("terrain_preference") or goals.get("terrain_preference"),
            "equipment": user.get("equipment") or goals.get("equipment")
        }

        # 2. Prepopulated biometrics from service
        prepop = TelemetryPrepopulateService.get_prepopulation_data(uid)

        # 3. Goal set extraction
        goal_set = {
            "primary_goal": goals.get("primary_goal") or goals.get("primary") or "marathon_endurance",
            "secondary_goals": goals.get("secondary_goals") or [],
            "days_available": goals.get("days_available") or ["Monday", "Wednesday", "Friday", "Saturday"],
            "target_date": goals.get("target_date") or goals.get("next_race_date"),
            "target_race": goals.get("target_race") or goals.get("current_goal"),
            "horizon": goals.get("horizon") or "4_week_foundation",
            "units": goals.get("units") or "metric",
            "llm_model": goals.get("llm_model") or "gemini-3.1-flash-lite"
        }

        # 4. Reality Check Calculation
        days_count = len(goal_set["days_available"]) if isinstance(goal_set["days_available"], list) else 4
        vol_km = prepop.get("acute_weekly_volume_km") or 0.0
        reality_check = compute_reality_check(
            goal_set["primary_goal"],
            vol_km,
            days_count,
            secondary_goals=goal_set["secondary_goals"]
        )

        # 5. Proposal
        proposal = user.get("training_plan") or goals.get("draft_proposal")

        return {
            "user_id": uid,
            "step": step,
            "coach_status": coach_status,
            "is_completed": is_completed,
            "athlete_profile": athlete_profile,
            "prepopulated_biometrics": prepop,
            "goal_set": goal_set,
            "reality_check": reality_check,
            "proposal": proposal
        }

    except Exception as e:
        logger.error(f"Error fetching onboarding state for user {uid}: {e}")
        return default_state


def save_onboarding_step(
    user_id: Any,
    step: int,
    data: Optional[Dict[str, Any]] = None,
    next_step: Optional[int] = None
) -> Dict[str, Any]:
    """
    Persists data submitted for a specific onboarding step and increments interview_step.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id
    payload = data or {}

    user_res = supabase.table("users").select("*").eq("id", uid).execute()
    if not user_res.data:
        raise ValueError(f"User {uid} not found.")

    user = user_res.data[0]
    current_goals = user.get("goals") or {}
    updates: Dict[str, Any] = {}

    # 1. Update Profile Fields
    if "age" in payload and payload["age"] is not None:
        updates["age"] = int(payload["age"])
    if "weight" in payload and payload["weight"] is not None:
        updates["weight"] = float(payload["weight"])
    if "height" in payload and payload["height"] is not None:
        updates["height"] = float(payload["height"])
    if "biological_sex" in payload and payload["biological_sex"] is not None:
        updates["biological_sex"] = payload["biological_sex"]
        current_goals["biological_sex"] = payload["biological_sex"]
    if "sport_history" in payload and payload["sport_history"] is not None:
        updates["sport_history"] = payload["sport_history"]
    if "running_experience" in payload and payload["running_experience"] is not None:
        updates["running_experience"] = payload["running_experience"]
    if "past_injuries" in payload and payload["past_injuries"] is not None:
        updates["past_injuries"] = payload["past_injuries"]
    if "lifestyle" in payload and payload["lifestyle"] is not None:
        updates["lifestyle"] = payload["lifestyle"]
    if "weekly_availability" in payload and payload["weekly_availability"] is not None:
        updates["weekly_availability"] = payload["weekly_availability"]
        current_goals["weekly_availability"] = payload["weekly_availability"]
    if "terrain_preference" in payload and payload["terrain_preference"] is not None:
        updates["terrain_preference"] = payload["terrain_preference"]
    if "equipment" in payload and payload["equipment"] is not None:
        updates["equipment"] = payload["equipment"]
        current_goals["equipment"] = payload["equipment"]

    # 2. Persist Manual Biometric Overrides / Confirmations
    biometric_fields = ["resting_hr", "hrv", "hrv_ms", "sleep_hours", "steps", "vo2_max"]
    manual_bio = {}
    for bf in biometric_fields:
        if bf in payload and payload[bf] is not None:
            manual_bio[bf] = payload[bf]

    if manual_bio:
        current_goals.setdefault("confirmed_biometrics", {}).update(manual_bio)
        try:
            manual_bio["source"] = "manual"
            record_daily_biometrics(uid, manual_bio)
        except Exception as e:
            logger.warning(f"Error persisting manual biometrics in save_onboarding_step: {e}")

    # 3. Update Goal Set Fields
    if "primary_goal" in payload:
        current_goals["primary_goal"] = payload["primary_goal"]
    if "secondary_goals" in payload:
        current_goals["secondary_goals"] = payload["secondary_goals"]
    if "days_available" in payload:
        current_goals["days_available"] = payload["days_available"]
    if "target_date" in payload:
        current_goals["target_date"] = payload["target_date"]
        current_goals["next_race_date"] = payload["target_date"]
    if "target_race" in payload:
        current_goals["target_race"] = payload["target_race"]
        current_goals["current_goal"] = payload["target_race"]
    if "horizon" in payload:
        current_goals["horizon"] = payload["horizon"]
    if "calibration_confirmed" in payload:
        current_goals["calibration_confirmed"] = payload["calibration_confirmed"]
    if "connected_providers" in payload:
        current_goals["connected_providers"] = payload["connected_providers"]
    if "skipped_hardware" in payload:
        current_goals["skipped_hardware"] = payload["skipped_hardware"]

    # 4. Update Step Advancement
    target_step = next_step if next_step is not None else min(step + 1, 5)
    updates["interview_step"] = target_step

    # 5. Status Transition
    current_status = user.get("coach_status") or "not_started"
    if current_status in ["not_started", "initial"]:
        updates["coach_status"] = "in_onboarding"
        updates["interview_started_at"] = datetime.now(timezone.utc).isoformat()

    updates["goals"] = current_goals

    supabase.table("users").update(updates).eq("id", uid).execute()

    return {
        "success": True,
        "current_step": target_step,
        "coach_status": updates.get("coach_status", current_status),
        "data": updates
    }


def generate_onboarding_proposal(
    user_id: Any,
    horizon: Optional[str] = None,
    custom_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a tailored 4-week Foundation Block or 8-12 week Milestone Block
    adhering to the gymbro.widget/v1 calendar_proposal schema.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id

    user_res = supabase.table("users").select("*").eq("id", uid).execute()
    user = user_res.data[0] if user_res.data else {}
    goals = user.get("goals") or {}

    selected_horizon = horizon or goals.get("horizon") or "4_week_foundation"
    primary_goal = goals.get("primary_goal") or "marathon_endurance"
    secondary_goals = goals.get("secondary_goals") or []
    days_available = goals.get("days_available") or ["Monday", "Wednesday", "Friday", "Saturday"]
    equipment = user.get("equipment") or goals.get("equipment") or "Commercial Gym + GPS Watch"

    prepop = TelemetryPrepopulateService.get_prepopulation_data(uid)
    acute_volume = prepop.get("acute_weekly_volume_km") or 0.0

    # Build Template Weeks based on Horizon & Goal
    is_foundation = (selected_horizon == "4_week_foundation")
    num_weeks = 4 if is_foundation else 8
    target_vol = 32.0 if is_foundation else 48.0

    sessions_preview = []
    weeks_data = []

    # Map available days to structured workouts
    day_workout_templates = {
        "marathon_endurance": [
            {"title": "Zone 2 Aerobic Base Run", "tag": "Endurance", "duration": 45, "distance": 6.5, "description": "Easy conversational pace in Heart Rate Zone 2"},
            {"title": "Threshold / Tempo Intervals", "tag": "Speed", "duration": 40, "distance": 7.0, "description": "10 min warmup + 4x4 min threshold with 2 min jog rest"},
            {"title": "Recovery Strength & Core", "tag": "Mobility", "duration": 35, "description": "Hip stability, single-leg deadlifts, and core stabilization"},
            {"title": "Progressive Weekend Long Run", "tag": "Long Run", "duration": 75, "distance": 12.0, "description": "Steady endurance run building fatigue resistance"}
        ],
        "muscle_strength": [
            {"title": "Upper Body Heavy Compound (Push/Pull)", "tag": "Strength", "duration": 50, "description": "Barbell Bench Press, Pull-ups, Overhead Press, Rows"},
            {"title": "Lower Body Strength (Squat & Hinge)", "tag": "Strength", "duration": 50, "description": "Back Squats, Romanian Deadlifts, Bulgarian Split Squats"},
            {"title": "Upper Hypertrophy & Arms", "tag": "Hypertrophy", "duration": 45, "description": "Incline DB Press, Lateral Raises, Face Pulls, Bicep Curls"},
            {"title": "Functional Core & Conditioning", "tag": "Conditioning", "duration": 35, "description": "Kettlebell swings, sled pushes, farmer carries"}
        ],
        "hybrid_fitness": [
            {"title": "Upper Body Strength + 2k Flush", "tag": "Hybrid", "duration": 50, "distance": 2.0, "description": "Compound upper lifting followed by 2km easy flush run"},
            {"title": "Zone 2 Steady Endurance Run", "tag": "Endurance", "duration": 45, "distance": 7.0, "description": "Pure aerobic base engine building"},
            {"title": "Lower Body Power & Core", "tag": "Strength", "duration": 45, "description": "Squat variations, lunges, and rotational core"},
            {"title": "Hybrid Metcon / Long Run", "tag": "Long Run", "duration": 60, "distance": 9.0, "description": "Long aerobic endurance effort with bodyweight checkpoints"}
        ],
        "fat_loss": [
            {"title": "Full Body Metabolic Resistance Split", "tag": "Strength", "duration": 45, "description": "Circuit compound movements keeping heart rate elevated"},
            {"title": "Zone 2 Incline Walk / Cardio Interval", "tag": "Cardio", "duration": 40, "distance": 4.5, "description": "Steady fat oxidation cardio zone"},
            {"title": "Upper Hypertrophy & Calisthenics", "tag": "Strength", "duration": 40, "description": "Push-ups, dips, rows, core density circuits"},
            {"title": "Aerobic Long Distance / Steps Goal", "tag": "Endurance", "duration": 60, "distance": 8.0, "description": "Long steady outdoor walk/run"}
        ]
    }

    goal_key = primary_goal if primary_goal in day_workout_templates else "marathon_endurance"
    templates = day_workout_templates[goal_key]

    for w in range(1, num_weeks + 1):
        week_days = []
        is_deload = (w == 4 or w == num_weeks)
        multiplier = 0.8 if is_deload else (1.0 + (w - 1) * 0.08)

        for idx, day_name in enumerate(days_available):
            tmpl = templates[idx % len(templates)]
            dist_km = round(tmpl.get("distance", 0.0) * multiplier, 1) if tmpl.get("distance") else None
            dur_min = int(round(tmpl.get("duration", 45) * (0.85 if is_deload else 1.0)))

            sess_item = {
                "day_name": day_name,
                "title": f"Week {w} {tmpl['title']}" if not is_deload else f"Deload: {tmpl['title']}",
                "tag": tmpl["tag"],
                "duration": dur_min,
                "description": tmpl["description"]
            }
            if dist_km:
                sess_item["distance"] = dist_km

            week_days.append({
                "day": day_name,
                "activity": sess_item["title"],
                "details": sess_item["description"],
                "duration_min": dur_min,
                "distance_km": dist_km,
                "tag": tmpl["tag"]
            })

            if w == 1:
                sessions_preview.append(sess_item)

        weeks_data.append({
            "week_number": w,
            "focus": "Deload & Adaptation" if is_deload else f"Progressive Block {w}",
            "days": week_days
        })

    plan_name = f"{'4-Week Foundation' if is_foundation else '8-Week Milestone'} Plan ({goal_key.replace('_', ' ').title()})"

    proposal_json = {
        "plan_name": plan_name,
        "horizon": "meso",
        "horizon_type": selected_horizon,
        "primary_goal": goal_key,
        "secondary_goals": secondary_goals,
        "weeks_count": num_weeks,
        "target_weekly_volume_km": target_vol,
        "weeks": weeks_data,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    # Widget Envelope adhering to gymbro.widget/v1
    widget_envelope = {
        "protocol": "gymbro.widget/v1",
        "widget_id": f"prop_onboard_{uuid.uuid4().hex[:8]}",
        "widget_type": "calendar_proposal",
        "title": plan_name,
        "subtitle": f"Targeting {len(days_available)} sessions/week • Tailored to your baseline",
        "state": "proposed",
        "payload": {
            "horizon": "meso",
            "target_volume_km": target_vol,
            "total_sessions": len(sessions_preview) * num_weeks,
            "sessions": sessions_preview
        },
        "actions": [
            {
                "id": "commit_calendar",
                "label": "Commit to Calendar & Launch",
                "style": "primary",
                "action_type": "api_call",
                "endpoint": "/onboarding/commit",
                "method": "POST",
                "payload": {"proposal": proposal_json}
            }
        ],
        "emitted_at": datetime.now(timezone.utc).isoformat()
    }

    # Save to user draft
    supabase.table("users").update({
        "training_plan": proposal_json,
        "training_plan_generated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", uid).execute()

    reality_check = compute_reality_check(
        primary_goal,
        acute_volume,
        len(days_available),
        secondary_goals=secondary_goals
    )

    return {
        "proposal": proposal_json,
        "widget": widget_envelope,
        "reality_check": reality_check
    }


def commit_onboarding(user_id: Any, proposal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validates the proposal, bulk-inserts sessions into training_events,
    sets users.coach_status = 'active', and produces the Day 1 Welcome Briefing.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id

    # 1. Fetch or fallback proposal
    plan = proposal
    if not plan:
        user_res = supabase.table("users").select("training_plan").eq("id", uid).execute()
        if user_res.data:
            plan = user_res.data[0].get("training_plan")

    if not plan:
        generated = generate_onboarding_proposal(uid)
        plan = generated["proposal"]

    weeks_list = plan.get("weeks") or []
    if not weeks_list:
        raise ValueError("Proposal does not contain valid structured weeks to commit.")

    # 2. Compute calendar dates starting from current Monday (or upcoming Monday if past)
    start_date = datetime.now(timezone.utc).date()
    days_ahead = (7 - start_date.weekday()) % 7
    first_monday = start_date + timedelta(days=days_ahead) if start_date.weekday() != 0 else start_date

    day_map = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }

    event_list = []
    for week in weeks_list:
        week_num = week.get("week_number", 1)
        for day_data in week.get("days", []):
            day_name = day_data.get("day")
            activity = day_data.get("activity")
            details = day_data.get("details", "")

            if not day_name or not activity:
                continue

            day_offset = day_map.get(day_name, 0)
            event_date = first_monday + timedelta(weeks=week_num - 1, days=day_offset)

            # Map activity type
            act_lower = activity.lower()
            if "rest" in act_lower:
                ev_type = "rest"
            elif "strength" in act_lower or "hypertrophy" in act_lower or "gym" in act_lower:
                ev_type = "strength"
            elif "race" in act_lower:
                ev_type = "race"
            elif "cross" in act_lower:
                ev_type = "cross_train"
            else:
                ev_type = "run"

            event_list.append({
                "user_id": uid,
                "date": event_date.isoformat()[:10],
                "title": activity,
                "description": details,
                "event_type": ev_type,
                "status": "planned",
                "created_by": "coach",
                "metrics": {
                    "duration_min": day_data.get("duration_min"),
                    "distance_km": day_data.get("distance_km"),
                    "tag": day_data.get("tag")
                },
                "created_at": datetime.now(timezone.utc).isoformat()
            })

    # Bulk insert in chunks
    if event_list:
        chunk_size = 50
        for i in range(0, len(event_list), chunk_size):
            chunk = event_list[i:i + chunk_size]
            supabase.table("training_events").insert(chunk).execute()

    # 3. Transition user status to 'active'
    now_iso = datetime.now(timezone.utc).isoformat()

    user_data_res = supabase.table("users").select("goals").eq("id", uid).execute()
    existing_goals = {}
    if user_data_res.data:
        existing_goals = user_data_res.data[0].get("goals") or {}

    existing_goals["onboarding_completed"] = True
    existing_goals["onboarding_completed_at"] = now_iso

    supabase.table("users").update({
        "coach_status": "active",
        "interview_step": 5,
        "interview_completed_at": now_iso,
        "training_plan": plan,
        "training_plan_generated_at": now_iso,
        "goals": existing_goals
    }).eq("id", uid).execute()

    # 4. Generate Day 1 Welcome Briefing
    first_session = event_list[0] if event_list else {
        "title": "Welcome & Baseline Calibration",
        "description": "Log your first morning recovery metrics or an easy introductory workout."
    }

    welcome_briefing = (
        f"🔥 Welcome to GYMBro! Your {plan.get('plan_name', 'Meso Horizon')} has been successfully "
        f"committed to your training calendar ({len(event_list)} sessions scheduled). "
        f"Day 1 Action: You are scheduled for '{first_session['title']}' ({first_session['description']}). "
        f"Let's get after it!"
    )

    return {
        "success": True,
        "coach_status": "active",
        "events_created": len(event_list),
        "welcome_briefing": welcome_briefing,
        "first_session": first_session,
        "plan_name": plan.get("plan_name")
    }
