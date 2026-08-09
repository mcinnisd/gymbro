# app/strava/sync.py

import os
import requests
import logging
from flask import current_app
from datetime import datetime, timezone
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def refresh_strava_access_token(user_id):
    """
    Use the stored refresh token to get a short-lived access token from Strava.
    Updates the Supabase users table with the new tokens.
    """
    try:
        response = supabase.table("users").select("strava_refresh_token").eq("id", user_id).execute()
        if not response.data:
            logger.error(f"No user found with id={user_id}")
            return None

        refresh_token = response.data[0].get("strava_refresh_token")
        if not refresh_token:
            logger.error(f"User {user_id} does not have a Strava refresh token stored.")
            return None

        url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": current_app.config.get("STRAVA_CLIENT_ID"),
            "client_secret": current_app.config.get("STRAVA_CLIENT_SECRET"),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        resp = requests.post(url, data=payload)
        if resp.status_code == 200:
            new_tokens = resp.json()
            new_access_token = new_tokens["access_token"]
            new_refresh_token = new_tokens["refresh_token"]

            # Update tokens in Supabase
            supabase.table("users").update({
                "strava_access_token": new_access_token,
                "strava_refresh_token": new_refresh_token,
                "strava_last_updated": datetime.now(timezone.utc).isoformat()
            }).eq("id", user_id).execute()

            return new_access_token
        else:
            logger.error(f"Error refreshing Strava access token for user {user_id}: {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Failed to refresh Strava token for user {user_id}: {e}")
        return None

def fetch_strava_activities(access_token, page=1, per_page=30):
    """
    Fetch a page of Strava activities using the given access token.
    """
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"page": page, "per_page": per_page}
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error(f"Error fetching Strava activities: {resp.text}")
            return []
    except Exception as e:
        logger.error(f"Failed to fetch Strava activities: {e}")
        return []

def sync_strava_activities(user_id):
    """
    Pulls Strava activities for the user, storing/updating them in Supabase.
    """
    access_token = refresh_strava_access_token(user_id)
    if not access_token:
        logger.error(f"Could not get a valid access token for user {user_id}. Stopping sync.")
        return

    # Fetch existing synced activity IDs to skip duplicates
    existing_ids = set()
    try:
        res = supabase.table("strava_activities").select("activity_id").eq("user_id", user_id).execute()
        if res.data:
            existing_ids = {r["activity_id"] for r in res.data}
    except Exception as e:
        logger.error(f"Error fetching existing Strava activity IDs: {e}")

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
                "user_id": user_id,
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
                "raw_data": act,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                
                # Performance fields
                "average_hr": act.get("average_heartrate"),
                "max_hr": act.get("max_heartrate"),
                "elevation_gain": act.get("total_elevation_gain"),
                "average_speed_perf": act.get("average_speed"),
                "max_speed_perf": act.get("max_speed"),
                "average_cadence": act.get("average_cadence")
            }
            batch_to_insert.append(doc)

        if batch_to_insert:
            try:
                supabase.table("strava_activities").upsert(batch_to_insert, on_conflict="activity_id").execute()
                total_inserted += len(batch_to_insert)
                for doc in batch_to_insert:
                    existing_ids.add(doc["activity_id"])
            except Exception as e:
                logger.error(f"Failed to upsert Strava activities: {e}")
                break

        page += 1

    logger.info(f"Strava sync finished. Synced {total_inserted} new activities for user {user_id}.")
