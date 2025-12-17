# app/garmin/sync.py

import logging
from datetime import datetime, timedelta, date, timezone
from flask import current_app
from app.supabase_client import supabase

import requests
from garth.exc import GarthHTTPError
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from app.utils.encryption import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

def init_garmin_api_for_user(user_id: str, encryption_key: str = None):
    """
    Initializes Garmin API session for a specific user by decrypting stored credentials.
    """
    # Fetch user from Supabase
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not response.data:
        logger.error(f"No user found with user_id={user_id}")
        return None
    user_doc = response.data[0]

    garmin_email = user_doc.get("garmin_email")
    encrypted_password = user_doc.get("garmin_password")
    if not garmin_email or not encrypted_password:
        logger.error(f"User {user_id} does not have Garmin credentials stored.")
        return None

    try:
        # Decrypt the password
        garmin_password = decrypt_data(encrypted_password, key=encryption_key)
    except Exception as e:
        logger.error(f"Error decrypting Garmin password for user {user_id}: {e}")
        return None

    try:
        logger.info(f"Logging in to Garmin for user {user_id}...")
        api = Garmin(email=garmin_email, password=garmin_password)
        api.login()
        logger.info("Garmin login successful.")
        return api
    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        requests.exceptions.HTTPError,
        GarthHTTPError,
    ) as err:
        logger.error(f"Failed to log in for user {user_id}: {err}")
        return None

def store_garmin_credentials(user_id: str, email: str, encrypted_password: str):
    """
    Stores encrypted Garmin credentials for a user.
    """
    supabase.table("users").update({
        "garmin_email": email,
        "garmin_password": encrypted_password,
    }).eq("id", user_id).execute()
    logger.info(f"Stored Garmin credentials for user {user_id}.")

def log_to_file(msg):
    try:
        with open("sync_debug.log", "a") as f:
            f.write(f"{datetime.now().isoformat()} - {msg}\n")
    except:
        pass

