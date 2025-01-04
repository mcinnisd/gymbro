from pymongo import MongoClient
from datetime import datetime, timedelta, UTC

client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["gymbro_db"]
garmin_daily = db["garmin_daily"]
garmin_sleep = db["garmin_sleep"]
summaries_collection = db["summaries"]

def create_daily_summary(user_id, date=None):
    """
    Generates a daily summary for the given user_id and date (YYYY-MM-DD).
    If date is None, defaults to today's date in UTC.
    """
    if not date:
        date = datetime.now(UTC).strftime("%Y-%m-%d")

    # Convert string to datetime object for queries (assuming daily docs store date)
    day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    # 1) Fetch Garmin daily data
    daily_doc = garmin_daily.find_one({
        "user_id": user_id,
        "date": {"$gte": day_start, "$lt": day_end}
    })
    # Example fields in daily_doc:
    # { steps: 9500, calories: 2200, ... }

    # 2) Fetch Sleep Data
    sleep_doc = garmin_sleep.find_one({
        "user_id": user_id,
        "sleep_date": {"$gte": day_start, "$lt": day_end}
    })
    # Example fields in sleep_doc:
    # { total_sleep: 7.2, deep_sleep: 1.5, rem_sleep: 1.2, ... }

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
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }

    # 4) Upsert into `summaries` collection
    summaries_collection.update_one(
        {
            "user_id": user_id,
            "summary_type": "daily",
            "date": day_start
        },
        {"$set": summary},
        upsert=True
    )
    return summary

if __name__ == "__main__":
    # Example usage:
    user_id = "john123"
    date_str = "2025-01-03"
    daily_summary = create_daily_summary(user_id, date_str)
    print("Daily summary created/updated:", daily_summary)