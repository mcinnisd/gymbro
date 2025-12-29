# app/coach/plan_service.py

import json
import logging
from datetime import datetime, timezone, timedelta
from app.supabase_client import supabase
from app.utils.llm_utils import generate_chat_response
from app.utils.prompts import (
    COACH_SYSTEM_PROMPT_TEMPLATE, 
    COACH_GENERATE_PLAN_PROMPT, 
    COACH_ORGANIZE_PHASES_PROMPT
)
from app.tools.calendar_tools import create_event

logger = logging.getLogger(__name__)

def generate_baseline_plan(user_id: str, context: str = None):
    """
    Generates a 4-week baseline training plan for the user.
    """
    try:
        # Fetch user data
        user_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            return None
        user = user_res.data[0]

        # Fetch interview context
        from app.coach.interview_service import get_interview_context
        interview_qa = get_interview_context(user_id)

        # Fetch recent activities
        activity_summary = "No recent activity data available."
        try:
            acts_res = supabase.table("garmin_activities").select("*").eq("user_id", user_id).order("start_time_local", desc=True).limit(20).execute()
            activities = acts_res.data if acts_res.data else []
            if activities:
                activity_summary = f"Found {len(activities)} recent Garmin activities:\n"
                for act in activities[:10]:
                    date_str = act.get("start_time_local", "")[:10]
                    type_str = act.get("activity_type", "Unknown")
                    dist = f"{act.get('distance', 0) / 1000:.2f}km" if act.get("distance") else "N/A"
                    activity_summary += f"- {date_str}: {type_str}, {dist}\n"
        except Exception as e:
            logger.warning(f"Error fetching activities for plan: {e}")

        # Construct prompts
        user_profile_str = json.dumps({
            "age": user.get("age"),
            "weight": user.get("weight"),
            "height": user.get("height"),
            "running_experience": user.get("running_experience"),
            "past_injuries": user.get("past_injuries"),
            "lifestyle": user.get("lifestyle"),
            "weekly_availability": user.get("weekly_availability"),
            "goals": user.get("goals", {})
        }, indent=2)

        prompt = COACH_GENERATE_PLAN_PROMPT.format(
            user_profile=user_profile_str,
            activity_summary=activity_summary,
            interview_qa=interview_qa
        )
        
        # Inject explicit context (from tool) if provided
        if context:
            prompt += f"\n\nADDITIONAL INSTRUCTIONS/CONTEXT:\n{context}\nPlease prioritize these instructions over the general profile."

        system_prompt = COACH_SYSTEM_PROMPT_TEMPLATE.format(
            age=user.get("age", "?"),
            weight=user.get("weight", "?"),
            height=user.get("height", "?"),
            sport_history=user.get("sport_history", "?"),
            running_experience=user.get("running_experience", "?"),
            past_injuries=user.get("past_injuries", "None"),
            lifestyle=user.get("lifestyle", "?"),
            weekly_availability=user.get("weekly_availability", "?"),
            terrain_preference=user.get("terrain_preference", "?"),
            equipment=user.get("equipment", "?"),
            current_goal=user.get("goals", {}).get("current_goal", "?")
        )

        # Generate using default LLM
        llm_provider = user.get("goals", {}).get("llm_model")
        
        # Use Reasoning Model for Planning if XAI
        model_name = None
        from app.config import Config
        if not llm_provider or llm_provider == "xai":
            model_name = Config.XAI_REASONING_MODEL
            
        response_text = generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            mode="coach",
            system_prompt=system_prompt,
            provider=llm_provider,
            model_name=model_name
        )

        # Parse JSON
        plan_json = _extract_json(response_text)
        
        # Store in DB
        supabase.table("users").update({
            "training_plan": plan_json,
            "training_plan_generated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()

        return plan_json

    except Exception as e:
        logger.error(f"Error generating baseline plan: {e}")
        return None

def organize_phased_plan(user_id: str):
    """
    Organizes the training into 4 phases leading to the race.
    """
    try:
        user_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            return None
        user = user_res.data[0]

        baseline_plan = user.get("training_plan")
        race_date = user.get("goals", {}).get("next_race_date") or user.get("goals", {}).get("current_goal", "Target Date")
        
        prompt = COACH_ORGANIZE_PHASES_PROMPT.format(
            race_date=race_date,
            baseline_plan=json.dumps(baseline_plan, indent=2)
        )

        # Use Reasoning Model for Planning if XAI
        llm_provider = user.get("goals", {}).get("llm_model")
        model_name = None
        from app.config import Config
        if not llm_provider or llm_provider == "xai":
             model_name = Config.XAI_REASONING_MODEL

        response_text = generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            mode="coach",
            provider=llm_provider,
            model_name=model_name
        )

        phases_json = _extract_json(response_text)
        
        supabase.table("users").update({
            "training_plan_phased": phases_json,
            "training_plan_phased_at": datetime.now(timezone.utc).isoformat(),
            "coach_status": "plan_phased"
        }).eq("id", user_id).execute()

        return phases_json
    except Exception as e:
        logger.error(f"Error organizing phased plan: {e}")
        return None

def populate_calendar_from_plan(user_id: str):
    """
    Takes the training plan and populates the training_events table.
    """
    try:
        user_res = supabase.table("users").select("training_plan, training_plan_phased").eq("id", user_id).execute()
        if not user_res.data:
            return {"error": "User not found"}
        
        user = user_res.data[0]
        plan = user.get("training_plan")
        
        if not plan or "weeks" not in plan:
            return {"error": "No structured plan found to populate calendar"}

        # Start from today or next Monday? Let's say next Monday for consistency if it's a "plan"
        # Or just start from today.
        start_date = datetime.now(timezone.utc).date()
        # Find next Monday
        days_ahead = 0 - start_date.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_monday = start_date + timedelta(days=days_ahead)
        
        current_date = next_monday
        events_created = 0
        
        day_map = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, 
            "Friday": 4, "Saturday": 5, "Sunday": 6
        }

        event_list = []
        for week in plan.get("weeks", []):
            week_num = week.get("week_number", 1)
            for day_data in week.get("days", []):
                day_name = day_data.get("day")
                activity = day_data.get("activity")
                details = day_data.get("details", "")
                
                if not day_name or not activity:
                    continue
                
                # Calculate exact date
                day_offset = day_map.get(day_name, 0)
                event_date = next_monday + timedelta(weeks=week_num-1, days=day_offset)
                
                # Map activity type
                event_type = "run"
                if "rest" in activity.lower(): event_type = "rest"
                elif "strength" in activity.lower() or "gym" in activity.lower(): event_type = "strength"
                elif "race" in activity.lower(): event_type = "race"
                
                event_list.append({
                    "user_id": int(user_id),
                    "date": event_date.isoformat()[:10], # Ensure strict date format
                    "title": activity,
                    "description": details,
                    "event_type": event_type,
                    "status": "planned",
                    "created_by": "coach_plan",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

        if event_list:
             # Bulk insert
             chunk_size = 50 # Supabase might have payload limits
             for i in range(0, len(event_list), chunk_size):
                 chunk = event_list[i:i + chunk_size]
                 supabase.table("training_events").insert(chunk).execute()
                 
        return {"success": True, "events_created": len(event_list)}

    except Exception as e:
        logger.error(f"Error populating calendar: {e}")
        return {"error": str(e)}

def _extract_json(text: str) -> dict:
    """Helper to extract JSON from LLM response."""
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(text[start:end])
    except:
        pass
    return {"raw_text": text}
