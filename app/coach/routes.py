# app/coach/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app.supabase_client import supabase
from app.utils.llm_utils import generate_chat_response
from app.utils.prompts import COACH_SYSTEM_PROMPT_TEMPLATE, COACH_INTERVIEW_QUESTIONS_PROMPT, COACH_GENERATE_PLAN_PROMPT
import logging
import json

coach_bp = Blueprint('coach', __name__)
logger = logging.getLogger(__name__)

@coach_bp.route("/start_interview", methods=["POST"])
@jwt_required()
def start_interview():
    """
    Starts the coach interview process.
    """
    try:
        user_identity = get_jwt_identity()
        user_id = user_identity 
        
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found."}), 404
        user = response.data[0]

        # --- FETCH GARMIN DATA FOR CONTEXT ---
        garmin_context = ""
        try:
            # 1. Recent Activities (Last 30 days)
            # Note: Supabase query syntax might vary slightly depending on client version, 
            # but .order().limit() is standard.
            acts_res = supabase.table("garmin_activities").select("*").eq("user_id", user_id).order("start_time_local", desc=True).limit(10).execute()
            activities = acts_res.data if acts_res.data else []
            
            if activities:
                garmin_context += "\n\n[DETECTED GARMIN DATA]\n"
                garmin_context += f"Recent Activities ({len(activities)} found):\n"
                for act in activities:
                    date_str = act.get("start_time_local", "")[:10]
                    type_str = act.get("activity_type", "Unknown")
                    dist = f"{act.get('distance', 0) / 1000:.2f}km" if act.get("distance") else "N/A"
                    garmin_context += f"- {date_str}: {type_str}, {dist}\n"
            
            # 2. Daily Metrics (Resting HR, Sleep) - Last 7 days
            daily_res = supabase.table("garmin_daily").select("*").eq("user_id", user_id).order("date", desc=True).limit(7).execute()
            dailies = daily_res.data if daily_res.data else []
            
            if dailies:
                avg_rhr = 0
                count = 0
                for d in dailies:
                    # resting_hr might be a JSON object or int depending on raw data
                    # In sync.py we stored `rhr_data` which is usually an int or dict
                    rhr = d.get("resting_hr")
                    if isinstance(rhr, int):
                        avg_rhr += rhr
                        count += 1
                    elif isinstance(rhr, dict) and "restingHeartRate" in rhr:
                        avg_rhr += rhr["restingHeartRate"]
                        count += 1
                
                if count > 0:
                    garmin_context += f"Average Resting HR (last 7 days): {avg_rhr // count} bpm\n"

        except Exception as e:
            logger.warning(f"Failed to fetch Garmin context: {e}")
            garmin_context = "\n(No Garmin data available or error fetching it)"

        # 1. Generate Interview Questions
        
        # Construct the "Dear Coach" prompt
        dear_coach_prompt = f"""Dear Coach,
I want you to act as my expert running coach and nutritionist.
Your mission is to get me in the best shape possible to achieve my next goal: {user.get("goals", {}).get("current_goal", "[Goal Not Specified]")}.

Before we start building my training and nutrition plans, I want you to fully understand my background, habits, and context.

Base info:
- Age: {user.get("age", "Not specified")}
- Weight: {user.get("weight", "Not specified")}
- Height: {user.get("height", "Not specified")}
- Sport history: {user.get("sport_history", "Not specified")}
- Running experience: {user.get("running_experience", "Not specified")}
- Past injuries: {user.get("past_injuries", "None")}
- Work & lifestyle: {user.get("lifestyle", "Not specified")}
- Weekly availability for training: {user.get("weekly_availability", "Not specified")}
- Terrain preference: {user.get("terrain_preference", "Not specified")}
- Equipment: {user.get("equipment", "Not specified")}

→ Are you ready to take on the challenge?
"""

        # Append Garmin context if available
        if garmin_context:
            dear_coach_prompt += f"\n\n[Additional Context from Garmin Data]:\n{garmin_context}\n"
            dear_coach_prompt += "\n(Please incorporate this data into your understanding of my current fitness level.)"

        # --- DEBUG LOGGING ---
        logger.info(f"DEBUG: User Profile Data: {user}")
        logger.info(f"DEBUG: Garmin Context: {garmin_context}")
        logger.info(f"DEBUG: Final Prompt: {dear_coach_prompt}")
        # ---------------------

        messages = [{"role": "user", "content": dear_coach_prompt}]
        
        # Call LLM
        # We use mode="coach" which sets the system prompt to "You are an expert running coach."
        # The user message is the "Dear Coach..." letter.
        questions_text = generate_chat_response(messages, mode="coach")
        
        # 2. Create Chat Session
        chat_doc = {
            "user_id": user_id,
            "title": "Coach Interview",
            "messages": [
                {
                    "sender": "bot",
                    "content": questions_text,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "type": "interview" # Mark this chat as special
        }
        
        res = supabase.table("chats").insert(chat_doc).execute()
        if not res.data:
             return jsonify({"error": "Failed to create chat."}), 500
        
        chat_id = res.data[0]["id"]
        
        # 3. Update User Status
        supabase.table("users").update({
            "coach_status": "interview_in_progress", 
            "interview_chat_id": chat_id
        }).eq("id", user_id).execute()
        
        return jsonify({
            "message": "Interview started.",
            "chat_id": chat_id,
            "questions": questions_text
        }), 200

    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        return jsonify({"error": "Failed to start interview."}), 500

@coach_bp.route("/generate_plan", methods=["POST"])
@jwt_required()
def generate_plan():
    """
    Generates a training plan based on the interview.
    """
    try:
        user_id = get_jwt_identity()
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found."}), 404
        user = response.data[0]
            
        chat_id = request.get_json().get("chat_id")
        if not chat_id:
            # Try to get from user record
            chat_id = user.get("interview_chat_id")
            
        if not chat_id:
             return jsonify({"error": "Chat ID required."}), 400

        chat_res = supabase.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id).execute()
        if not chat_res.data:
            return jsonify({"error": "Chat not found."}), 404
        chat = chat_res.data[0]

        # 1. Construct Context
        # Format the chat history into a string for the prompt
        interview_qa = ""
        for msg in chat.get("messages", []):
            sender = "Coach" if msg["sender"] == "bot" else "User"
            interview_qa += f"{sender}: {msg['content']}\n"

        user_profile_str = json.dumps({
            "age": user.get("age"),
            "weight": user.get("weight"),
            "height": user.get("height"),
            "sport_history": user.get("sport_history"),
            "running_experience": user.get("running_experience"),
            "past_injuries": user.get("past_injuries"),
            "lifestyle": user.get("lifestyle"),
            "weekly_availability": user.get("weekly_availability"),
            "terrain_preference": user.get("terrain_preference"),
            "equipment": user.get("equipment"),
            "goals": user.get("goals", {})
        }, indent=2)

        # Fetch recent activity summary
        activity_summary = "No recent activity data available."
        try:
            # Fetch last 10 Garmin activities
            acts_res = supabase.table("garmin_activities").select("*").eq("user_id", user_id).order("start_time_local", desc=True).limit(10).execute()
            activities = acts_res.data if acts_res.data else []
            
            if activities:
                activity_summary = f"Found {len(activities)} recent Garmin activities:\n"
                for act in activities:
                    date_str = act.get("start_time_local", "")[:10]
                    type_str = act.get("activity_type", "Unknown")
                    dist = f"{act.get('distance', 0) / 1000:.2f}km" if act.get("distance") else "N/A"
                    activity_summary += f"- {date_str}: {type_str}, {dist}\n"
        except Exception as e:
            logger.warning(f"Failed to fetch activity data: {e}")

        prompt = COACH_GENERATE_PLAN_PROMPT.format(
            user_profile=user_profile_str,
            activity_summary=activity_summary,
            interview_qa=interview_qa
        )

        # 2. Call LLM
        system_prompt = COACH_SYSTEM_PROMPT_TEMPLATE.format(
            age=user.get("age", "Not specified"),
            weight=user.get("weight", "Not specified"),
            height=user.get("height", "Not specified"),
            sport_history=user.get("sport_history", "Not specified"),
            running_experience=user.get("running_experience", "Not specified"),
            past_injuries=user.get("past_injuries", "None"),
            lifestyle=user.get("lifestyle", "Not specified"),
            weekly_availability=user.get("weekly_availability", "Not specified"),
            terrain_preference=user.get("terrain_preference", "Not specified"),
            equipment=user.get("equipment", "Not specified"),
            current_goal=user.get("goals", {}).get("current_goal", "Not specified")
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        # Fetch user's LLM preference
        llm_provider = user.get("goals", {}).get("llm_model")

        response_text = generate_chat_response(
            messages, 
            mode="coach", 
            system_prompt=system_prompt,
            provider=llm_provider
        )
        # 3. Parse and Store Plan
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = response_text[start:end]
                plan_json = json.loads(json_str)
            else:
                plan_json = {"raw_text": plan_text}
        except Exception as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            plan_json = {"raw_text": plan_text}

        supabase.table("users").update({
            "coach_status": "plan_generated", 
            "training_plan": plan_json,
            "training_plan_generated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()

        return jsonify({
            "message": "Plan generated successfully.",
            "plan": plan_json
        }), 200

    except Exception as e:
        logger.error(f"Error generating plan: {e}")
        return jsonify({"error": "Failed to generate plan."}), 500

@coach_bp.route("/organize_plan", methods=["POST"])
@jwt_required()
def organize_plan():
    """
    Organizes the baseline plan into phases.
    """
    try:
        user_id = get_jwt_identity()
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        if not response.data:
            return jsonify({"error": "User not found."}), 404
        user = response.data[0]

        baseline_plan = user.get("training_plan")
        if not baseline_plan:
            return jsonify({"error": "No baseline plan found. Generate a plan first."}), 400

        race_date = user.get("goals", {}).get("next_race_date", "Not specified")
        
        from app.utils.prompts import COACH_ORGANIZE_PHASES_PROMPT
        
        prompt = COACH_ORGANIZE_PHASES_PROMPT.format(
            race_date=race_date,
            baseline_plan=json.dumps(baseline_plan, indent=2)
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM
        phases_text = generate_chat_response(messages, mode="coach")
        
        # Parse JSON
        try:
            start = phases_text.find('{')
            end = phases_text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = phases_text[start:end]
                phases_json = json.loads(json_str)
            else:
                phases_json = {"raw_text": phases_text}
        except Exception as e:
            logger.warning(f"Failed to parse phases JSON: {e}")
            phases_json = {"raw_text": phases_text}
            
        supabase.table("users").update({
            "coach_status": "plan_phased",
            "training_plan_phased": phases_json,
            "training_plan_phased_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return jsonify({
            "message": "Plan organized into phases successfully.",
            "phased_plan": phases_json
        }), 200
        
    except Exception as e:
        logger.error(f"Error organizing plan: {e}")
        return jsonify({"error": "Failed to organize plan."}), 500
