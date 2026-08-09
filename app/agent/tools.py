"""
Agent Tools & UI Payload Generation Module.

Provides tool wrappers for the AI coach agent that produce structured JSON payloads
(e.g., WORKOUT_PLAN, CHART, GOALS) for rendering rich widgets in the chat UI.
"""

import logging
from typing import Dict, Any, Optional
from app.context.chart_generator import generate_chart_data
from app.tools.goal_tools import update_goal
from app.tools.plan_tools import generate_training_plan as base_generate_plan

logger = logging.getLogger(__name__)


def render_chart(user_id: str, metric: str, period_days: int = 30, scope: str = "trend") -> Dict[str, Any]:
    """
    Generates a chart payload for rendering in the chat UI.
    
    Returns:
        Dict formatted as { "type": "CHART", "data": chart_config }
    """
    try:
        chart_data = generate_chart_data(user_id=user_id, metric=metric, period_days=period_days, scope=scope)
        if not chart_data:
            chart_data = {
                "type": "line",
                "title": f"{metric.replace('_', ' ').title()} Trend",
                "data": {
                    "labels": ["Day 1", "Day 2", "Day 3"],
                    "datasets": [{"label": metric.title(), "data": [0, 0, 0]}]
                }
            }
        return {
            "type": "CHART",
            "data": chart_data
        }
    except Exception as e:
        logger.error(f"Error rendering chart for {metric}: {e}")
        return {
            "type": "CHART",
            "data": {
                "error": str(e),
                "metric": metric
            }
        }


def generate_training_plan_tool(user_id: str, goal: str, weeks: int = 4, start_date: str = None) -> Dict[str, Any]:
    """
    Generates a multi-week training plan and wraps it in a structured WORKOUT_PLAN UI payload.
    
    Returns:
        Dict formatted as { "type": "WORKOUT_PLAN", "data": plan_dict }
    """
    try:
        plan_res = base_generate_plan(user_id=user_id, goal=goal, weeks=weeks, start_date=start_date)
        return {
            "type": "WORKOUT_PLAN",
            "data": plan_res
        }
    except Exception as e:
        logger.error(f"Error generating training plan tool output: {e}")
        return {
            "type": "WORKOUT_PLAN",
            "data": {"status": "error", "message": str(e)}
        }


def update_user_goals(user_id: str, goal_type: str, target_value: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates user goals and returns a structured GOALS UI payload.
    
    Returns:
        Dict formatted as { "type": "GOALS", "data": goal_update_res }
    """
    try:
        res = update_goal(user_id=user_id, goal_type=goal_type, target_value=target_value, description=description)
        return {
            "type": "GOALS",
            "data": {
                "goal_type": goal_type,
                "target_value": target_value,
                "description": description,
                "status": res.get("status", "success"),
                "message": res.get("message", "Goal updated")
            }
        }
    except Exception as e:
        logger.error(f"Error updating user goals tool: {e}")
        return {
            "type": "GOALS",
            "data": {"status": "error", "message": str(e)}
        }
