# app/strava/sync.py

import os
import requests
from flask import current_app
from bson import ObjectId
from datetime import datetime, timezone, UTC

def refresh_strava_access_token(user_id):
    """
    Use the stored refresh token to get a short-lived access token from Strava.
    """
    user_doc = current_app.mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        current_app.logger.error(f"No user doc found for user_id={user_id}")
        return None

    refresh_token = user_doc.get("strava_refresh_token")
    if not refresh_token:
        current_app.logger.error(f"User {user_id} does not have a Strava refresh token stored.")
        return None

    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": current_app.config.get("STRAVA_CLIENT_ID"),
        "client_secret": current_app.config.get("STRAVA_CLIENT_SECRET"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]

        # Update the user doc with new tokens
        current_app.mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "strava_access_token": new_access_token,
                    "strava_refresh_token": new_refresh_token,
                    "strava_last_updated": datetime.now(timezone.utc)
                }
            }
        )
        return new_access_token
    else:
        current_app.logger.error(f"Error refreshing Strava access token for user {user_id}: {response.text}")
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
        current_app.logger.error(f"Error fetching Strava activities: {resp.text}")
        return []

def sync_strava_activities(user_id):
    """
    Pulls Strava activities for the user, storing new ones in MongoDB.
    Avoids duplicates by checking 'activity_id'.
    """
    access_token = refresh_strava_access_token(user_id)
    if not access_token:
        current_app.logger.error(f"Could not get a valid access token for user {user_id}. Stopping sync.")
        return

    existing_ids = set(
        doc["activity_id"] for doc in current_app.mongo.db.strava_activities.find({"user_id": user_id}, {"activity_id": 1, "_id": 0})
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

        if batch_to_insert:
            current_app.mongo.db.strava_activities.insert_many(batch_to_insert)
            total_inserted += len(batch_to_insert)
            for doc in batch_to_insert:
                existing_ids.add(doc["activity_id"])

        page += 1

    current_app.logger.info(f"Strava sync finished. Inserted {total_inserted} new activities for user {user_id}.")
