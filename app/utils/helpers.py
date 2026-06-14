# app/utils/helpers.py

import base64
import json
import re
from typing import Any, Optional

def format_conversation(messages):
    """
    Formats a list of message objects (each a dict with 'role' and 'content')
    into a single newline-separated string.
    """
    return "\n".join(f"{msg.get('role', 'UNKNOWN').upper()}: {msg.get('content', '')}" for msg in messages)


def encode_image(image_bytes):
    """
    Encode image bytes to a base64 string.
    """
    try:
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def clean_response(response_text):
    """
    Clean the response text to extract JSON by removing Markdown code block delimiters.
    """
    if response_text.startswith("```") and response_text.endswith("```"):
        lines = response_text.split('\n')
        if len(lines) >= 3:
            return '\n'.join(lines[1:-1])
    return response_text

def parse_openai_response(response_text):
    """
    Parse the OpenAI JSON response to extract macro estimates.
    """
    try:
        cleaned_response = clean_response(response_text)
        data = json.loads(cleaned_response)
        
        # Normalize keys
        normalized_data = {}
        for key, value in data.items():
            normalized_key = key.split('(')[0].strip().lower()
            normalized_data[normalized_key] = value
        
        # Extract required fields
        calories = normalized_data.get("calories")
        fat = normalized_data.get("fat")
        carbohydrates = normalized_data.get("carbohydrates")
        protein = normalized_data.get("protein")
        
        if None in (calories, fat, carbohydrates, protein):
            print("Missing one or more required fields in the response.")
            return None
        
        return {
            "calories": calories,
            "fat": fat,
            "carbohydrates": carbohydrates,
            "protein": protein
        }
    except json.JSONDecodeError:
        print("Failed to parse response as JSON.")
        return None
    except Exception as e:
        print(f"Error parsing OpenAI response: {e}")
        return None

def extract_json_from_text(text: str) -> Optional[Any]:
    """
    Finds and parses a JSON block (either object {...} or list [...]) from the given text.
    Returns the parsed Python data structure (dict or list), or None if parsing fails.
    """
    if not text or not isinstance(text, str):
        return None
        
    # Try finding an array first [ ... ]
    array_match = re.search(r'\[.*\]', text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass
            
    # Try finding an object next { ... }
    object_match = re.search(r'\{.*\}', text, re.DOTALL)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except json.JSONDecodeError:
            pass
            
    # Fallback to direct json.loads of the whole text if no delimiters found
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
        
    return None