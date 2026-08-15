"""
GYMBro Agent Tool Models & Execution Contracts.

Defines the canonical Pydantic models for tool execution, results, mutation policies,
and structured UI widget returns across the Agent Engine and MCP Server adapters.
"""

from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field


class MutationPolicy(BaseModel):
    """
    Specifies the execution safety policy for a tool.
    """
    category: Literal["read", "direct_edit", "proposal", "analytics"] = Field(
        ...,
        description="Tool execution category: read (autonomous), direct_edit (user-intent driven), proposal (two-phase approval required), or analytics (dual-output)."
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this tool invocation requires explicit user confirmation before committing state changes."
    )
    confirmation_message: Optional[str] = Field(
        default=None,
        description="Human-readable prompt displayed when confirmation is required."
    )


class ToolExecutionContext(BaseModel):
    """
    Runtime execution context injected by backend middleware.
    Never populated or overridden by LLM-generated arguments.
    """
    user_id: str = Field(..., description="Authenticated athlete identifier.")
    session_id: Optional[str] = Field(default=None, description="Active chat or coaching session identifier.")
    client_platform: Optional[str] = Field(default="expo_mobile", description="Client source platform (expo_mobile, web, mcp_agent).")


class ToolResult(BaseModel):
    """
    Unified return type for all GYMBro domain tools.
    Feeds observation text to the LLM, raw data to programmatic/MCP consumers,
    and structured widget envelopes to the Expo client.
    """
    success: bool = Field(default=True, description="Whether tool execution completed successfully.")
    observation: str = Field(..., description="Concise text or markdown fed back to the LLM reasoning context.")
    ui_payload: Optional[Dict[str, Any]] = Field(default=None, description="gymbro.widget/v1 envelope for native Expo client rendering.")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Raw structured data payload for programmatic / MCP consumers.")
    error: Optional[str] = Field(default=None, description="Error message if execution failed.")


class ToolDefinition(BaseModel):
    """
    Canonical metadata and schema definition for an Agent tool.
    """
    name: str = Field(..., description="Unique tool identifier name.")
    description: str = Field(..., description="Detailed description of tool purpose and usage.")
    parameters_schema: Dict[str, Any] = Field(..., description="JSON Schema object for tool arguments.")
    mutation_policy: MutationPolicy = Field(..., description="Execution and safety policy.")
    tags: List[str] = Field(default_factory=list, description="Categorization tags (e.g. telemetry, calendar, nutrition).")
