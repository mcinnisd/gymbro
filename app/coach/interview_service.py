# app/coach/interview_service.py
"""
Interview Service for the 10-step Coach Interview workflow.

Manages interview state, generates contextual prompts, and stores responses.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import json # Added for LLM response parsing
from app.supabase_client import supabase
from app.context.context_builder import store_user_context, get_all_user_context
from app.utils.llm_utils import generate_chat_response # Added for LLM calls
from app.coach.plan_service import generate_baseline_plan, organize_phased_plan # Added for action steps

logger = logging.getLogger(__name__)

STEP_MISSIONS = {
    1: "Goal Definition: Identify the specific Race, Date, and Time Goal.",
    2: "Profile Audit: LIST the user's Age, Weight, Height, and History summary. Ask ONE question: 'Is this accurate?'",
    3: "Data Reality Check: CITE the specific weekly volume (e.g. 50km) and patterns from Garmin. Ask: 'Does this match your real-world training?'",
    4: "Lifestyle Constraints: Ask about their weekly schedule constraints (running days vs gym days).",
    5: "Baseline Plan Preview: Present the strategy (e.g. '4 weeks base building'). Ask for approval to generate.",
    6: "Phasing Overview: Briefly explain the Training Phases. Ask confirmation to proceed.",
    7: "Cross-Training Check: Confirm if they want to keep their current Strength schedule (detected from Garmin).",
    8: "Fueling Quick Check: Ask one key question about their nutrition strategy.",
    9: "Calendar Commit: Ask permission to write this plan to the calendar.",
    10: "Final Polish: Any last requests before we launch?"
}

# ... [Keep lines 34-378 unchanged] ...

def _generate_dynamic_response(user_id: str, step: int, context: str) -> str:
    """Generates a natural coach response for a specific step/instruction."""
    user_res = supabase.table("users").select("*").eq("id", user_id).execute()
    user_data = user_res.data[0] if user_res.data else {}
    garmin_summary = _get_garmin_summary(user_id)
    
    training_plan = user_data.get("training_plan")
    phased_plan = user_data.get("training_plan_phased")
    
    # Selective Context Injection to reduce noise
    visible_context = ""
    
    # Selective Context Injection:
    # STRATEGY: Provide MORE context, but use Prompt Instructions to control focus.
    # Hiding context caused the Coach to "panic" and re-ask for verification.
    
    visible_context = ""
    
    # ALWAYS Inject Profile (It's small and critical)
    profile_str = f"User Profile & Goal Info (VERIFIED - DO NOT ASK - DO NOT PARROT):\n"
    profile_str += f"- Bio: {user_data.get('age')}y, {user_data.get('weight')}, {user_data.get('height')}\n"
    profile_str += f"- Experience: {user_data.get('running_experience')}\n"
    profile_str += f"- Injuries: {user_data.get('past_injuries')}\n"
    profile_str += f"- Goal Input: {json.dumps(user_data.get('goals', {}))}\n"
    visible_context += profile_str + "\n"

    # ALWAYS Inject Garmin Data (If available) - It informs ability
    visible_context += f"Garmin Intelligent Insights:\n{garmin_summary}\n"

    # Plan Context
    # Plan Context
    if training_plan and step >= 5:
        visible_context += f"\n[CURRENT BASELINE PLAN]: {json.dumps(training_plan)[:500]}..."
    if phased_plan and step >= 6:
        visible_context += f"\n[CURRENT PHASED PLAN]: {json.dumps(phased_plan)[:500]}..."

    prompt = f"""
You are an expert AI Running Coach executing a structured Onboarding Checklist.
Current Step: {step}/10
Mission: {STEP_MISSIONS.get(step)}

CONTEXT (The Truth):
{visible_context}

CRITICAL RULES:
1. **NEVER ASK FOR**: Age, Weight, Height, Running History, recent Weekly Mileage. You HAVE them in the Context.
   - If the mission says "Confirm Profile", you must LIST the data you see and ask "Is this correct?". Do NOT ask the user to provide it.
