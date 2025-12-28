from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app.supabase_client import supabase
import logging

calendar_bp = Blueprint('calendar', __name__)
logger = logging.getLogger(__name__)

@calendar_bp.route("/events", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_events():
    user_id = get_jwt_identity()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    try:
        query = supabase.table("training_events").select("*").eq("user_id", user_id)
        
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
            
        # Order by date
        query = query.order("date")
        
        response = query.execute()
        events = response.data if response.data else []
        return jsonify({"events": events}), 200
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return jsonify({"error": "Failed to fetch events."}), 500

@calendar_bp.route("/events", methods=["POST"], strict_slashes=False)
@jwt_required()
def create_event():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ["date", "title", "event_type"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
            
    event_doc = {
        "user_id": int(user_id),
        "date": data["date"],
        "title": data["title"],
        "description": data.get("description", ""),
        "event_type": data["event_type"],
        "status": data.get("status", "planned"),
        "created_by": "user",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        response = supabase.table("training_events").insert(event_doc).execute()
        if response.data:
            return jsonify({"message": "Event created.", "event": response.data[0]}), 201
        else:
            return jsonify({"error": "Failed to create event."}), 500
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return jsonify({"error": str(e)}), 500

@calendar_bp.route("/events/<int:event_id>", methods=["PUT"], strict_slashes=False)
@jwt_required()
def update_event(event_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Allowed updates
    updates = {}
    allowed = ["date", "title", "description", "event_type", "status"]
    for k in allowed:
        if k in data:
            updates[k] = data[k]
            
    if not updates:
        return jsonify({"message": "No updates provided."}), 200
        
    try:
        # Verify ownership
        check = supabase.table("training_events").select("id").eq("id", event_id).eq("user_id", user_id).execute()
        if not check.data:
            return jsonify({"error": "Event not found."}), 404
            
        response = supabase.table("training_events").update(updates).eq("id", event_id).execute()
        if response.data:
            return jsonify({"message": "Event updated.", "event": response.data[0]}), 200
        else:
            return jsonify({"error": "Failed to update event."}), 500
    except Exception as e:
        logger.error(f"Error updating event: {e}")
        return jsonify({"error": str(e)}), 500

@calendar_bp.route("/events/<int:event_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_event(event_id):
    user_id = get_jwt_identity()
    
    try:
        # Verify ownership
        check = supabase.table("training_events").select("id").eq("id", event_id).eq("user_id", user_id).execute()
        if not check.data:
            return jsonify({"error": "Event not found."}), 404
            
        supabase.table("training_events").delete().eq("id", event_id).execute()
        return jsonify({"message": "Event deleted."}), 200
    except Exception as e:
        logger.error(f"Error deleting event: {e}")
        return jsonify({"error": str(e)}), 500
