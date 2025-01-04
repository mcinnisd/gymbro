import os
import logging
from datetime import datetime, timedelta, date, timezone, UTC
from pymongo import MongoClient

import requests
from garth.exc import GarthHTTPError
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# MongoDB Setup
# -------------------------------------------------------------------------
client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["gymbro_db"]
users_collection = db["users"]

# Collections (split into categories)
garmin_activities = db["garmin_activities"]    # Workouts
garmin_daily = db["garmin_daily"]              # Steps, stress, respiration, etc.
garmin_sleep = db["garmin_sleep"]              # Sleep info
garmin_floors = db["garmin_floors"]            # Floors climbed
garmin_battery = db["garmin_battery"]          # Body battery
garmin_maxmetrics = db["garmin_maxmetrics"]    # VO2max / fitnessAge
garmin_hrv = db["garmin_hrv"]                  # HRV


# -------------------------------------------------------------------------
# Utility: Initialize Garmin API session for a specific user
# -------------------------------------------------------------------------
def init_garmin_api_for_user(user_id: str):
    """
    1) Looks up the user's Garmin credentials in Mongo.
    2) Logs in to Garmin with those credentials.
    3) Returns a Garmin() session object.
    """
    user_doc = users_collection.find_one({"user_id": user_id})
    if not user_doc:
        logger.error(f"No user found with user_id={user_id}")
        return None

    garmin_email = user_doc.get("garmin_email")
    garmin_password = user_doc.get("garmin_password")
    if not garmin_email or not garmin_password:
        logger.error(f"User {user_id} does not have Garmin credentials stored.")
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


# -------------------------------------------------------------------------
# Storing Garmin credentials in the DB
# -------------------------------------------------------------------------
def store_garmin_credentials(user_id: str, email: str, password: str):
    """
    Example helper to store raw email/password for a user.
    In production, DO NOT store plain text – use encryption or token-based approach.
    """
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "garmin_email": email,
                "garmin_password": password,
            }
        },
        upsert=True
    )
    logger.info(f"Stored Garmin credentials for user {user_id}.")


# -------------------------------------------------------------------------
# Sync the relevant Garmin data for a Single User
# -------------------------------------------------------------------------
def sync_all_garmin_data_for_user(user_id: str, days_back: int = 7):
    """
    Fetches:
      1) Activity Data (Workouts)
      2) Daily Data (steps, heart rate, floors, respiration, stress, etc.)
      3) Additional calls: resting heart rate, body battery, max metrics, HRV data
    and stores them into various collections.

    Adjust or comment out items not needed yet.
    """
    garmin_api = init_garmin_api_for_user(user_id)
    if not garmin_api:
        logger.error(f"Garmin session not available for {user_id}, skipping.")
        return

    logger.info(f"Syncing Garmin data for user {user_id}, last {days_back} days...")

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 1) Activities (Workouts)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    try:
        raw_activities = garmin_api.get_activities_by_date(
            start_date.isoformat(), end_date.isoformat()
        )
        logger.info(f"Fetched {len(raw_activities)} activities for {user_id}.")

        # Avoid duplicates
        existing_ids = set(
            doc["activity_id"]
            for doc in garmin_activities.find({"user_id": user_id}, {"activity_id": 1, "_id": 0})
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
            garmin_activities.insert_one(doc)
            existing_ids.add(activity_id)
            new_activities_count += 1

        logger.info(f"Inserted {new_activities_count} new activities for {user_id}.")

    except Exception as e:
        logger.error(f"Error fetching activities for user {user_id}: {e}")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 2) Daily Data (Day-by-day loop)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
            # Resting HR might be separate
            rhr_data = garmin_api.get_rhr_day(day_str)  # If library supports it daily
            # # Body composition
            # body_comp = garmin_api.get_body_composition(day_str)
            # Sleep
            sleep_data = garmin_api.get_sleep_data(day_str)
            # Floors
            floors_data = garmin_api.get_floors(day_str)
            # Body Battery (some calls do a range; might do daily if needed)
            # e.g. garmin_api.get_body_battery_events(day_str) or get_body_battery(start, end)

            # Insert daily doc: many devs store it all in one “daily” doc
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
            garmin_daily.insert_one(daily_doc)

            # Sleep
            if sleep_data:
                sleep_doc = {
                    "user_id": user_id,
                    "date": day_str,
                    "sleep_data": sleep_data,
                    "synced_at": datetime.now(UTC),
                }
                garmin_sleep.insert_one(sleep_doc)

        except Exception as ex:
            logger.error(f"Error fetching daily data for {day_str}, user {user_id}: {ex}")

        current_day += timedelta(days=1)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3) Additional Endpoints: Body Battery, Max Metrics, HRV
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    try:
        # Body battery for entire range
        # e.g. garmin_api.get_body_battery(start_date.isoformat(), end_date.isoformat())
        # if your version of the lib has that method
        # battery_data = garmin_api.get_body_battery(start_date.isoformat(), end_date.isoformat())
        # if battery_data:
        #     doc = {
        #         "user_id": user_id,
        #         "range_start": start_date.isoformat(),
        #         "range_end": end_date.isoformat(),
        #         "body_battery_data": battery_data,
        #         "synced_at": datetime.now(UTC),
        #     }
        #     garmin_battery.insert_one(doc)

        # Max metrics (like VO2 Max or fitnessAge) for the final day or each day
        # e.g. garmin_api.get_max_metrics(day_str)
        last_day_str = end_date.isoformat()
        max_metrics = garmin_api.get_max_metrics(last_day_str)
        if max_metrics:
            doc = {
                "user_id": user_id,
                "date": last_day_str,
                "max_metrics": max_metrics,
                "synced_at": datetime.now(UTC),
            }
            garmin_maxmetrics.insert_one(doc)

        # HRV
        # hrv_data = garmin_api.get_hrv_data(end_date.isoformat())
        # if hrv_data:
        #     doc = {
        #         "user_id": user_id,
        #         "date": end_date.isoformat(),
        #         "hrv_data": hrv_data,
        #         "synced_at": datetime.now(UTC),
        #     }
        #     garmin_hrv.insert_one(doc)

    except Exception as e:
        logger.error(f"Error fetching body battery / max metrics / HRV: {e}")

    logger.info(f"Finished syncing Garmin data for user {user_id}.")


# -------------------------------------------------------------------------
# Example: Direct Run
# -------------------------------------------------------------------------
if __name__ == "__main__":
    """
    For testing:
    1) Insert user credentials:
       store_garmin_credentials("alice", "alice_garmin@example.com", "pass123")
    2) Run:
       python garmin_sync.py
    3) It calls sync_all_garmin_data_for_user("alice", days_back=7).
    """
    TEST_USER_ID = "mcinnisd"
    DAYS_BACK = 7

    # Uncomment to store credentials
    store_garmin_credentials(TEST_USER_ID, "mcinnisd@umich.edu", "duzkew0Togzumigzys")

    sync_all_garmin_data_for_user(TEST_USER_ID, days_back=DAYS_BACK)