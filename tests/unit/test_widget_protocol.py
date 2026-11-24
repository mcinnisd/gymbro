import pytest
from app.agent.tools import evaluate_readiness_anomaly_tool, tune_macro_targets_tool
from app.agent.widget_protocol import (
    GYMBRO_WIDGET_PROTOCOL, WIDGET_TYPE_INTERACTIVE_CHART, WIDGET_TYPE_MACRO_SLIDER,
    WIDGET_TYPE_READINESS_ACTION, build_calendar_proposal_widget, build_interactive_chart_widget,
    build_macro_slider_widget, build_readiness_action_widget, build_widget_envelope,
)
from app.coach.service import process_coach_message


def test_widget_builders_keep_protocol_payload_and_actions():
    envelope = build_widget_envelope(widget_type="test_widget", title="Test Widget", payload={"foo": "bar"})
    assert envelope["protocol"] == GYMBRO_WIDGET_PROTOCOL and envelope["payload"] == {"foo": "bar"}
    chart = build_interactive_chart_widget(
        title="Recovery Trend", time_range="14d",
        metrics=[{"key": "hrv", "label": "HRV", "unit": "ms", "color": "#059669"}],
        points=[{"date": "08-01", "values": {"hrv": 72}}],
    )
    assert chart["widget_type"] == WIDGET_TYPE_INTERACTIVE_CHART and chart["payload"]["interactive_scrubbing"] is True
    calendar = build_calendar_proposal_widget(
        title="Week", horizon="micro",
        sessions=[{"day_name": "Mon", "title": "Easy Run"}, {"day_name": "Wed", "title": "Intervals"}],
    )
    assert calendar["payload"]["total_sessions"] == 2 and calendar["actions"][0]["id"] == "commit_calendar"
    macros = build_macro_slider_widget(title="Tune", protein_g=175, carbs_g=220, fats_g=60)
    assert macros["widget_type"] == WIDGET_TYPE_MACRO_SLIDER and macros["payload"]["protein_g"] == 175
    ready = build_readiness_action_widget(
        title="Alert", readiness_score=52, hrv_anomaly_pct=-19.5, sleep_score=60,
        recommendation="Easy day", original_session={"title": "Hard"}, suggested_session={"title": "Easy"},
    )
    assert ready["widget_type"] == WIDGET_TYPE_READINESS_ACTION and len(ready["actions"]) == 2


def test_agent_tools_and_coach_messages_emit_the_matching_widget():
    assert tune_macro_targets_tool("user_1", protein_g=160, carbs_g=200, fats_g=50)["type"] == "MACRO_SLIDER"
    assert evaluate_readiness_anomaly_tool(
        user_id="user_1", readiness_score=58, hrv_anomaly_pct=-15, sleep_score=65,
        recommendation="Easy", original_session={"title": "Intervals"}, suggested_session={"title": "Recovery"},
    )["type"] == "READINESS_ACTION"
    cases = (
        ("adjust my daily macros for body recomp", WIDGET_TYPE_MACRO_SLIDER),
        ("I feel fatigued and sore, should I reschedule?", WIDGET_TYPE_READINESS_ACTION),
        ("can you give me a plot of my resting heart rate?", WIDGET_TYPE_INTERACTIVE_CHART),
        ("Show me my hrv trend", WIDGET_TYPE_INTERACTIVE_CHART),
    )
    for message, kind in cases:
        result = process_coach_message("user_test", message)
        assert result["ui_payload"]["widget_type"] == kind
        assert result["ui_payload"]["protocol"] == GYMBRO_WIDGET_PROTOCOL
