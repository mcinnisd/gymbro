"""
Coach Service Module.

Handles message processing, tool dispatch, and structured UI payload generation
for chat widget rendering (workout plans, charts, goal updates).
"""

import logging
from typing import Dict, Any, Optional
from app.agent.tools import (
    render_chart,
    generate_training_plan_tool,
    update_user_goals
)

logger = logging.getLogger(__name__)


def process_coach_message(user_id: str, message: str) -> Dict[str, Any]:
    """
    Processes an incoming message to the coach agent and dispatches tool calls
    if required, returning a structured response with text and optional `ui_payload`.

    Args:
        user_id: The ID of the user sending the message.
        message: The user's input text message.

    Returns:
        Dict containing:
            - 'response': Text message from the coach.
            - 'ui_payload': Structured payload dict ({ 'type': ..., 'data': ... }) or None.
            - 'plan': (Optional) workout plan data if plan was generated.
    """
    msg_lower = message.lower()
    ui_payload: Optional[Dict[str, Any]] = None
    response_text = ""
    plan_data = None

    # Check for training plan intent
    if any(k in msg_lower for k in ["plan", "marathon", "generate a", "routine"]):
        ui_payload = generate_training_plan_tool(user_id=user_id, goal=message)
        plan_data = ui_payload.get("data")
        response_text = f"I've generated a customized training plan based on your request: '{message}'."

    # Check for chart / visualization intent
    elif any(k in msg_lower for k in ["chart", "trend", "show pace", "hrv", "sleep", "visualize"]):
        metric = "pace"
        if "hrv" in msg_lower:
            metric = "hrv"
        elif "distance" in msg_lower or "mileage" in msg_lower:
            metric = "distance"
        elif "sleep" in msg_lower:
            metric = "sleep_score"
        elif "load" in msg_lower or "training load" in msg_lower:
            metric = "training_load"

        ui_payload = render_chart(user_id=user_id, metric=metric)
        response_text = f"Here is your {metric.replace('_', ' ')} chart overview."

    # Check for goal update intent
    elif any(k in msg_lower for k in ["goal", "target"]):
        ui_payload = update_user_goals(
            user_id=user_id,
            goal_type="marathon_pace",
            target_value="4:30/km",
            description=message
        )
        response_text = "I've updated your fitness goal."

    # Standard chat response fallback
    else:
        response_text = f"Thanks for your message! How else can I assist with your training?"

    result = {
        "response": response_text,
        "ui_payload": ui_payload
    }

    if plan_data is not None:
        result["plan"] = plan_data

    return result
