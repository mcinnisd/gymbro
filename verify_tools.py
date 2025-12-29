
import json
import logging
from app.tools.registry import get_tool_definitions, get_tool_implementation
from app.tools.calendar_tools import create_event

# Configure logging to see errors
logging.basicConfig(level=logging.ERROR)

def verify_tools():
    print("Verifying Tool Registry...")
    tools = get_tool_definitions()
    
    # Check 1: Registry returns list
    if not isinstance(tools, list):
        print("FAIL: get_tool_definitions did not return a list.")
        return
    
    print(f"PASS: Found {len(tools)} tool definitions.")
    
    # Check 2: Check standard keys
    required_tools = ["create_calendar_event", "get_calendar_events", "update_calendar_event", "delete_calendar_event", "generate_chart"]
    found_tools = [t["function"]["name"] for t in tools]
    
    missing = set(required_tools) - set(found_tools)
    if missing:
        print(f"FAIL: Missing tool definitions: {missing}")
    else:
        print(f"PASS: All required tools defined: {found_tools}")

    # Check 3: Check implementation mapping
    print("\nVerifying Implementations...")
    for t_name in required_tools:
        func = get_tool_implementation(t_name)
        if not func:
            print(f"FAIL: No implementation found for {t_name}")
        elif not callable(func):
            print(f"FAIL: Implementation for {t_name} is not callable")
        else:
            print(f"PASS: {t_name} mapped to {func.__name__}")

    # Check 4: Check calendar_tools return type (mock call not possible easily without DB, but checking import)
    # We rely on static verification that we overwrote it.
    print("\nVerifying imports...")
    try:
        from app.tools.calendar_tools import create_event
        # Inspect source code of create_event via introspection?
        # Or just checking if it is importable is enough for syntax check.
        print("PASS: app.tools.calendar_tools imported successfully.")
    except Exception as e:
        print(f"FAIL: Could not import calendar_tools: {e}")

if __name__ == "__main__":
    verify_tools()
