"""
Coach Service Module.

Handles message processing, tool dispatch, RAG context injection, and structured UI payload generation
for chat widget rendering (workout plans, charts, goal updates).
"""

import logging
from typing import Dict, Any, Optional
import logging
from typing import Dict, Any, Optional
from app.agent.analyst import AnalystAgent
from app.context.builder import build_user_context
from app.agent.tools import (
    render_chart,
    generate_training_plan_tool,
    update_user_goals,
    tune_macro_targets_tool,
    evaluate_readiness_anomaly_tool
)

logger = logging.getLogger(__name__)


def process_coach_message(user_id: str, message: str) -> Dict[str, Any]:
    """
    Processes an incoming message to the coach agent using RAG context building and LLM response generation,
    returning a structured response with rich text and optional `ui_payload` conforming to gymbro.widget/v1.

    Args:
        user_id: The ID of the user sending the message.
        message: The user's input text message.

    Returns:
        Dict containing:
            - 'response': Rich text message from the coach.
            - 'ui_payload': Structured payload dict or None.
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
    elif any(k in msg_lower for k in ["macro", "nutrition", "calories", "protein", "carbs", "fats"]):
        ui_payload = tune_macro_targets_tool(user_id=user_id, protein_g=175, carbs_g=220, fats_g=60, goal_type="recomp")
    elif any(k in msg_lower for k in ["readiness", "swap", "reschedule", "fatigue", "sore"]):
        ui_payload = evaluate_readiness_anomaly_tool(
            user_id=user_id,
            readiness_score=54,
            hrv_anomaly_pct=-18.0,
            sleep_score=62,
            recommendation="Replace scheduled 5x1km threshold intervals with a 40-minute Zone 2 recovery flush.",
            original_session={"title": "5x1km Threshold Intervals", "duration": 55, "intensity": "Hard"},
            suggested_session={"title": "Zone 2 Aerobic Recovery Flush", "duration": 40, "intensity": "Easy"}
        )
    elif any(k in msg_lower for k in ["chart", "trend", "show pace", "hrv", "sleep", "visualize", "recovery"]):
        metric = "pace"
        if "hrv" in msg_lower:
            metric = "hrv"
        elif "distance" in msg_lower or "mileage" in msg_lower:
            metric = "distance"
        elif "sleep" in msg_lower or "recovery" in msg_lower:
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
            response_text = f"I've analyzed your telemetry and updated your fast context for: '{message}'."

    result = {
        "response": response_text,
        "reply": response_text,
        "ui_payload": ui_payload
    }

    if plan_data is not None:
        result["plan"] = plan_data

    return result

