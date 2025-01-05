# app/utils/helpers.py

import base64
import json
from datetime import datetime, timedelta, timezone
from flask import current_app
from bson import ObjectId

def mongo_to_dict(doc):
    """Helper to convert MongoDB document to JSON-serializable dict."""
    return {
        "id": str(doc["_id"]),
        "activity_id": doc.get("activity_id"),
        "name": doc.get("name"),
        "type": doc.get("type"),
        "distance": doc.get("distance"),
        "moving_time": doc.get("moving_time"),
        "elapsed_time": doc.get("elapsed_time"),
        "total_elevation_gain": doc.get("total_elevation_gain"),
        "start_date_local": doc.get("start_date_local"),
        "average_speed": doc.get("average_speed"),
        "max_speed": doc.get("max_speed"),
        "calories": doc.get("calories"),
        "user_id": doc.get("user_id"),
        "raw_data": doc.get("raw_data"),
    }

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

def create_daily_summary(user_id, date=None):
    """
    Generates a daily summary for the given user_id and date (YYYY-MM-DD).
    If date is None, defaults to today's date in UTC.
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Convert string to datetime object for queries
    try:
        day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        print("Incorrect date format. Should be YYYY-MM-DD.")
        return None

    day_end = day_start + timedelta(days=1)

    db = current_app.mongo.db  # Access the MongoDB instance from Flask-PyMongo

    # 1) Fetch Garmin daily data
    daily_doc = db.garmin_daily.find_one({
        "user_id": user_id,
        "date": date  # Assuming 'date' is stored as a string in 'YYYY-MM-DD' format
    })

    # 2) Fetch Sleep Data
    sleep_doc = db.garmin_sleep.find_one({
        "user_id": user_id,
        "date": date  # Ensure the field name matches your data structure
    })

    # Handle missing docs gracefully
    daily_data = daily_doc if daily_doc else {}
    sleep_data = sleep_doc if sleep_doc else {}

    # 3) Build the summary
    summary = {
        "user_id": user_id,
        "summary_type": "daily",
        "date": day_start,  # store as a datetime for clarity
        "sleep_summary": {
            "total_sleep": sleep_data.get("total_sleep", 0),
            "deep_sleep": sleep_data.get("deep_sleep", 0),
            "rem_sleep": sleep_data.get("rem_sleep", 0),
            "light_sleep": sleep_data.get("light_sleep", 0),
        },
        "activity_summary": {
            "steps": daily_data.get("steps", 0),
            "active_calories": daily_data.get("active_calories", 0),
            "workouts": daily_data.get("workouts", []),
            # Add other fields as needed...
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    # 4) Upsert into `summaries` collection
    db.summaries.update_one(
        {
            "user_id": user_id,
            "summary_type": "daily",
            "date": day_start
        },
        {"$set": summary},
        upsert=True
    )
    return summary