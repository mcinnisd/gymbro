"""
Mutation policy metadata for MCP-exposed tools (ADR-0003 §2).

Read/analytics tools run freely. Proposal and destructive deletes require an
explicit `confirm=true` argument before the domain tool is invoked.
"""

from __future__ import annotations

from typing import Dict

from app.tools.models import MutationPolicy

# Tools that require confirm=true before execution over MCP.
CONFIRM_PARAM = "confirm"

TOOL_MUTATION_POLICIES: Dict[str, MutationPolicy] = {
    # Reads
    "get_calendar_events": MutationPolicy(category="read", requires_approval=False),
    "get_recent_activities": MutationPolicy(category="read", requires_approval=False),
    "get_wellness_metrics": MutationPolicy(category="read", requires_approval=False),
    "get_biomarkers": MutationPolicy(category="read", requires_approval=False),
    "get_biomarker_trends": MutationPolicy(category="read", requires_approval=False),
    # Analytics
    "generate_chart": MutationPolicy(category="analytics", requires_approval=False),
    # Direct edits (autonomous on explicit tool call)
    "create_calendar_event": MutationPolicy(category="direct_edit", requires_approval=False),
    "update_calendar_event": MutationPolicy(category="direct_edit", requires_approval=False),
    "update_goal": MutationPolicy(category="direct_edit", requires_approval=False),
    "log_meal": MutationPolicy(category="direct_edit", requires_approval=False),
    "reschedule_workout": MutationPolicy(category="direct_edit", requires_approval=False),
    "log_manual_workout": MutationPolicy(category="direct_edit", requires_approval=False),
    # Destructive delete — require confirm for MCP clients
    "delete_calendar_event": MutationPolicy(
        category="direct_edit",
        requires_approval=True,
        confirmation_message=(
            "This permanently deletes a calendar event. "
            "Re-call with confirm=true to proceed."
        ),
    ),
    # Bulk / generative — two-phase proposal (ADR-0003)
    "generate_training_plan": MutationPolicy(
        category="proposal",
        requires_approval=True,
        confirmation_message=(
            "Generating a training plan writes multiple calendar sessions. "
            "Re-call with confirm=true to commit the plan."
        ),
    ),
}


def get_mutation_policy(tool_name: str) -> MutationPolicy:
    return TOOL_MUTATION_POLICIES.get(
        tool_name,
        MutationPolicy(category="direct_edit", requires_approval=False),
    )


def requires_confirm(tool_name: str) -> bool:
    return bool(get_mutation_policy(tool_name).requires_approval)
