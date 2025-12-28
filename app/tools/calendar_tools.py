from datetime import datetime, timezone
from app.supabase_client import supabase
import json
import logging

logger = logging.getLogger(__name__)

def create_event(user_id, date, title, event_type, description=""):
    """
    Creates a new training event in the calendar.
    
    Args:
        user_id (int): The ID of the user.
        date (str): The date of the event in YYYY-MM-DD format.
        title (str): The title of the event (e.g., "5k Run").
        event_type (str): The type of event ('run', 'strength', 'rest', 'race', 'other').
        description (str): Optional description of the event.
        
    Returns:
        str: JSON string with the result or error.
    """
    try:
        event_doc = {
            "user_id": int(user_id),
            "date": date,
            "title": title,
            "description": description,
            "event_type": event_type,
            "status": "planned",
            "created_by": "coach",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        response = supabase.table("training_events").insert(event_doc).execute()
        if response.data:
            return json.dumps({"status": "success", "message": f"Event '{title}' created for {date}.", "event": response.data[0]})
        else:
            return json.dumps({"status": "error", "message": "Failed to create event."})
    except Exception as e:
        logger.error(f"Error in create_event: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def get_events(user_id, start_date=None, end_date=None):
    """
    Retrieves training events for a user, optionally within a date range.
    
    Args:
        user_id (int): The ID of the user.
        start_date (str): Optional start date (YYYY-MM-DD).
        end_date (str): Optional end date (YYYY-MM-DD).
        
    Returns:
        str: JSON string with the list of events.
    """
    try:
        query = supabase.table("training_events").select("*").eq("user_id", user_id)
        
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
            
        query = query.order("date")
        response = query.execute()
        
        events = response.data if response.data else []
        # Summarize events for LLM context to save tokens
        summary = [f"{e['date']}: {e['title']} ({e['event_type']})" for e in events]
        return json.dumps({"status": "success", "events": summary, "count": len(events)})
    except Exception as e:
        logger.error(f"Error in get_events: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def update_event(user_id, event_id, updates):
    """
    Updates an existing training event.
    
    Args:
        user_id (int): The ID of the user.
        event_id (int): The ID of the event to update.
        updates (dict): Dictionary of fields to update (date, title, description, event_type, status).
        
    Returns:
        str: JSON string with the result.
    """
    try:
        # Verify ownership
        check = supabase.table("training_events").select("id").eq("id", event_id).eq("user_id", user_id).execute()
        if not check.data:
            return json.dumps({"status": "error", "message": "Event not found."})
            
        allowed = ["date", "title", "description", "event_type", "status"]
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        
        if not clean_updates:
            return json.dumps({"status": "error", "message": "No valid updates provided."})
            
        response = supabase.table("training_events").update(clean_updates).eq("id", event_id).execute()
        if response.data:
            return json.dumps({"status": "success", "message": "Event updated.", "event": response.data[0]})
        else:
            return json.dumps({"status": "error", "message": "Failed to update event."})
    except Exception as e:
        logger.error(f"Error in update_event: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def delete_event(user_id, event_id):
    """
    Deletes a training event.
    
    Args:
        user_id (int): The ID of the user.
        event_id (int): The ID of the event to delete.
        
    Returns:
        str: JSON string with the result.
    """
    try:
        # Verify ownership
        check = supabase.table("training_events").select("id").eq("id", event_id).eq("user_id", user_id).execute()
        if not check.data:
            return json.dumps({"status": "error", "message": "Event not found."})
            
        supabase.table("training_events").delete().eq("id", event_id).execute()
        return json.dumps({"status": "success", "message": "Event deleted."})
    except Exception as e:
        logger.error(f"Error in delete_event: {e}")
        return json.dumps({"status": "error", "message": str(e)})
