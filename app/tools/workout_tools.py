# app/tools/workout_tools.py

import logging
from datetime import datetime, timezone
import uuid
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def reschedule_workout(user_id: str, from_date: str, to_date: str) -> dict:
    """
    Reschedules a training event from one date to another.
    """
    try:
        # Find event on from_date
        res = supabase.table("training_events")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("date", from_date)\
            .execute()
            
        events = res.data or []
        if not events:
            return {"status": "error", "message": f"No training event found on {from_date}."}
            
        event_id = events[0]["id"]
        title = events[0]["title"]
        
        # Update date
        update_res = supabase.table("training_events")\
            .update({"date": to_date})\
            .eq("id", event_id)\
            .execute()
            
        if update_res.data:
            return {
                "status": "success",
                "message": f"Successfully rescheduled '{title}' from {from_date} to {to_date}."
            }
        return {"status": "error", "message": "Failed to update event date in database."}
    except Exception as e:
        logger.error(f"Error rescheduling workout: {e}")
        return {"status": "error", "message": str(e)}

def log_manual_workout(user_id: str, activity_type: str, distance_km: float, duration_min: float, feedback: str = None) -> dict:
    """
    Logs a completed manual workout and saves the user's qualitative feedback.
    """
    try:
        # 1. Update calendar training event on today if one was planned
        today_str = datetime.now(timezone.utc).date().isoformat()
        planned_res = supabase.table("training_events")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("date", today_str)\
            .eq("status", "planned")\
            .execute()
            
        if planned_res.data:
            event_id = planned_res.data[0]["id"]
            desc = planned_res.data[0].get("description") or ""
            if feedback:
                desc = f"{desc}\nFeedback: {feedback}"
            supabase.table("training_events").update({
                "status": "completed",
                "description": desc
            }).eq("id", event_id).execute()
            
        # 2. Insert into garmin_activities (or raw logs) as a manual activity
        activity_id = f"manual_{uuid.uuid4().hex[:8]}"
        act_doc = {
            "user_id": int(user_id),
            "activity_id": activity_id,
            "activity_name": f"Manual {activity_type.capitalize()}",
            "start_time_local": datetime.now().isoformat(),
            "distance": float(distance_km) * 1000.0, # store in meters
            "duration": float(duration_min) * 60.0,   # store in seconds
            "activity_type": activity_type,
            "raw_data": {"manual": True, "feedback": feedback},
            "synced_at": datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table("garmin_activities").insert(act_doc).execute()
        
        # 3. Store feedback in Intelligence memory
        if feedback:
            from app.context.intelligence_service import IntelligenceService
            IntelligenceService.add_intelligence(
                user_id=user_id,
                category="interaction",
                content=f"User feedback on manual {activity_type} ({distance_km}km): {feedback}",
                source="workout_logging"
            )
            
        return {
            "status": "success",
            "message": f"Successfully logged manual {activity_type}: {distance_km}km in {duration_min} mins."
        }
    except Exception as e:
        logger.error(f"Error logging manual workout: {e}")
        return {"status": "error", "message": str(e)}
