#!/usr/bin/env python
"""Quick test to verify xAI API connection."""
import sys
sys.path.insert(0, '.')

from app.utils.llm_utils import generate_chat_response

def test_xai():
    print("Testing xAI API connection...")
    
    messages = [{"role": "user", "content": "Say 'Hello from Grok!' and tell me today's date."}]
    
    response = generate_chat_response(messages, mode="normal", provider="xai")
    
    print(f"Response: {response}")
    
    if "Error" in response:
        print("❌ xAI connection failed")
        return False
    else:
        print("✅ xAI connection successful!")
        return True

if __name__ == "__main__":
    test_xai()
