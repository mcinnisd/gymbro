# app/journal/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app.supabase_client import supabase
import logging

journal_bp = Blueprint('journal', __name__)
logger = logging.getLogger(__name__)

@journal_bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@jwt_required()
def handle_journal():
    user_id = get_jwt_identity()
    if request.method == "GET":
        try:
            res = supabase.table("daily_journals").select("*").eq("user_id", user_id).execute()
            entries = res.data if res.data else []
            return jsonify({"journals": entries, "count": len(entries)}), 200
        except Exception as e:
            logger.error(f"Error fetching journals: {e}")
            return jsonify({"error": str(e)}), 500

    data = request.get_json()
    if not data or "answers" not in data:
        return jsonify({"error": "Missing answers in request body."}), 400
        
    date_val = data.get("date", datetime.now(timezone.utc).date().isoformat())
    
    journal_doc = {
        "user_id": int(user_id),
        "date": date_val,
        "answers": data["answers"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # Check if exists
        check = supabase.table("daily_journals").select("id").eq("user_id", user_id).eq("date", date_val).execute()
        if check.data:
            # Update
            res = supabase.table("daily_journals").update({
                "answers": data["answers"]
            }).eq("id", check.data[0]["id"]).execute()
        else:
            # Insert
            res = supabase.table("daily_journals").insert(journal_doc).execute()
            
        if res.data:
            # Index into user_intelligence for RAG retrieval
            try:
                from app.context.intelligence_service import IntelligenceService
                ans = data["answers"]
                j_text = f"Journal ({date_val}): Energy={ans.get('energy_level', 7)}/10, Sore={ans.get('felt_sore', False)}. Notes: {ans.get('journal_text', '')}"
                IntelligenceService.add_intelligence(user_id=user_id, content=j_text, category="fact", metadata={"date": date_val})
            except Exception as ie:
                logger.warning(f"Failed to index journal intelligence: {ie}")
            return jsonify({"message": "Journal saved successfully.", "journal": res.data[0]}), 200
        return jsonify({"error": "Failed to save journal."}), 500
    except Exception as e:
        logger.error(f"Error saving journal: {e}")
        return jsonify({"error": str(e)}), 500

@journal_bp.route("/<date>", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_journal(date):
    user_id = get_jwt_identity()
    try:
        res = supabase.table("daily_journals").select("*").eq("user_id", user_id).eq("date", date).execute()
        if res.data:
            return jsonify({"journal": res.data[0]}), 200
        return jsonify({"message": "No journal entry found for this date."}), 404
    except Exception as e:
        logger.error(f"Error fetching journal: {e}")
        return jsonify({"error": str(e)}), 500
