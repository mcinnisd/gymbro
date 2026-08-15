import logging
from typing import Dict, Any, Optional, List
from app.context.chart_generator import generate_chart_data
from app.tools.goal_tools import update_goal
from app.tools.plan_tools import generate_training_plan as base_generate_plan
from app.agent.widget_protocol import (
    GYMBRO_WIDGET_PROTOCOL,
    build_interactive_chart_widget,
    build_calendar_proposal_widget,
    build_macro_slider_widget,
    build_readiness_action_widget
)

logger = logging.getLogger(__name__)


def render_chart(user_id: str, metric: str, period_days: int = 30, scope: str = "trend") -> Dict[str, Any]:
    """
    Generates an interactive chart payload for rendering in the chat UI
    conforming to gymbro.widget/v1.
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
        
        # Convert to gymbro.widget/v1 format
        labels = chart_data.get("data", {}).get("labels", [])
        datasets = chart_data.get("data", {}).get("datasets", [])
        
        metrics_list = []
        points_list = []
        
        for ds in datasets:
            metrics_list.append({
                "key": metric,
                "label": ds.get("label", metric.title()),
                "unit": "ms" if "hrv" in metric else ("pts" if "sleep" in metric else "val"),
                "color": ds.get("borderColor", "#D97706"),
                "y_axis": "left",
                "chart_type": chart_data.get("type", "line")
            })

        for i, lbl in enumerate(labels):
            vals = {}
            for ds in datasets:
                data_arr = ds.get("data", [])
                vals[metric] = data_arr[i] if i < len(data_arr) else None
            points_list.append({
                "date": lbl,
                "label": lbl,
                "values": vals,
                "flag": "optimal"
            })

        widget = build_interactive_chart_widget(
            title=chart_data.get("title", f"{metric.title()} Trend"),
            subtitle=f"Last {period_days} Days Analysis",
            time_range=f"{period_days}d",
            metrics=metrics_list,
            points=points_list,
            summary_insight=f"Analyzed {len(points_list)} daily telemetry points for {metric}."
        )

        # Legacy backward-compatibility wrapper
        widget["type"] = "CHART"
        widget["data"] = chart_data
        return widget

    except Exception as e:
        logger.error(f"Error rendering chart for {metric}: {e}")
        return {
            "protocol": GYMBRO_WIDGET_PROTOCOL,
            "type": "CHART",
            "data": {
                "error": str(e),
                "metric": metric
            }
        }


def generate_training_plan_tool(user_id: str, goal: str, weeks: int = 4, start_date: str = None) -> Dict[str, Any]:
    """
    Generates a multi-week training plan and wraps it in a structured gymbro.widget/v1
    calendar proposal payload.
    """
    try:
        plan_res = base_generate_plan(user_id=user_id, goal=goal, weeks=weeks, start_date=start_date)
        
        # Build sessions list from plan_res
        raw_sessions = plan_res.get("workouts", []) if isinstance(plan_res, dict) else []
        sessions = []
        for s in raw_sessions:
            sessions.append({
                "day_name": s.get("day", "Day"),
                "title": s.get("title", s.get("name", "Workout")),
                "tag": s.get("intensity", "Aerobic Base"),
                "duration": s.get("duration", 45),
                "distance": s.get("distance", 0)
            })

        if not sessions:
            sessions = [
                {"day_name": "Mon", "title": "Base Aerobic Run", "tag": "Zone 2", "duration": 45, "distance": 7.0},
                {"day_name": "Tue", "title": "Threshold Intervals", "tag": "Threshold", "duration": 50, "distance": 8.5},
                {"day_name": "Wed", "title": "Strength & Mobility", "tag": "Strength", "duration": 45, "distance": 0},
                {"day_name": "Thu", "title": "Recovery Jog", "tag": "Recovery", "duration": 30, "distance": 5.0},
                {"day_name": "Sat", "title": "Progressive Long Run", "tag": "Long Run", "duration": 75, "distance": 14.0}
            ]

        widget = build_calendar_proposal_widget(
            title=f"Training Plan: {goal.title() if goal else 'Endurance Cycle'}",
            subtitle=f"{weeks}-Week Program Block",
            horizon="meso" if weeks >= 3 else "micro",
            target_volume_km=sum(s.get("distance", 0) for s in sessions),
            sessions=sessions
        )

        widget["type"] = "WORKOUT_PLAN"
        widget["data"] = plan_res
        return widget

    except Exception as e:
        logger.error(f"Error generating training plan tool output: {e}")
        return {
            "protocol": GYMBRO_WIDGET_PROTOCOL,
            "type": "WORKOUT_PLAN",
            "data": {"status": "error", "message": str(e)}
        }


def tune_macro_targets_tool(user_id: str, protein_g: int, carbs_g: int, fats_g: int, goal_type: str = "recomp") -> Dict[str, Any]:
    """
    Emits a dynamic macro slider tuning widget conforming to gymbro.widget/v1.
    """
    widget = build_macro_slider_widget(
        title="Macronutrient Target Tuning",
        protein_g=protein_g,
        carbs_g=carbs_g,
        fats_g=fats_g,
        goal_type=goal_type
    )
    widget["type"] = "MACRO_SLIDER"
    widget["data"] = widget["payload"]
    return widget


def evaluate_readiness_anomaly_tool(
    user_id: str,
    readiness_score: int,
    hrv_anomaly_pct: float,
    sleep_score: int,
    recommendation: str,
    original_session: Dict[str, Any],
    suggested_session: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Emits a morning readiness anomaly and reschedule proposal widget conforming to gymbro.widget/v1.
    """
    widget = build_readiness_action_widget(
        title="Morning Recovery Readiness Alert",
        readiness_score=readiness_score,
        hrv_anomaly_pct=hrv_anomaly_pct,
        sleep_score=sleep_score,
        recommendation=recommendation,
        original_session=original_session,
        suggested_session=suggested_session
    )
    widget["type"] = "READINESS_ACTION"
    widget["data"] = widget["payload"]
    return widget


def update_user_goals(user_id: str, goal_type: str, target_value: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates user goals and returns a structured GOALS UI payload.
    """
    try:
        res = update_goal(user_id=user_id, goal_type=goal_type, target_value=target_value, description=description)
        return {
            "protocol": GYMBRO_WIDGET_PROTOCOL,
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
            "protocol": GYMBRO_WIDGET_PROTOCOL,
            "type": "GOALS",
            "data": {"status": "error", "message": str(e)}
        }

