"""
Unit Tests for GYMBro In-Chat Native Interactive Chart & Action Widget Protocol (gymbro.widget/v1).
"""

import pytest
from app.agent.widget_protocol import (
    GYMBRO_WIDGET_PROTOCOL,
    WIDGET_TYPE_INTERACTIVE_CHART,
    WIDGET_TYPE_CALENDAR_PROPOSAL,
    WIDGET_TYPE_MACRO_SLIDER,
    WIDGET_TYPE_READINESS_ACTION,
    WIDGET_STATE_PROPOSED,
    build_widget_envelope,
    build_interactive_chart_widget,
    build_calendar_proposal_widget,
    build_macro_slider_widget,
    build_readiness_action_widget
)
from app.agent.tools import (
    render_chart,
    generate_training_plan_tool,
    tune_macro_targets_tool,
    evaluate_readiness_anomaly_tool
)
from app.coach.service import process_coach_message


def test_build_widget_envelope_defaults():
    payload = {"foo": "bar"}
    envelope = build_widget_envelope(
        widget_type="test_widget",
        title="Test Widget",
        payload=payload
    )

    assert envelope["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert envelope["widget_type"] == "test_widget"
    assert envelope["title"] == "Test Widget"
    assert envelope["state"] == WIDGET_STATE_PROPOSED
    assert envelope["payload"] == payload
    assert isinstance(envelope["actions"], list)
    assert envelope["widget_id"].startswith("test_")
    assert "emitted_at" in envelope


def test_build_interactive_chart_widget():
    metrics = [
        {"key": "hrv", "label": "HRV", "unit": "ms", "color": "#059669", "y_axis": "left", "chart_type": "line"},
        {"key": "sleep", "label": "Sleep", "unit": "pts", "color": "#4F46E5", "y_axis": "right", "chart_type": "bar"}
    ]
    points = [
        {"date": "08-01", "label": "Fri", "values": {"hrv": 72, "sleep": 85}, "flag": "optimal"},
        {"date": "08-02", "label": "Sat", "values": {"hrv": 45, "sleep": 58}, "flag": "alert", "annotation": "Dip"}
    ]

    widget = build_interactive_chart_widget(
        title="Recovery Trend",
        time_range="14d",
        metrics=metrics,
        points=points,
        subtitle="Correlation Analysis",
        summary_insight="HRV dipped on Aug 02."
    )

    assert widget["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert widget["widget_type"] == WIDGET_TYPE_INTERACTIVE_CHART
    assert widget["title"] == "Recovery Trend"
    assert widget["payload"]["time_range"] == "14d"
    assert widget["payload"]["metrics"] == metrics
    assert widget["payload"]["points"] == points
    assert widget["payload"]["interactive_scrubbing"] is True
    assert len(widget["actions"]) > 0


def test_build_calendar_proposal_widget():
    sessions = [
        {"day_name": "Mon", "title": "Easy Run", "tag": "Zone 2", "duration": 45, "distance": 7.0},
        {"day_name": "Wed", "title": "Threshold Intervals", "tag": "Threshold", "duration": 50, "distance": 8.0}
    ]

    widget = build_calendar_proposal_widget(
        title="10K Training Week 1",
        horizon="micro",
        sessions=sessions,
        target_volume_km=15.0
    )

    assert widget["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert widget["widget_type"] == WIDGET_TYPE_CALENDAR_PROPOSAL
    assert widget["payload"]["total_sessions"] == 2
    assert widget["payload"]["sessions"] == sessions
    assert widget["actions"][0]["id"] == "commit_calendar"
    assert widget["actions"][0]["endpoint"] == "/calendar/commit"


def test_build_macro_slider_widget():
    widget = build_macro_slider_widget(
        title="Daily Nutrition Tuning",
        protein_g=175,
        carbs_g=220,
        fats_g=60,
        goal_type="recomp"
    )

    assert widget["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert widget["widget_type"] == WIDGET_TYPE_MACRO_SLIDER
    assert widget["payload"]["protein_g"] == 175
    assert widget["payload"]["carbs_g"] == 220
    assert widget["payload"]["fats_g"] == 60
    assert len(widget["payload"]["presets"]) >= 3
    assert widget["actions"][0]["id"] == "commit_macros"


def test_build_readiness_action_widget():
    orig = {"title": "Threshold Intervals", "duration": 55, "intensity": "Hard"}
    suggested = {"title": "Zone 2 Recovery Flush", "duration": 40, "intensity": "Easy"}

    widget = build_readiness_action_widget(
        title="Morning Readiness Alert",
        readiness_score=52,
        hrv_anomaly_pct=-19.5,
        sleep_score=60,
        recommendation="Swap hard intervals for easy recovery flush.",
        original_session=orig,
        suggested_session=suggested
    )

    assert widget["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert widget["widget_type"] == WIDGET_TYPE_READINESS_ACTION
    assert widget["payload"]["readiness_score"] == 52
    assert widget["payload"]["hrv_anomaly_pct"] == -19.5
    assert widget["payload"]["original_session"] == orig
    assert widget["payload"]["suggested_session"] == suggested
    assert len(widget["actions"]) == 2
    assert widget["actions"][0]["id"] == "accept_reschedule"


def test_agent_tools_macro_and_readiness():
    macro_widget = tune_macro_targets_tool("user_1", protein_g=160, carbs_g=200, fats_g=50)
    assert macro_widget["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert macro_widget["type"] == "MACRO_SLIDER"

    readiness_widget = evaluate_readiness_anomaly_tool(
        user_id="user_1",
        readiness_score=58,
        hrv_anomaly_pct=-15.0,
        sleep_score=65,
        recommendation="Take it easy today",
        original_session={"title": "Intervals"},
        suggested_session={"title": "Recovery Run"}
    )
    assert readiness_widget["protocol"] == GYMBRO_WIDGET_PROTOCOL
    assert readiness_widget["type"] == "READINESS_ACTION"


def test_process_coach_message_triggers_widgets():
    # Macro trigger
    res_macro = process_coach_message("user_test", "Can you adjust my daily macros for body recomp?")
    assert res_macro["ui_payload"] is not None
    assert res_macro["ui_payload"]["widget_type"] == WIDGET_TYPE_MACRO_SLIDER

    # Readiness trigger
    res_readiness = process_coach_message("user_test", "I feel fatigued and sore, should I reschedule?")
    assert res_readiness["ui_payload"] is not None
    assert res_readiness["ui_payload"]["widget_type"] == WIDGET_TYPE_READINESS_ACTION

    # Resting Heart Rate plot trigger
    res_rhr = process_coach_message("user_test", "can you give me a plot of my resting heart rate?")
    assert res_rhr["ui_payload"] is not None
    assert res_rhr["ui_payload"]["widget_type"] == WIDGET_TYPE_INTERACTIVE_CHART
    assert "heart" in res_rhr["ui_payload"]["title"].lower() or "rhr" in res_rhr["ui_payload"]["title"].lower()
    assert not res_rhr["response"].startswith("I've analyzed your telemetry and updated your fast context")

    # HRV plot trigger
    res_hrv = process_coach_message("user_test", "Show me my hrv trend")
    assert res_hrv["ui_payload"] is not None
    assert res_hrv["ui_payload"]["widget_type"] == WIDGET_TYPE_INTERACTIVE_CHART

