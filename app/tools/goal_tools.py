"""
Goal Management Tools.

Allows the Agent to update user fitness goals (e.g., Marathon Pace).
"""
import logging
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def update_goal(user_id: str, goal_type: str, target_value: str, description: str = None) -> dict:
    """
    Updates a specific fitness goal for the user.
    
    Args:
        user_id: The user's ID.
        goal_type: Type of goal (e.g., 'marathon_pace', 'weekly_distance', 'weight').
        target_value: The numeric or text target (e.g., '6:00 min/km', '50km').
        description: Optional context.
    
    Returns:
        dict: Status and message.
    """
    try:
        # Fetch current goals
        res = supabase.table("users").select("goals").eq("id", user_id).execute()
        current_goals = {}
        if res.data and res.data[0].get("goals"):
             current_goals = res.data[0].get("goals")
        
        # Update specific goal entry
        # We can store this as a structured dict inside the 'goals' JSONB column
        # Or simpler: just a key-value if the schema supports it. 
        # Let's assume 'goals' is a JSONB map.
        
        current_goals[goal_type] = {
            "target": target_value,
            "description": description,
            "updated_at": "now" # In real app, use timestamp
        }
        
        update_res = supabase.table("users").update({"goals": current_goals}).eq("id", user_id).execute()
        
        # Also update Intelligence so RAG picks it up
        from app.context.intelligence_service import IntelligenceService
        IntelligenceService.add_intelligence(
            user_id=user_id,
            category="goal",
            content=f"My target {goal_type.replace('_', ' ')} is {target_value}. {description or ''}",
            source="user_update"
        )
        
        if update_res.data:
            return {"status": "success", "message": f"Updated {goal_type} to {target_value}"}
        else:
            return {"status": "error", "message": "Database update failed."}
            
    except Exception as e:
        logger.error(f"Error updating goal: {e}")
        return {"status": "error", "message": str(e)}
