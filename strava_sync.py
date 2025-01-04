# strava_sync.py

import os
import requests
from pymongo import MongoClient
from datetime import datetime, UTC

# ----------------------
#  CONFIG / CONSTANTS
# ----------------------

STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Hard-coded or environment variables (recommended).
# Make sure these have correct scopes (e.g. activity:read, activity:read_all).
# In production, do NOT hardcode:
# STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "YOUR_CLIENT_ID")
# STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
# STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN", "YOUR_REFRESH_TOKEN")

# hardcoded for now
# STRAVA_CLIENT_ID="144064"
# STRAVA_CLIENT_SECRET="bc4f5112b3468717230d8746647d8a38aaaebfd5"
# STRAVA_REFRESH_TOKEN="972c97ad1dd1062b30ed394c46c52f53f375daad"

STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "YOUR_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "YOUR_CLIENT_SECRET")


# MongoDB setup
client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["gymbro_db"]
activities_collection = db["strava_activities"]
users_collection = db["users"]

def refresh_strava_access_token(user_id):
    """
    Use the stored refresh token to get a short-lived access token from Strava.
    """
    user_doc = users_collection.find_one({"user_id": user_id})
    if not user_doc:
        print(f"No user doc found for user_id={user_id}")
        return None

    refresh_token = user_doc["refresh_token"]

    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]

        # Update the user doc with new tokens
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "last_updated": datetime.now(UTC)
                }
            }
        )
        return new_access_token
    else:
        print("Error refreshing access token:", response.text)
        return None

def fetch_strava_activities(access_token, page=1, per_page=30):
    """
    Fetch a page of Strava activities using the given access token.
    """
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"page": page, "per_page": per_page}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    else:
        print("Error fetching Strava activities:", resp.text)
        return []
    
def sync_strava_activities(user_id):
    """
    Pulls Strava activities for the user, storing new ones in MongoDB.
    Avoids duplicates by checking 'activity_id'.
    """
    access_token = refresh_strava_access_token(user_id)
    if not access_token:
        print("Could not get a valid access token. Stopping sync.")
        return

    existing_ids = set(
        doc["activity_id"] for doc in activities_collection.find({}, {"activity_id": 1, "_id": 0})
    )

    page = 1
    total_inserted = 0
    while True:
        activities = fetch_strava_activities(access_token, page=page, per_page=30)
        if not activities:
            break  # No more data or error

        new_activities = [act for act in activities if str(act["id"]) not in existing_ids]
        if not new_activities:
            page += 1
            continue

        batch_to_insert = []
        for act in new_activities:
            doc = {
                "activity_id": str(act["id"]),
                "name": act.get("name"),
                "type": act.get("type"),
                "distance": act.get("distance"),
                "moving_time": act.get("moving_time"),
                "elapsed_time": act.get("elapsed_time"),
                "total_elevation_gain": act.get("total_elevation_gain"),
                "start_date_local": act.get("start_date_local"),
                "average_speed": act.get("average_speed"),
                "max_speed": act.get("max_speed"),
                "calories": act.get("calories"),
                "user_id": user_id,
                "raw_data": act,
                "synced_at": datetime.now(UTC),
            }
            batch_to_insert.append(doc)

        activities_collection.insert_many(batch_to_insert)
        total_inserted += len(batch_to_insert)

        # Add newly inserted IDs to the set
        for doc in batch_to_insert:
            existing_ids.add(doc["activity_id"])

        page += 1

    print(f"Sync finished. Inserted {total_inserted} new activities.")




