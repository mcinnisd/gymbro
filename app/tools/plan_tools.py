"""
Training Plan Tools.

Allows the Agent to generate and populate full training plans.
"""
import logging
from app.supabase_client import supabase
from app.coach.plan_service import generate_baseline_plan as service_generate_plan
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_training_plan(user_id: str, goal: str, weeks: int = 4, start_date: str = None) -> dict:
    """
    Generates a multi-week training plan and populates the calendar.
    
    Args:
        user_id: The user's ID.
        goal: The goal description (e.g., "Sub-4 hour marathon").
        weeks: Duration of the plan.
        start_date: YYYY-MM-DD start date.
    
    Returns:
        dict: Summary of the created plan.
    """
    try:
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")

        # Reuse existing service logic
        # Note: service_generate_plan typically takes (user_id, user_context_str)
        # We might need to fetch context here or pass the goal as context.
        
        # For this tool wrapper, we'll synthesize a context string from the arguments
        plan_context = f"Goal: {goal}\nDuration: {weeks} weeks\nStart Date: {start_date}"
        
        # Call the actual service (which interacts with LLM to build the plan JSON)
        # and then populates the DB.
        result = service_generate_plan(user_id, plan_context)
        
        return result 
        
    except Exception as e:
        logger.error(f"Error generating plan: {e}")
        return {"status": "error", "message": str(e)}
