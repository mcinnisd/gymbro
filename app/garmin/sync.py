# app/garmin/sync.py

import logging
from datetime import datetime, timedelta, date, timezone, UTC
from bson import ObjectId
from flask import current_app

import requests
from garth.exc import GarthHTTPError
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from app.utils.encryption import encrypt_data, decrypt_data  # Import encryption functions

logger = logging.getLogger(__name__)

def init_garmin_api_for_user(user_id: str):
    """
    Initializes Garmin API session for a specific user by decrypting stored credentials.
    """
    user_doc = current_app.mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        logger.error(f"No user found with user_id={user_id}")
        return None

    garmin_email = user_doc.get("garmin_email")
    encrypted_password = user_doc.get("garmin_password")
    if not garmin_email or not encrypted_password:
        logger.error(f"User {user_id} does not have Garmin credentials stored.")
        return None

    try:
        # Decrypt the password
        garmin_password = decrypt_data(encrypted_password)
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
    current_app.mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "garmin_email": email,
                "garmin_password": encrypted_password,
            }
        },
        upsert=True
    )
    logger.info(f"Stored Garmin credentials for user {user_id}.")

def sync_all_garmin_data_for_user(user_id: str, days_back: int = 7):
    """
    Synchronizes all relevant Garmin data for a specific user.
    """
    garmin_api = init_garmin_api_for_user(user_id)
    if not garmin_api:
        logger.error(f"Garmin session not available for user {user_id}, skipping.")
        return

    logger.info(f"Syncing Garmin data for user {user_id}, last {days_back} days...")

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # 1) Activities (Workouts)
    try:
        raw_activities = garmin_api.get_activities_by_date(
            start_date.isoformat(), end_date.isoformat()
        )
        logger.info(f"Fetched {len(raw_activities)} activities for user {user_id}.")

        # Avoid duplicates
        existing_ids = set(
            doc["activity_id"]
            for doc in current_app.mongo.db.garmin_activities.find({"user_id": user_id}, {"activity_id": 1, "_id": 0})
        )

        new_activities_count = 0
        for act in raw_activities:
            activity_id = str(act["activityId"])
            if activity_id in existing_ids:
                continue

            doc = {
                "user_id": user_id,
                "activity_id": activity_id,
                "activity_name": act.get("activityName"),
                "start_time_local": act.get("startTimeLocal"),
                "distance": act.get("distance"),
                "duration": act.get("duration"),
                "calories": act.get("calories"),
                "activity_type": act.get("activityType", {}).get("typeKey"),
                "raw_data": act,  # full record
                "synced_at": datetime.now(UTC),
            }
            current_app.mongo.db.garmin_activities.insert_one(doc)
            existing_ids.add(activity_id)
            new_activities_count += 1

        logger.info(f"Inserted {new_activities_count} new activities for user {user_id}.")

    except Exception as e:
        logger.error(f"Error fetching activities for user {user_id}: {e}")

    # 2) Daily Data (Day-by-day loop)
    current_day = start_date
    while current_day <= end_date:
        day_str = current_day.isoformat()
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
                "synced_at": datetime.now(UTC),
            }
            current_app.mongo.db.garmin_daily.insert_one(daily_doc)

            # Sleep
            if sleep_data:
                sleep_doc = {
                    "user_id": user_id,
                    "date": day_str,
                    "sleep_data": sleep_data,
                    "synced_at": datetime.now(UTC),
                }
                current_app.mongo.db.garmin_sleep.insert_one(sleep_doc)

        except Exception as ex:
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
                "synced_at": datetime.now(UTC),
            }
            current_app.mongo.db.garmin_maxmetrics.insert_one(doc)

    except Exception as e:
        logger.error(f"Error fetching body battery / max metrics / HRV for user {user_id}: {e}")

    logger.info(f"Finished syncing Garmin data for user {user_id}.")