2. **Be Transactional**: We are verifying data, not chatting. Get a specific "Yes/No" or "Correction" and move on.
3. **Step 3 Specific**: You MUST cite the exact volume numbers from Garmin (e.g. "I see 50km/week"). Ask "Is this typical?".

INSTRUCTIONS:
- Review the Context.
- Execute the specific Mission for Step {step}.
- If the user's last message ("{context}") covers the mission, accept it and suggest moving next.

Keep it short (under 100 words).
"""
    logger.info(f"Step {step} Prompt Context Size: {len(visible_context)} chars")
    
    return generate_chat_response(
        messages=[{"role": "user", "content": prompt}],
        mode="coach",
        provider="xai"
    )


def start_interview(user_id: str) -> Dict[str, Any]:
    """
    Initialize a new interview for a user.
    """
    try:
        # Check for existing
        user_res = supabase.table("users").select("interview_chat_id, interview_step").eq("id", user_id).execute()
        if user_res.data:
            existing_chat_id = user_res.data[0].get("interview_chat_id")
            if existing_chat_id:
                # Verify chat actually exists
                chat_res = supabase.table("chats").select("id").eq("id", existing_chat_id).execute()
                if chat_res.data:
                    return {
                        "success": True,
                        "chat_id": existing_chat_id,
                        "step": user_res.data[0].get("interview_step", 1),
                        "is_existing": True
                    }
                else:
                    # Chat ID exists in user record but chat is gone. Reset.
                    logger.warning(f"User {user_id} has stale interview_chat_id {existing_chat_id}. Resetting.")
                    supa_res = supabase.table("users").update({
                        "interview_chat_id": None, 
                        "coach_status": "not_started",
                        "interview_step": 1
                    }).eq("id", user_id).execute()


        # Initialize
        supabase.table("users").update({
            "interview_step": 1,
            "coach_status": "interview_in_progress",
            "interview_started_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        # Use LLM to generate opening
        user_data = _get_user_data(user_id)
        opening_prompt = _generate_dynamic_response(user_id, 1, "Start the interview by introducing yourself as their AI Coach and asking for their goal.")
        
        chat_doc = {
            "user_id": user_id,
            "title": "AI Coach Interview",
            "type": "interview",
            "messages": [{
                "sender": "bot",
                "content": opening_prompt,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"step": 1}
            }],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table("chats").insert(chat_doc).execute()
        chat_id = result.data[0]["id"]
        
        supabase.table("users").update({"interview_chat_id": chat_id}).eq("id", user_id).execute()
        
        return {"success": True, "chat_id": chat_id, "step": 1, "prompt": opening_prompt}
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        return {"success": False, "error": str(e)}


def get_current_step(user_id: str) -> int:
    """Get user's current interview step (0-10)."""
    try:
        result = supabase.table("users").select("interview_step").eq("id", user_id).execute()
        if result.data:
            return result.data[0].get("interview_step", 0)
        return 0
    except Exception:
        return 0


def process_answer(user_id: str, answer: str, chat_id: str = None) -> Dict[str, Any]:
    """
    Process user's answer and store it.
    """
    try:
        current_step = get_current_step(user_id)
        
        # Store the answer
        store_user_context(
            user_id=user_id,
            context_type="interview_answer",
            content=answer,
            metadata={"step": current_step, "chat_id": chat_id}
        )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error processing answer: {e}")
        return {"success": False, "error": str(e)}


