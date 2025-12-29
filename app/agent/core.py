"""
Core Agent Architecture.

Defines the base Agent class that implements the Think -> Act -> Observe loop.
Uses the Tool Registry to expose capabilities to the LLM.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Generator

from app.utils.llm_utils import generate_chat_response
from app.tools.registry import get_tool_definitions, get_tool_implementation

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, name: str, system_prompt: str, model_name: str = None, provider: str = None):
        self.name = name
        self.system_prompt = system_prompt
        self.model_name = model_name
        self.provider = provider
        self.tools = get_tool_definitions()

    def run(self, user_id: str, message: str, context: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Main execution loop for the agent.
        Participates in a "Think -> Act -> Observe" loop.
        Yields status updates and final response chunks.
        """
        logger.info(f"Agent {self.name} starting run for user {user_id}")
        yield {"status": f"{self.name} is thinking..."}
        
        conversation_history = [
            {"role": "user", "content": f"Context:\n{context}\n\nUser Request: {message}"}
        ]

        # Maximum depth to prevent infinite loops
        max_turns = 5
        current_turn = 0
        
        while current_turn < max_turns:
            current_turn += 1
            
            # 1. THINK
            logger.info(f"Agent {self.name} thinking (turn {current_turn})...")
            # yield {"status": "Thinking..."} # Optional granularity
            
            response = self._think(conversation_history)
            
            # Check if likely a tool call (naive check for JSON block)
            tool_call = self._detect_tool_call(response)
            
            if tool_call:
                # 2. ACT
                logger.info(f"Agent {self.name} acting: {tool_call['name']}")
                yield {"status": f"Using tool: {tool_call['name']}..."}
                
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                
                # Execute tool
                tool_result = self._act(tool_name, tool_args, user_id)
                
                # Check if tool result has special frontend payloads (like charts)
                if isinstance(tool_result, dict) and "type" in tool_result and tool_result["type"] in ["line", "bar", "pie", "doughnut"]:
                     # It's a Chart.js config! Yield it.
                     yield {"chart": tool_result}
                
                # 3. OBSERVE
                logger.info(f"Agent {self.name} observed result.")
                
                # Append tool use and result to history
                conversation_history.append({"role": "assistant", "content": response})
                conversation_history.append({
                    "role": "user", 
                    "content": f"Tool '{tool_name}' Output:\n{json.dumps(tool_result, indent=2)}\n\nContinue helping the user based on this information."
                })
                
            else:
                # Final response (no more tools needed)
                # Yield the final text
                yield {"status": "Complete"}
                yield {"answer": response}
                return

        yield {"error": "Deep thought loop exceeded."}

    def _think(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM to generate the next response."""
        # Inject tool definitions into system prompt if not already there
        # For simplicity, we append them here or rely on the LLM knowing them via system prompt injection
        tool_desc = json.dumps(self.tools, indent=2)
        full_system_prompt = f"{self.system_prompt}\n\nYou have access to the following tools. To use them, output a JSON object with 'tool': 'tool_name' and 'arguments': {{...}}.\nTOOLS:\n{tool_desc}"
        
        response = generate_chat_response(
            messages=messages,
            system_prompt=full_system_prompt,
            mode="agent", # arbitrary mode
            model_name=self.model_name,
            provider=self.provider
        )
        return response

    def _detect_tool_call(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parses the response to see if it contains a tool call.
        Expected format: JSON object with "tool" and "arguments".
        """
        try:
            # Look for JSON block
            if "{" in response_text and "}" in response_text:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    if "tool" in data and "arguments" in data:
                        return {"name": data["tool"], "arguments": data["arguments"]}
        except Exception:
            pass
        return None

    def _act(self, tool_name: str, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute the tool."""
        func = get_tool_implementation(tool_name)
        if not func:
            return {"error": f"Tool {tool_name} not found."}
        
        # Inject user_id if not present in args
        if "user_id" not in args:
            args["user_id"] = user_id
            
        try:
            return func(**args)
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}
