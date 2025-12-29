
import json
import logging
from unittest.mock import MagicMock
from app.agent.analyst import AnalystAgent

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_agent_loop():
    print("Testing Agent Loop...")
    
    agent = AnalystAgent()
    
    # Mock _think to return a tool call first, then a final answer
    # Turn 1: Call create_calendar_event
    # Turn 2: Final answer
    
    responses = [
        json.dumps({
            "tool": "create_calendar_event",
            "arguments": {
                "user_id": "123",
                "date": "2023-10-27",
                "title": "Test Run",
                "event_type": "run",
                "description": "Testing the brain"
            }
        }),
        "I have created the event for you."
    ]
    
    agent._think = MagicMock(side_effect=responses)
    
    # Mock the tool implementation to avoid DB calls
    # We need to mock get_tool_implementation in the core module
    # But since we imported Agent from core, we can mock the method on the instance or monkeypatch
    
    # Let's monkeypatch _act instead to just return success
    agent._act = MagicMock(return_value={"status": "success", "message": "Mock Event Created"})
    
    print("Running agent...")
    # Consume generator
    gen = agent.run(user_id="123", message="Schedule a run for today")
    final_response = None
    status_updates = []
    
    for update in gen:
        print(f"Update: {update}")
        if "status" in update:
            status_updates.append(update["status"])
        if "answer" in update:
            final_response = update["answer"]

    print(f"Final Response: {final_response}")
    
    # Verify loop behavior
    if agent._think.call_count == 2:
        print("PASS: Agent thought twice (Once for tool, once for final).")
    else:
        print(f"FAIL: Agent thought {agent._think.call_count} times.")
        
    if agent._act.call_count == 1:
        print("PASS: Agent acted once.")
    else:
        print(f"FAIL: Agent acted {agent._act.call_count} times.")
        
    if final_response == "I have created the event for you.":
        print("PASS: Final response matches.")
    else:
        print("FAIL: Final response mismatch.")
        
    if len(status_updates) > 0:
        print(f"PASS: Received {len(status_updates)} status updates.")
    else:
        print("FAIL: No status updates received.")

if __name__ == "__main__":
    test_agent_loop()