def get_next_question(user_id: str, chat_id: str = None) -> Dict[str, Any]:
    """
    The main engine for the dynamic interview. 
    Analyzes history and decides whether to advance or follow up.
    """
    try:
        user_res = supabase.table("users").select("*").eq("id", user_id).execute()
        user = user_res.data[0]
        current_step = user.get("interview_step", 1)
        
        # Fetch history
        chat_res = supabase.table("chats").select("messages").eq("id", chat_id).execute()
        history = chat_res.data[0].get("messages", []) if chat_res.data else []
        
        last_message = history[-1]["content"] if history else ""
        
        mission = STEP_MISSIONS.get(current_step, "Continue the coaching conversation.")
        
        # 1. Ask the supervisor if current step is done
        progress_analysis = _analyze_progress(user_id, current_step, history)
        
        should_advance = progress_analysis.get("is_complete", False)
        llm_response = progress_analysis.get("response", "")
        
        if should_advance and current_step < 10:
            current_step += 1
            supabase.table("users").update({"interview_step": current_step}).eq("id", user_id).execute()
            
            # Action Steps
            if current_step == 5:
                # Generate Plan
                from app.coach.plan_service import generate_baseline_plan
                generate_baseline_plan(user_id)
            elif current_step == 6:
                # Organize phases
                from app.coach.plan_service import organize_phased_plan
                organize_phased_plan(user_id)
            elif current_step == 9:
                # Populate calendar (if they confirmed, supervisor should have marked done)
                from app.coach.plan_service import populate_calendar_from_plan
                populate_calendar_from_plan(user_id)

            # Re-generate response for the NEW step
            new_mission = STEP_MISSIONS.get(current_step)
            llm_response = _generate_dynamic_response(user_id, current_step, f"The user has completed the previous step. MISSION SUCCESS. Now move to mission: {new_mission}. Acknowledge their previous answer naturally and enthusiastically.")

        return {
            "success": True,
            "question": llm_response,
            "is_complete": (current_step == 10),
            "step": current_step
        }

    except Exception as e:
        logger.error(f"Error in dynamic interview: {e}")
        return {"success": False, "error": str(e)}


def _get_user_data(user_id: str) -> Dict[str, Any]:
    """Fetch user profile data."""
    try:
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else {}
    except Exception:
        return {}


