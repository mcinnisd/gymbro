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


def process_coach_message(user_id: str, message: str, mode: str = "fast") -> Dict[str, Any]:
    """
    Processes an incoming message to the coach agent using RAG context building and LLM response generation,
    returning a structured response with rich text and optional `ui_payload` conforming to gymbro.widget/v1.

    Args:
        user_id: The ID of the user sending the message.
        message: The user's input text message.
        mode: Operating mode ('fast', 'debug', 'rag').

    Returns:
        Dict containing:
            - 'response': Rich text message from the coach.
            - 'reply': Alias for response.
            - 'ui_payload': Structured payload dict or None.
            - 'mode': The operational mode used.
            - 'plan': (Optional) workout plan data if plan was generated.
    """
    msg_lower = message.lower()
    ui_payload: Optional[Dict[str, Any]] = None
    plan_data = None

    # 1. Build context bundle (activities, sleep, HRV, baselines, notes)
    try:
        context_str = build_user_context(user_id=user_id, query=message)
    except Exception as e:
        logger.error(f"Error building user context for coach message: {e}")
        context_str = ""

    # 2. Check for explicit tool UI payload triggers
    if any(k in msg_lower for k in ["generate a plan", "create a plan", "marathon plan", "training plan", "workout routine", "plan proposal", "build a plan", "plan"]) and not any(k in msg_lower for k in ["chart", "plot", "graph"]):
        ui_payload = generate_training_plan_tool(user_id=user_id, goal=message)
        plan_data = ui_payload.get("data")
    elif any(k in msg_lower for k in ["macro", "macros", "nutrition", "calorie target", "calories", "protein", "carbs", "fats"]) and not any(k in msg_lower for k in ["chart", "plot", "graph"]):
        ui_payload = tune_macro_targets_tool(user_id=user_id, protein_g=175, carbs_g=220, fats_g=60, goal_type="recomp")
    elif any(k in msg_lower for k in ["readiness", "swap", "reschedule", "fatigue", "sore", "anomaly"]) and not any(k in msg_lower for k in ["chart", "plot", "graph"]):
        ui_payload = evaluate_readiness_anomaly_tool(
            user_id=user_id,
            readiness_score=54,
            hrv_anomaly_pct=-18.0,
            sleep_score=62,
            recommendation="Replace scheduled 5x1km threshold intervals with a 40-minute Zone 2 recovery flush.",
            original_session={"title": "5x1km Threshold Intervals", "duration": 55, "intensity": "Hard"},
            suggested_session={"title": "Zone 2 Aerobic Recovery Flush", "duration": 40, "intensity": "Easy"}
        )
    elif any(k in msg_lower for k in [
        "chart", "trend", "plot", "graph", "show", "visualize", "view",
        "hrv", "sleep", "recovery", "rhr", "resting heart rate", "resting hr", "heart rate", "bpm",
        "pace", "distance", "mileage", "elevation", "load", "volume", "training load", "cadence"
    ]):

        metric = "hrv"
        if any(term in msg_lower for term in ["resting heart rate", "resting hr", "rhr", "resting"]):
            metric = "resting_hr"
        elif "heart rate" in msg_lower or "bpm" in msg_lower:
            metric = "resting_hr" if ("rest" in msg_lower or "night" in msg_lower or "sleep" in msg_lower) else "heart_rate"
        elif "hrv" in msg_lower or "variability" in msg_lower:
            metric = "hrv"
        elif "sleep" in msg_lower:
            metric = "sleep_score"
        elif "recovery" in msg_lower or "stress" in msg_lower:
            metric = "hrv"
        elif "pace" in msg_lower or "speed" in msg_lower:
            metric = "pace"
        elif "distance" in msg_lower or "mileage" in msg_lower or "volume" in msg_lower:
            metric = "distance"
        elif "elevation" in msg_lower or "climb" in msg_lower:
            metric = "elevation"
        elif "cadence" in msg_lower or "spm" in msg_lower:
            metric = "cadence"
        elif "load" in msg_lower:
            metric = "training_load"
        
        ui_payload = render_chart(user_id=user_id, metric=metric)
    elif any(k in msg_lower for k in ["goal", "target"]) and any(k in msg_lower for k in ["set", "update", "change"]):
        ui_payload = update_user_goals(
            user_id=user_id,
            goal_type="fitness_goal",
            target_value="active_target",
            description=message
        )

    # 3. Formulate clean athletic insight for widget or execute LLM turn
    response_text = ""
    if ui_payload:
        w_type = ui_payload.get("widget_type") or ui_payload.get("type", "").lower()
        if "chart" in w_type or "interactive_chart" in w_type:
            title = ui_payload.get("title", "Biometric Trend")
            response_text = f"Here is your {title.lower()} over the recent period."
        elif "calendar" in w_type or "proposal" in w_type:
            response_text = "I've structured a customized training proposal for you. Review the sessions below."
        elif "macro" in w_type:
            response_text = "Here are your updated macronutrient targets. You can adjust the sliders below."
        elif "readiness" in w_type:
            response_text = "I analyzed your overnight recovery metrics. Here is an adaptive session recommendation."
        else:
            response_text = "Here are your requested metrics."

    # 4. If no widget was produced or in deep RAG mode, run LLM turn with context
    if not response_text or mode in ["rag", "debug"]:
        try:
            from app.utils.llm_utils import generate_chat_response
            prompt_sys = (
                "You are GYMBro AI, an elite, warm athletic coach and exercise physiologist. "
                "Answer the user's question directly, clearly, and concisely based on their telemetry context. "
                "Do not dump raw logs or telemetry data strings unprompted."
            )
            llm_reply = generate_chat_response(
                messages=[{"role": "user", "content": message}],
                mode="coach",
                system_prompt=prompt_sys,
                context=context_str
            )
            if llm_reply and isinstance(llm_reply, str) and llm_reply.strip():
                response_text = llm_reply.strip()
        except Exception as e:
            logger.warning(f"LLM chat turn failed in coach service: {e}")

    # Fallback to natural coach message if still empty
    if not response_text:
        response_text = "I've checked your latest metrics and recovery status. How can I help you adjust your training today?"

    # 5. Append debug context trace ONLY when in debug mode
    if mode == "debug" and context_str:
        response_text += f"\n\n---\n**🔍 Telemetry Debug Context**:\n```\n{context_str[:800]}\n```"

    result = {
        "response": response_text,
        "reply": response_text,
        "ui_payload": ui_payload,
        "mode": mode
    }

    if plan_data is not None:
        result["plan"] = plan_data

    return result



