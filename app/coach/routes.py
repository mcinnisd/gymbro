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
def start_interview_route():
    """
    Starts the coach interview process using InterviewService.
    """
    try:
        user_id = get_jwt_identity()
        from app.coach.interview_service import start_interview
        
        result = start_interview(user_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify({"error": result.get("error", "Failed to start interview")}), 500

    except Exception as e:
        logger.error(f"Error in start_interview_route: {e}")
        return jsonify({"error": str(e)}), 500


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
                    # Make type explicit
                    type_raw = act.get("activity_type", "Unknown").lower()
                    type_str = type_raw.upper()
                    
                    dist_km = (act.get("distance") or 0) / 1000
                    dur_min = (act.get("duration") or 0) / 60
                    dist_fmt = f"{dist_km:.2f}km"
                    
                    # Highlight Runs
                    if "running" in type_raw:
                        activity_summary += f"- [RUN] {date_str}: {type_str}, {dist_fmt} in {dur_min:.1f} min\n"
                    else:
                        activity_summary += f"- [CROSS-TRAIN] {date_str}: {type_str}, {dist_fmt} in {dur_min:.1f} min\n"
        except Exception as e:
            logger.warning(f"Failed to fetch activity data: {e}")

        prompt = COACH_GENERATE_PLAN_PROMPT.format(
            user_profile=user_profile_str,
            activity_summary=activity_summary,
            interview_qa=interview_qa
        )

        # 2. Call Plan Service
        from app.coach.plan_service import generate_baseline_plan
        plan_json = generate_baseline_plan(user_id)

        if plan_json:
            return jsonify({
                "message": "Plan generated successfully.",
                "plan": plan_json
            }), 200
        else:
            return jsonify({"error": "Failed to generate plan."}), 500

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
        
        # Call Plan Service
        from app.coach.plan_service import organize_phased_plan
        phased_plan = organize_phased_plan(user_id)

        if phased_plan:
            return jsonify({
                "message": "Plan organized into phases successfully.",
                "phased_plan": phased_plan
            }), 200
        else:
            return jsonify({"error": "Failed to organize plan."}), 500
        
    except Exception as e:
        logger.error(f"Error organizing plan: {e}")
        return jsonify({"error": "Failed to organize plan."}), 500