def _get_garmin_summary(user_id: str) -> str:
    """
    Generate a rich summary of user's Garmin data including calculated PBs, volume,
    holistic health (sleep/HR), and strict activity filtering.
    """
    try:
        from datetime import datetime, timedelta, timezone
        
        # 1. Fetch Baselines (Running)
        base_res = supabase.table("user_baselines").select("baselines").eq("user_id", user_id).eq("metric_category", "running").execute()
        baselines = base_res.data[0]["baselines"] if base_res.data else None

        # 2. Daily Stats (RHR, Stress) - Last 14 days
        two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
        
        # NOTE: garmin_daily table currently lacks sleep data column. Skipping sleep for now.
        daily_res = supabase.table("garmin_daily")\
            .select("resting_hr, stress")\
            .eq("user_id", user_id)\
            .gte("date", two_weeks_ago)\
            .execute()
            
        daily_data = daily_res.data if daily_res.data else []
        
        avg_rhr, avg_stress = 0, 0
        avg_sleep_hrs = 0.0 # Default to 0 as we have no column
        
        if daily_data:
            rhrs = []
            stresses = []
            for d in daily_data:
                 # RHR Safe Extraction
                 r_val = d.get('resting_hr')
                 if isinstance(r_val, (int, float)):
                     rhrs.append(r_val)
                 elif isinstance(r_val, dict):
                     # Handle edge case where it might be json
                     v = r_val.get('value') or r_val.get('amount')
                     if isinstance(v, (int, float)): rhrs.append(v)
                     
                 # Stress Safe Extraction
                 s_val = d.get('stress')
                 if isinstance(s_val, (int, float)):
                     stresses.append(s_val)
                 elif isinstance(s_val, dict):
                     v = s_val.get('value')
                     if isinstance(v, (int, float)): stresses.append(v)
            
            if rhrs: avg_rhr = sum(rhrs) / len(rhrs)
            if stresses: avg_stress = sum(stresses) / len(stresses)

        # 2b. Fetch Sleep (from garmin_sleep table)
        sleep_res = supabase.table("garmin_sleep")\
            .select("sleep_data")\
            .eq("user_id", user_id)\
            .gte("date", two_weeks_ago)\
            .execute()
        
        sleeps = sleep_res.data or []
        if sleeps:
            durations = []
            for s in sleeps:
                # Path: sleep_data -> dailySleepDTO -> sleepTimeSeconds
                try:
                    data = s.get('sleep_data', {})
                    dto = data.get('dailySleepDTO', {})
                    secs = dto.get('sleepTimeSeconds')
                    if isinstance(secs, (int, float)) and secs > 0:
                        durations.append(secs)
                except: pass
            
            if durations:
                avg_sleep_hrs = (sum(durations) / len(durations)) / 3600

        # 3. Fetch Recent Activities (RUNNING ONLY) - Last 28 Days for Weekly Stats
        twenty_eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=28)).date().isoformat()
        
        run_types = ['running', 'treadmill_running', 'trail_running', 'street_running', 'track_running']
        
        # Robust Fetch: Get everything, filter in memory to avoid .in_ syntax issues
        try:
            acts_result = supabase.table("garmin_activities")\
                .select("start_time_local, distance, duration, activity_type, average_hr")\
                .eq("user_id", user_id)\
                .gte("start_time_local", twenty_eight_days_ago)\
                .order("start_time_local", desc=True)\
                .execute()
            all_recent = acts_result.data if acts_result.data else []
            
            # Filter in memory
            recent_runs = [a for a in all_recent if a.get('activity_type') in run_types]
        except Exception as e:
            logger.error(f"Error querying recent runs: {e}")
            recent_runs = []

        # 4. Fetch Strength/Other - Last 28 days
        # We can reuse 'all_recent' if we fetched everything!
        # But 'all_recent' only has specific columns. Strength needs duration/start_time which we have.
        # Let's reuse 'all_recent' to save a query.
        
        strength_acts = []
        try:
             strength_acts = [a for a in all_recent if a.get('activity_type') == 'strength_training']
        except: 
             strength_acts = []
             
        strength_count = len(strength_acts)

        summary_parts = []
        
        # Format Baselines (Existing code)
        if baselines:
            pbs = baselines.get("pbs", {})
            vol = baselines.get("volume", {})
            longest = baselines.get("longest_run", {})
            
            pb_str = "All-Time Best Efforts (Calculated):\n"
            if not pbs: pb_str += " None detected."
            for dist, data in pbs.items():
                pb_str += f"- {dist}: {data['formatted_time']} ({data['date']})\n"
            
            if longest:
                pb_str += f"- Longest Run: {longest.get('distance_km')}km ({longest.get('date')})\n"
            summary_parts.append(f"[FITNESS BASELINES]\n{pb_str}")

        # WEEKLY VOLUME BREAKDOWN (Dynamic)
        # Group by Week (Mon-Sun)
        weeks = {}
        for act in recent_runs:
             try:
                 dt = datetime.fromisoformat(act['start_time_local'])
                 # Find start of week (Monday)
                 start_of_week = (dt - timedelta(days=dt.weekday())).date()
                 iso_week = start_of_week.isoformat()
                 
                 if iso_week not in weeks: weeks[iso_week] = 0.0
                 
                 raw_dist = act.get('distance')
                 if isinstance(raw_dist, (int, float)):
                     weeks[iso_week] += (raw_dist / 1000.0)
                 elif raw_dist is None:
                     pass # 0 distance
                 else:
                     # Attempt strict float conversion if string
                     weeks[iso_week] += (float(raw_dist) / 1000.0)
             except Exception as e:
                 logger.warning(f"Skipping activity distance calc: {e}")
                 pass
        
        vol_str = "[RECENT WEEKLY VOLUME]\n"
        sorted_weeks = sorted(weeks.keys(), reverse=True)
        if not sorted_weeks: vol_str += "No running volume in last 4 weeks."
        for w in sorted_weeks:
            vol_str += f"- Week of {w}: {weeks[w]:.1f} km\n"
        summary_parts.append(vol_str)
        
        # Format Holistic
        health_str = f"[HOLISTIC HEALTH (Last 14d Avg)]\n- Resting HR: {int(avg_rhr)} bpm\n- Stress Score: {int(avg_stress)}/100"
        if avg_sleep_hrs > 0:
            health_str += f"\n- Avg Sleep: {avg_sleep_hrs:.1f} hrs"
        summary_parts.append(health_str)
        
        # Format Cross Training (Detailed)
        cross_str = f"[CROSS TRAINING (Last 28d)]\n- Strength Training: {strength_count} sessions total."
        if strength_acts:
            cross_str += "\n  Recent sessions: " + ", ".join([f"{a['start_time_local'][:10]}" for a in strength_acts[:4]])
        summary_parts.append(cross_str)

        # Format Recent Log (Top 5 display)
        if recent_runs:
            recent_log = []
            
            # Pattern Recognition
            morning_count, evening_count = 0, 0
            
            for i, act in enumerate(recent_runs):
                # Time of Day Analysis (Analyze ALL, display only top 5)
                try:
                    dt = datetime.fromisoformat(act.get('start_time_local'))
                    hour = dt.hour
                    if 5 <= hour < 12: morning_count += 1
                    elif 16 <= hour < 22: evening_count += 1
                except: pass

                if i < 5: # Limit display log
                    dist_meters = act.get('distance', 0)
                    duration_secs = act.get('duration', 0)
                    date_str = act.get('start_time_local', '')[:10]
                    type_key = act.get('activity_type', 'run')
                    if dist_meters > 0:
                       pace_min_km = (duration_secs / 60) / (dist_meters / 1000)
                       pace_str = f"{int(pace_min_km)}:{int((pace_min_km % 1) * 60):02d}/km"
                       recent_log.append(f"- {date_str} ({type_key}): {dist_meters/1000:.2f}km @ {pace_str}")
            
            summary_parts.append(f"\n[RECENT RUNNING LOG (Latest 5)]\n" + chr(10).join(recent_log))
            
            # Add Pattern Insight
            pattern_str = "[DETECTED PATTERNS]\n"
            if morning_count > evening_count:
                pattern_str += "- User prefers MORNING runs."
            elif evening_count > morning_count:
                pattern_str += "- User prefers EVENING runs."
            
            if strength_count > 0:
                pattern_str += f"\n- Strength Training is part of routine ({strength_count} sessions/mo)."
            
            summary_parts.append(pattern_str)

        return "\n\n".join(summary_parts)

    except Exception as e:
        import traceback
        logger.error(f"Error analyzing Garmin data: {e}\n{traceback.format_exc()}")
        return "Error analyzing Garmin data."


