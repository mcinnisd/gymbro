"""
Coach Service Module.

Handles message processing, tool dispatch, RAG context injection, and structured UI payload generation
for chat widget rendering (workout plans, charts, goal updates).
"""

import logging
from typing import Dict, Any, Optional
from app.agent.analyst import AnalystAgent
from app.context.builder import build_user_context
from app.agent.tools import (
    render_chart,
    generate_training_plan_tool,
    update_user_goals
)

logger = logging.getLogger(__name__)


def process_coach_message(user_id: str, message: str) -> Dict[str, Any]:
    """
    Processes an incoming message to the coach agent using RAG context building and LLM response generation,
    returning a structured response with rich text and optional `ui_payload`.

    Args:
        user_id: The ID of the user sending the message.
        message: The user's input text message.

    Returns:
        Dict containing:
            - 'response': Rich text message from the coach.
            - 'ui_payload': Structured payload dict ({ 'type': ..., 'data': ... }) or None.
            - 'plan': (Optional) workout plan data if plan was generated.
    """
    msg_lower = message.lower()
    ui_payload: Optional[Dict[str, Any]] = None
    plan_data = None

    # 1. Build RAG context bundle (activities, sleep, HRV, baselines, notes)
    try:
        context_str = build_user_context(user_id=user_id, query=message)
    except Exception as e:
        logger.error(f"Error building user context for coach message: {e}")
        context_str = ""

    # 2. Check for explicit tool UI payload triggers
    if any(k in msg_lower for k in ["plan", "marathon", "generate a plan", "training routine"]):
        ui_payload = generate_training_plan_tool(user_id=user_id, goal=message)
        plan_data = ui_payload.get("data")
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
    elif any(k in msg_lower for k in ["goal", "target"]):
        ui_payload = update_user_goals(
            user_id=user_id,
            goal_type="fitness_goal",
            target_value="active_target",
            description=message
        )

    # 3. Execute AnalystAgent LLM turn with context
    response_text = ""
    try:
        agent = AnalystAgent()
        gen = agent.run(user_id=str(user_id), message=message, context=context_str)
        for update in gen:
            if "answer" in update and update["answer"]:
                response_text = update["answer"]
            elif "chart" in update and not ui_payload:
                ui_payload = {"type": "CHART", "data": update["chart"]}
    except Exception as err:
        logger.error(f"AnalystAgent run error in coach service: {err}")

    # Fallback to intelligent context summary if agent text is empty
    if not response_text or response_text.strip() == "Complete":
        if "activities" in context_str.lower():
            response_text = f"Here is a summary of your training activities based on your recorded data:\n\n{context_str}"
        else:
            response_text = f"I've analyzed your request: '{message}'. How else can I assist your athletic training today?"

    result = {
        "response": response_text,
        "ui_payload": ui_payload
    }

    if plan_data is not None:
        result["plan"] = plan_data

    return result