def sync_all_garmin_data_for_user(user_id: str, days_back: int = 7, encryption_key: str = None):
    """
    Synchronizes all relevant Garmin data for a specific user.
    """
    log_to_file(f"Starting sync for user {user_id}")
    garmin_api = init_garmin_api_for_user(user_id, encryption_key)
    if not garmin_api:
        log_to_file(f"Garmin session not available for user {user_id}, skipping.")
        logger.error(f"Garmin session not available for user {user_id}, skipping.")
        return

    # Determine sync window
    user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
    last_synced = None
    user_goals = {}
    if user_response.data:
        user_goals = user_response.data[0].get("goals") or {}
        if user_goals.get("garmin_last_synced"):
            try:
                last_synced = datetime.fromisoformat(user_goals["garmin_last_synced"]).date()
            except ValueError:
                pass

    end_date = date.today()
    if last_synced:
        # Sync from last synced date up to today, BUT go back 3 days to catch late syncs/backfills
        start_date = last_synced - timedelta(days=3)
        log_to_file(f"Incremental sync for user {user_id} from {start_date} (overlap 3 days) to {end_date}")
        logger.info(f"Incremental sync for user {user_id} from {start_date} (overlap 3 days) to {end_date}")
    else:
        # Initial sync: 1 year back
        start_date = end_date - timedelta(days=365)
        log_to_file(f"Initial sync for user {user_id} (last 365 days)")
        logger.info(f"Initial sync for user {user_id} (last 365 days)")

    # 1) Activities (Workouts)
    try:
        log_to_file("Fetching activities...")
        raw_activities = garmin_api.get_activities_by_date(
            start_date.isoformat(), end_date.isoformat()
        )
        log_to_file(f"Fetched {len(raw_activities)} activities for user {user_id}.")
        logger.info(f"Fetched {len(raw_activities)} activities for user {user_id}.")

        # Avoid duplicates
        existing_ids = set()
        res = supabase.table("garmin_activities").select("activity_id").eq("user_id", user_id).execute()
        if res.data:
            existing_ids = {item["activity_id"] for item in res.data}

        new_activities_count = 0
        batch_activities = []
        
        # Process activities
        for act in raw_activities:
            activity_id = str(act["activityId"])
            
            # Fetch detailed streams (HR, Elevation, etc.)
            activity_details = {}
            try:
                activity_details = garmin_api.get_activity_details(activity_id)
            except Exception as e:
                log_to_file(f"Could not fetch details for activity {activity_id}: {e}")
                logger.warning(f"Could not fetch details for activity {activity_id}: {e}")

            doc = {
                "user_id": user_id,
                "activity_id": activity_id,
                "activity_name": act.get("activityName"),
                "start_time_local": act.get("startTimeLocal"),
                "distance": act.get("distance"),
                "duration": act.get("duration"),
                "calories": act.get("calories"),
                "activity_type": act.get("activityType", {}).get("typeKey"),
                "raw_data": act, 
                "details": activity_details, # Store detailed streams/metrics
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            batch_activities.append(doc)
            new_activities_count += 1
        
        if batch_activities:
            # Upsert activities
            log_to_file(f"Upserting {len(batch_activities)} activities...")
            supabase.table("garmin_activities").upsert(batch_activities, on_conflict="activity_id").execute()

        log_to_file(f"Upserted {new_activities_count} activities for user {user_id}.")
        logger.info(f"Upserted {new_activities_count} activities for user {user_id}.")
        
        # Update last_synced_at in goals
        user_goals["garmin_last_synced"] = datetime.now(timezone.utc).isoformat()
        supabase.table("users").update({
            "goals": user_goals
        }).eq("id", user_id).execute()
        log_to_file("Updated garmin_last_synced in goals.")

    except Exception as e:
        log_to_file(f"Error fetching activities for user {user_id}: {e}")
        logger.error(f"Error fetching activities for user {user_id}: {e}")

    # 2) Daily Data (Day-by-day loop)
    current_day = start_date
    while current_day <= end_date:
        day_str = current_day.isoformat()
        log_to_file(f"Fetching daily data for {day_str}...")
        logger.info(f"Fetching daily data for {day_str} (user {user_id})...")

        try:
            # Steps
            steps_data = garmin_api.get_steps_data(day_str)
            # Heart Rate (daily avg/min if available)
            hr_data = garmin_api.get_heart_rates(day_str)
            # Stress
            stress_data = garmin_api.get_stress_data(day_str)
            # Respiration
            respiration_data = garmin_api.get_respiration_data(day_str)
            # SpO2
            spo2_data = garmin_api.get_spo2_data(day_str)
            # Resting HR
            rhr_data = garmin_api.get_rhr_day(day_str)  # If library supports it daily
            # Sleep
            sleep_data = garmin_api.get_sleep_data(day_str)
            # Floors
            floors_data = garmin_api.get_floors(day_str)

            # Insert daily doc
            daily_doc = {
                "user_id": user_id,
                "date": day_str,
                "steps": steps_data,
                "heartrate": hr_data,
                "stress": stress_data,
                "respiration": respiration_data,
                "spo2": spo2_data,
                "resting_hr": rhr_data,
                "floors": floors_data,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            # Upsert logic: delete existing for date then insert, or just insert (assuming unique constraint)
            # Supabase upsert requires primary key or unique constraint.
            # Let's try upsert if we have a unique constraint on (user_id, date)
            supabase.table("garmin_daily").upsert(daily_doc, on_conflict="user_id, date").execute()

            # Sleep
            if sleep_data:
                sleep_doc = {
                    "user_id": user_id,
                    "date": day_str,
                    "sleep_data": sleep_data,
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }
                supabase.table("garmin_sleep").upsert(sleep_doc, on_conflict="user_id, date").execute()

        except Exception as ex:
            log_to_file(f"Error fetching daily data for {day_str}, user {user_id}: {ex}")
            logger.error(f"Error fetching daily data for {day_str}, user {user_id}: {ex}")

        current_day += timedelta(days=1)

    # 3) Additional Endpoints: Body Battery, Max Metrics, HRV
    try:
        # Max metrics (like VO2 Max or fitnessAge) for the final day or each day
        last_day_str = end_date.isoformat()
        max_metrics = garmin_api.get_max_metrics(last_day_str)
        if max_metrics:
            doc = {
                "user_id": user_id,
                "date": last_day_str,
                "max_metrics": max_metrics,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            supabase.table("garmin_maxmetrics").upsert(doc, on_conflict="user_id, date").execute()

    except Exception as e:
        log_to_file(f"Error fetching body battery / max metrics / HRV for user {user_id}: {e}")
        logger.error(f"Error fetching body battery / max metrics / HRV for user {user_id}: {e}")

    log_to_file(f"Finished syncing Garmin data for user {user_id}.")
    logger.info(f"Finished syncing Garmin data for user {user_id}.")