"""
Tool Registry for LLM Function Calling.
Defines the JSON schemas (OpenAI format) for available tools.
"""

from app.tools.calendar_tools import create_event, get_events, update_event, delete_event
from app.context.chart_generator import generate_chart_data
from app.tools.goal_tools import update_goal
from app.tools.plan_tools import generate_training_plan

TOOLS_REGISTRY = [
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a new training event in the user's calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date of the event in YYYY-MM-DD format."
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the workout (e.g., '5k Easy Run')."
                    },
                    "event_type": {
                        "type": "string",
                        "enum": ["run", "strength", "rest", "race", "other"],
                        "description": "Type of the event."
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional details about the workout."
                    }
                },
                "required": ["date", "title", "event_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": "Retrieve training events from the calendar for a specific date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD). Defaults to today if omitted."
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD). Defaults to 7 days from start."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_calendar_event",
            "description": "Update an existing calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The ID of the event to update."
                    },
                    "updates": {
                        "type": "object",
                        "description": "Dictionary of fields to update (date, title, description, event_type, status).",
                        "properties": {
                            "date": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "status": {"type": "string", "enum": ["planned", "completed", "skipped"]}
                        }
                    }
                },
                "required": ["event_id", "updates"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Delete a training event from the calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The ID of the event to delete."
                    }
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Generate a chart visualization for a specific fitness metric over a time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "The metric(s) to visualize. Can be a single metric or comma-separated list (e.g. 'heart_rate,elevation') for activity scope. Options: pace, distance, hrv, training_load, heart_rate, cadence, elevation, sleep_score."
                    },
                    "period_days": {
                        "type": "integer",
                        "description": "Number of days to look back (default 30).",
                        "default": 30
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["trend", "activity"],
                        "description": "'trend' for over time, 'activity' for specific recent workout details.",
                        "default": "trend"
                    }
                },
                "required": ["metric"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_goal",
            "description": "Update a specific user fitness goal (e.g. set marathon pace to 5:00/km).",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_type": {
                        "type": "string",
                        "description": "Type of goal (e.g. 'marathon_pace', 'weekly_volume', 'weight')."
                    },
                    "target_value": {
                        "type": "string",
                        "description": "The target value (e.g. '5:00 min/km', '50km')."
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional context about the goal."
                    }
                },
                "required": ["goal_type", "target_value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_training_plan",
            "description": "Generate and populate a full training plan for multiple weeks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The primary goal (e.g. 'Sub-4 Marathon')."
                    },
                    "weeks": {
                        "type": "integer",
                        "description": "Duration in weeks.",
                        "default": 4
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date YYYY-MM-DD (defaults to today)."
                    }
                },
                "required": ["goal"]
            }
        }
    }
]

# Mapping of tool names to actual python functions
TOOL_IMPLEMENTATIONS = {
    "create_calendar_event": create_event,
    "get_calendar_events": get_events,
    "update_calendar_event": update_event,
    "delete_calendar_event": delete_event,
    "generate_chart": generate_chart_data,
    "update_goal": update_goal,
    "generate_training_plan": generate_training_plan
}

def get_tool_definitions():
    """Return the list of tool definitions for the LLM."""
    return TOOLS_REGISTRY

def get_tool_implementation(tool_name):
    """Return the python function for a given tool name."""
    return TOOL_IMPLEMENTATIONS.get(tool_name)