def _analyze_progress(user_id: str, step: int, history: List[Dict]) -> Dict:
    """Uses a fast LLM to decide if the mission is complete and how to respond."""
    mission = STEP_MISSIONS.get(step)
    
    # Format history for classifier
    history_str = ""
    for m in history[-5:]: # Last 5
        history_str += f"{m['sender']}: {m['content']}\n"
        
    prompt = f"""
You are an interview supervisor for an AI Running Coach.
Current Mission for Step {step}: {mission}

Review the conversation history and decide if the user has provided enough information to fulfill this mission.
Be strict but natural. If they were too brief, you should PRY for more detail.

Conversation:
{history_str}

Return your analysis in JSON format:
{{
  "is_complete": true/false,
  "response": "Your natural follow-up or transition message here",
  "thought": "Briefly explain why"
}}
"""
    try:
        # Use a fast model for analysis
        response_text = generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            mode="developer",
            provider="xai" # Default to fast provider
        )
        
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        return json.loads(response_text[start:end])
    except:
        return {"is_complete": False, "response": "Could you tell me a bit more about that?"}




def get_interview_context(user_id: str) -> str:
    """Get summarized interview context for plan generation."""
    try:
        chat_id_res = supabase.table("users").select("interview_chat_id").eq("id", user_id).execute()
        chat_id = chat_id_res.data[0].get("interview_chat_id")
        if not chat_id: return ""
        
        chat_res = supabase.table("chats").select("messages").eq("id", chat_id).execute()
        messages = chat_res.data[0].get("messages", [])
        
        qa = ""
        for m in messages:
            qa += f"{m['sender']}: {m['content']}\n"
        return qa
    except:
        return ""
