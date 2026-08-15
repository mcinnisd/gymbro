import pytest
from app.tools.models import ToolResult, ToolExecutionContext, MutationPolicy, ToolDefinition


def test_tool_result_creation():
    res = ToolResult(
        success=True,
        observation="Found 3 recent runs totaling 24.5 km.",
        data={"total_km": 24.5, "count": 3}
    )
    assert res.success is True
    assert "24.5" in res.observation
    assert res.ui_payload is None
    assert res.data["count"] == 3


def test_tool_result_with_widget():
    from app.agent.widget_protocol import build_interactive_chart_widget
    
    widget = build_interactive_chart_widget(
        title="Pace Trend",
        time_range="30d",
        metrics=[{"key": "pace", "label": "Pace (min/km)", "unit": "min/km", "color": "#E07A5F"}],
        points=[{"date": "2026-08-01", "pace": 5.1}]
    )
    
    res = ToolResult(
        success=True,
        observation="Generated 30-day pace trend chart.",
        ui_payload=widget,
        data={"chart_id": widget["payload"]["chart_id"]}
    )
    assert res.ui_payload["protocol"] == "gymbro.widget/v1"
    assert res.ui_payload["widget_type"] == "interactive_chart"


def test_mutation_policy_validation():
    policy_read = MutationPolicy(category="read", requires_approval=False)
    assert policy_read.category == "read"
    assert not policy_read.requires_approval

    policy_prop = MutationPolicy(
        category="proposal",
        requires_approval=True,
        confirmation_message="Do you want to commit these 16 sessions to your calendar?"
    )
    assert policy_prop.category == "proposal"
    assert policy_prop.requires_approval


def test_execution_context_injection():
    ctx = ToolExecutionContext(user_id="ath_987", client_platform="expo_mobile")
    assert ctx.user_id == "ath_987"
    assert ctx.client_platform == "expo_mobile"
