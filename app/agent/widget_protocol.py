"""
GYMBro In-Chat Native Interactive Chart & Action Widget Protocol (gymbro.widget/v1)

Provides structured serialization utilities for Agent Engine tool calls that render
high-performance 60fps native interactive charts (HRV, pace, sleep) and action cards
(Add to Calendar, Adjust Macros, Readiness Reschedule) seamlessly inline in chat.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

GYMBRO_WIDGET_PROTOCOL = "gymbro.widget/v1"

# Widget Archetypes
WIDGET_TYPE_INTERACTIVE_CHART = "interactive_chart"
WIDGET_TYPE_CALENDAR_PROPOSAL = "calendar_proposal"
WIDGET_TYPE_MACRO_SLIDER = "macro_slider"
WIDGET_TYPE_READINESS_ACTION = "readiness_action"
WIDGET_TYPE_SESSION_EDITOR = "session_editor"

# Widget Lifecycle States
WIDGET_STATE_PROPOSED = "proposed"
WIDGET_STATE_ACTIVE = "active"
WIDGET_STATE_CONFIRMED = "confirmed"
WIDGET_STATE_EXECUTED = "executed"
WIDGET_STATE_DISMISSED = "dismissed"
WIDGET_STATE_ERROR = "error"


def create_widget_id(prefix: str = "wid") -> str:
    """Generates a short unique widget identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def build_widget_envelope(
    widget_type: str,
    title: str,
    payload: Dict[str, Any],
    subtitle: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    widget_id: Optional[str] = None,
    state: str = WIDGET_STATE_PROPOSED
) -> Dict[str, Any]:
    """
    Wraps payload data into the standard gymbro.widget/v1 protocol envelope.
    """
    return {
        "protocol": GYMBRO_WIDGET_PROTOCOL,
        "widget_id": widget_id or create_widget_id(widget_type[:4]),
        "widget_type": widget_type,
        "title": title,
        "subtitle": subtitle,
        "state": state,
        "payload": payload,
        "actions": actions or [],
        "emitted_at": datetime.now(timezone.utc).isoformat()
    }


def build_interactive_chart_widget(
    title: str,
    time_range: str,
    metrics: List[Dict[str, Any]],
    points: List[Dict[str, Any]],
    subtitle: Optional[str] = None,
    summary_insight: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    widget_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs an interactive multi-metric scrubbing chart widget payload.
    """
    payload = {
        "chart_id": create_widget_id("cht"),
        "time_range": time_range,
        "metrics": metrics,
        "points": points,
        "summary_insight": summary_insight,
        "interactive_scrubbing": True
    }
    
    default_actions = actions or [
        {
          "id": "discuss_trend",
          "label": "Discuss Trend with Agent",
          "style": "ghost",
          "action_type": "prompt_trigger",
          "prompt_text": f"Can you analyze the key inflection points in this {title} trend?"
        }
    ]

    return build_widget_envelope(
        widget_type=WIDGET_TYPE_INTERACTIVE_CHART,
        title=title,
        subtitle=subtitle,
        payload=payload,
        actions=default_actions,
        widget_id=widget_id
    )


def build_calendar_proposal_widget(
    title: str,
    horizon: str,
    sessions: List[Dict[str, Any]],
    subtitle: Optional[str] = None,
    target_volume_km: Optional[float] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    widget_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a multi-horizon training plan calendar proposal widget payload.
    """
    payload = {
        "horizon": horizon,
        "target_volume_km": target_volume_km,
        "total_sessions": len(sessions),
        "sessions": sessions
    }

    default_actions = actions or [
        {
            "id": "commit_calendar",
            "label": f"Commit {len(sessions)} Sessions to Calendar",
            "style": "primary",
            "action_type": "api_call",
            "endpoint": "/calendar/commit",
            "confirmation_message": f"Successfully committed {len(sessions)} sessions to your training calendar."
        }
    ]

    return build_widget_envelope(
        widget_type=WIDGET_TYPE_CALENDAR_PROPOSAL,
        title=title,
        subtitle=subtitle,
        payload=payload,
        actions=default_actions,
        widget_id=widget_id
    )


def build_macro_slider_widget(
    title: str,
    protein_g: int,
    carbs_g: int,
    fats_g: int,
    goal_type: str = "recomp",
    target_weight_kg: Optional[float] = None,
    presets: Optional[List[Dict[str, Any]]] = None,
    subtitle: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    widget_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a dynamic macronutrient slider tuning widget payload.
    """
    default_presets = presets or [
        {
            "id": "recomp",
            "name": "High Protein Recomp",
            "protein_g": 180,
            "carbs_g": 200,
            "fats_g": 60,
            "ratio_label": "35 / 40 / 25"
        },
        {
            "id": "endurance",
            "name": "Endurance Fueling",
            "protein_g": 140,
            "carbs_g": 320,
            "fats_g": 50,
            "ratio_label": "25 / 55 / 20"
        },
        {
            "id": "keto",
            "name": "Keto / Low Carb",
            "protein_g": 160,
            "carbs_g": 40,
            "fats_g": 120,
            "ratio_label": "35 / 10 / 55"
        }
    ]

    payload = {
        "goal_type": goal_type,
        "target_weight_kg": target_weight_kg,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fats_g": fats_g,
        "presets": default_presets
    }

    total_kcal = (protein_g * 4) + (carbs_g * 4) + (fats_g * 9)

    default_actions = actions or [
        {
            "id": "commit_macros",
            "label": "Save Targets to Profile",
            "style": "primary",
            "action_type": "api_call",
            "endpoint": "/nutrition/targets",
            "confirmation_message": f"Daily target saved: {total_kcal:,} kcal ({protein_g}g P / {carbs_g}g C / {fats_g}g F)."
        }
    ]

    return build_widget_envelope(
        widget_type=WIDGET_TYPE_MACRO_SLIDER,
        title=title,
        subtitle=subtitle or f"Daily Target: {total_kcal:,} kcal",
        payload=payload,
        actions=default_actions,
        widget_id=widget_id
    )


def build_readiness_action_widget(
    title: str,
    readiness_score: int,
    hrv_anomaly_pct: float,
    sleep_score: int,
    recommendation: str,
    original_session: Dict[str, Any],
    suggested_session: Dict[str, Any],
    subtitle: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    widget_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a morning readiness anomaly and schedule rescheduler action widget.
    """
    payload = {
        "readiness_score": readiness_score,
        "hrv_anomaly_pct": hrv_anomaly_pct,
        "sleep_score": sleep_score,
        "recommendation": recommendation,
        "original_session": original_session,
        "suggested_session": suggested_session
    }

    default_actions = actions or [
        {
            "id": "accept_reschedule",
            "label": "Accept Reschedule",
            "style": "primary",
            "action_type": "api_call",
            "endpoint": "/calendar/reschedule",
            "confirmation_message": f"Workout updated to {suggested_session.get('title', 'Recovery Session')}."
        },
        {
            "id": "dismiss_reschedule",
            "label": "Keep Original Workout",
            "style": "ghost",
            "action_type": "client_mutation",
            "confirmation_message": "Original workout kept on calendar."
        }
    ]

    return build_widget_envelope(
        widget_type=WIDGET_TYPE_READINESS_ACTION,
        title=title,
        subtitle=subtitle or f"HRV {hrv_anomaly_pct:+.1f}% vs baseline",
        payload=payload,
        actions=default_actions,
        widget_id=widget_id
    )
