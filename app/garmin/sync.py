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

def robust_api_call(func, *args, retries=3, **kwargs):
    """
    Helper to execute Garmin API calls with strict retries for SSL/Connection errors.
    """
    last_exception = None
    import time
    
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            last_exception = e
            logger.warning(f"Network error in Garmin API call (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(1 * (attempt + 1)) # Backoff
        except Exception as e:
            # For other errors (e.g. Auth), fail fast or check type
            raise e
            
    if last_exception:
        raise last_exception


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

def update_progress(user_id: str, progress: int):
    """
    Updates the sync progress in the user's 'goals' JSONB column.
    This avoids the need for a schema migration.
    """
    try:
        # Fetch current goals first to preserve other data
        res = supabase.table("users").select("goals").eq("id", user_id).execute()
        if res.data:
            goals = res.data[0].get("goals") or {}
            goals["sync_progress"] = progress
            supabase.table("users").update({"goals": goals}).eq("id", user_id).execute()
    except Exception as e:
        logger.warning(f"Failed to update sync progress in goals: {e}")

def sync_all_garmin_data_for_user(user_id: str, days_back: int = 7, encryption_key: str = None, force_resync: bool = False):
    """
    Unified Sync Logic:
    - Automatically detects Initial vs. Incremental mode.
    - Handles fetching activities and daily health data.
    - Updates progress via 'goals' JSON.
    - Triggers analytics at the end.
    """
    log_to_file(f"Starting unified sync for user {user_id} (Force Resync: {force_resync})")
    
    try:
        # 1. Initialization and Mode Detection
        user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
        user_goals = {}
        last_synced = None
        
        if user_response.data:
            user_goals = user_response.data[0].get("goals") or {}
            if user_goals.get("garmin_last_synced"):
                try:
                    last_synced = datetime.fromisoformat(user_goals["garmin_last_synced"]).date()
                except ValueError:
                    pass

        # Reset Progress to 0% and Status to syncing
        user_goals["sync_progress"] = 0
        supabase.table("users").update({
            "garmin_sync_status": "syncing",
            "garmin_sync_started_at": datetime.now(timezone.utc).isoformat(),
            "goals": user_goals
        }).eq("id", user_id).execute()

        garmin_api = init_garmin_api_for_user(user_id, encryption_key)
        if not garmin_api:
            log_to_file(f"Garmin session not available for user {user_id}, skipping.")
            supabase.table("users").update({
                "garmin_sync_status": "error",
                "garmin_last_sync_error": "Failed to initialize Garmin API session. Please reconnect."
            }).eq("id", user_id).execute()
            return
            
        update_progress(user_id, 5) # 5% - Login Complete

        # 2. Determine Scope
        end_date = date.today()
        start_date = None
        daily_start_date = None
        is_initial_sync = False

        if last_synced and not force_resync:
            # Incremental Sync
            is_initial_sync = False
            start_date = last_synced - timedelta(days=3) # Overlap for safety
            daily_start_date = start_date
            log_to_file(f"Incremental Sync detected. Fetching from {start_date} to {end_date}")
        else:
            # Initial Sync OR Forced Resync
            is_initial_sync = True
            start_date = end_date - timedelta(days=1825) # 5 Years for activities
            daily_start_date = end_date - timedelta(days=30) # 30 Days for daily data (heavy)
            log_to_file(f"Initial/Forced Sync detected. Activities: 5y, Daily: 30d (from {daily_start_date})")

        # 3. Process Activities
        update_progress(user_id, 10) # 10% - Starting Activities
        try:
            log_to_file(f"Fetching activities from {start_date}...")
            
            # Robust Pagination Loop
            raw_activities = []
            start_idx = 0
            limit = 100
            
            while True:
                # Fetch batch
                log_to_file(f"Fetching batch start={start_idx} limit={limit}...")
                # Fetch batch with retry
                log_to_file(f"Fetching batch start={start_idx} limit={limit}...")
                try:
                    batch = robust_api_call(garmin_api.get_activities, start_idx, limit)
                except Exception as e:
                    log_to_file(f"Failed to fetch batch at {start_idx}: {e}")
                    # If batch fails, we can assume we might have issues. 
                    # Try to continue? Or break? 
                    # If robust call failed after retries, we likely can't proceed with this chain.
                    break
                
                if not batch:
                    break
                
                valid_batch = []
                stop_fetching = False
                
                for act in batch:
                    # Check date
                    act_date_str = act.get("startTimeLocal")
                    if not act_date_str: continue
                    
                    act_date = datetime.fromisoformat(act_date_str).date()
                    
                    if act_date >= start_date:
                        if act_date <= end_date:
                            valid_batch.append(act)
                    else:
                        # Found an activity older than start_date. 
                        # Since get_activities returns newest first, we can likely stop.
                        stop_fetching = True
                        # Don't break immediately, potential disorder? Garmin is usually ordered.
                        # But to be safe, if we are way past (e.g. 7 days past), stop.
                        if act_date < (start_date - timedelta(days=7)):
                             stop_fetching = True
                             
                raw_activities.extend(valid_batch)
                start_idx += limit
                
                if stop_fetching or len(batch) < limit:
                    break
                    
            total_activities = len(raw_activities)
            log_to_file(f"Fetched {total_activities} activities.")
            
            # Optimization: Update daily_start_date if we found older activities during initial sync
            # to ensure we don't fetch daily data for years with no activities
            if is_initial_sync and raw_activities:
                # Sort oldest first to check start date
                sorted_acts = sorted(raw_activities, key=lambda x: x.get("startTimeLocal", "9999"))
                oldest_act_str = sorted_acts[0].get("startTimeLocal")
                if oldest_act_str:
                    oldest_date = datetime.fromisoformat(oldest_act_str).date()
                    # If the oldest activity is newer than our heavy fetch limit (30d), 
                    # we can technically start fetching daily data earlier, 
                    # BUT for initial sync we strictly limit daily data to 30 days to avoid timeouts.
                    # So we only Adjust if the user literally JUST joined Garmin fewer than 30 days ago.
                    if oldest_date > daily_start_date:
                        daily_start_date = oldest_date
                        log_to_file(f"Adjusted daily sync start to {daily_start_date} (User joined recently)")

            batch_activities = []
            
            for i, act in enumerate(raw_activities):
                activity_id = str(act["activityId"])
                
                # DETAILS STRATEGY: 
                # Incremental: Fetch details for ALL (since it's small).
                # Initial: Fetch details ONLY for top 50 (recent).
                fetch_details = not is_initial_sync or (i < 50)
                
                activity_details = {}
                if fetch_details:
                    # Retry logic for SSL/Connection errors
                    for attempt in range(2):
                        try:
                            activity_details = garmin_api.get_activity_details(activity_id)
                            break # Success
                        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                            logger.warning(f"Network error fetching details for {activity_id} (Attempt {attempt+1}/2): {e}")
                            if attempt == 1:
                                log_to_file(f"Skipping details for {activity_id} after 2 retries due to SSL/Network error.")
                        except Exception as e:
                            logger.warning(f"Failed to get details for {activity_id}: {e}")
                            break # Don't retry other errors

                doc = {
                    "user_id": user_id,
                    "activity_id": activity_id,
                    "activity_name": act.get("activityName"),
                    "start_time_local": act.get("startTimeLocal"),
                    "distance": act.get("distance"),
                    "duration": act.get("duration"),
                    "calories": act.get("calories"),
                    "activity_type": act.get("activityType", {}).get("typeKey"),
                    "average_hr": act.get("averageHR"),
                    "max_hr": act.get("maxHR"),
                    "elevation_gain": act.get("elevationGain"),
                    "average_speed": act.get("averageSpeed"),
                    "max_speed": act.get("maxSpeed"),
                    "raw_data": act, 
                    "details": activity_details,
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }
                batch_activities.append(doc)

                # Progress Update (10% -> 50%)
                if total_activities > 0 and i % 5 == 0:
                    pct = 10 + int((i / total_activities) * 40)
                    update_progress(user_id, pct)

                if len(batch_activities) >= 20:
                    supabase.table("garmin_activities").upsert(batch_activities, on_conflict="activity_id").execute()
                    batch_activities = []
            
            if batch_activities:
                supabase.table("garmin_activities").upsert(batch_activities, on_conflict="activity_id").execute()

        except Exception as e:
            log_to_file(f"Error processing activities: {e}")
            # Continue to daily data even if activities fail partial

        # 4. Process Daily Data
        update_progress(user_id, 50) # 50% - Starting Daily Data
        
        # Optimization: Fetch existing dates to skip unnecessary API calls
        existing_dates_set = set()
        try:
            ex_res = supabase.table("garmin_daily").select("date").eq("user_id", user_id).gte("date", daily_start_date.isoformat()).execute()
            existing_dates_set = {r["date"] for r in ex_res.data}
        except:
            pass

        current_day = daily_start_date
        total_days = (end_date - daily_start_date).days + 1
        days_processed = 0
        
        daily_batch = []
        sleep_batch = []

        while current_day <= end_date:
            day_str = current_day.isoformat()
            
            # Progress (50% -> 90%)
            if total_days > 0 and days_processed % 3 == 0:
                pct = 50 + int((days_processed / total_days) * 40)
                update_progress(user_id, pct)
            
            days_processed += 1

            # Skip if already exists AND we are in initial sync mode (speed up).
            # For incremental, we overwrite to ensure freshness.
            if is_initial_sync and day_str in existing_dates_set:
                current_day += timedelta(days=1)
                continue

            try:
                log_to_file(f"Fetching daily: {day_str}")
                # Fetch minimal set first to fail fast? No, just fetch.
                log_to_file(f"Fetching daily: {day_str}")
                # Fetch minimal set first to fail fast? No, just fetch.
                # Wrap in robust calls
                steps = robust_api_call(garmin_api.get_steps_data, day_str)
                sleep = robust_api_call(garmin_api.get_sleep_data, day_str)
                hr = robust_api_call(garmin_api.get_heart_rates, day_str)
                # Helper data extraction
                rhr_raw = robust_api_call(garmin_api.get_rhr_day, day_str)
                stress_raw = robust_api_call(garmin_api.get_stress_data, day_str)

                # Normalize RHR (Extract scalar from heavy JSON)
                rhr_val = None
                try:
                    if isinstance(rhr_raw, dict):
                         # Path: allMetrics -> metricsMap -> WELLNESS_RESTING_HEART_RATE -> [0] -> value
                         mmap = rhr_raw.get('allMetrics', {}).get('metricsMap', {})
                         vals = mmap.get('WELLNESS_RESTING_HEART_RATE', [])
                         if vals and isinstance(vals, list):
                             rhr_val = vals[0].get('value')
                    elif isinstance(rhr_raw, (int, float)):
                        rhr_val = rhr_raw
                except:
                    pass

                # Normalize Stress
                stress_val = None
                try:
                    if isinstance(stress_raw, dict):
                        stress_val = stress_raw.get('avgStressLevel')
                    elif isinstance(stress_raw, (int, float)):
                        stress_val = stress_raw
                except:
                    pass

                daily_doc = {
                    "user_id": user_id,
                    "date": day_str,
                    "steps": steps,
                    "heartrate": hr,
                    "resting_hr": rhr_val, # Cleaned
                    "stress": stress_val,  # Cleaned
                    "synced_at": datetime.now(timezone.utc).isoformat()
                }
                daily_batch.append(daily_doc)

                if sleep:
                    sleep_doc = {
                        "user_id": user_id,
                        "date": day_str,
                        "sleep_data": sleep,
                        "synced_at": datetime.now(timezone.utc).isoformat()
                    }
                    sleep_batch.append(sleep_doc)

            except Exception as e:
                log_to_file(f"Failed daily {day_str}: {e}")
            
            current_day += timedelta(days=1)

            # Upsert batches of 7 (weekly)
            if len(daily_batch) >= 7:
                supabase.table("garmin_daily").upsert(daily_batch, on_conflict="user_id, date").execute()
                daily_batch = []
            if len(sleep_batch) >= 7:
                supabase.table("garmin_sleep").upsert(sleep_batch, on_conflict="user_id, date").execute()
                sleep_batch = []

        # Final flush
        if daily_batch:
            supabase.table("garmin_daily").upsert(daily_batch, on_conflict="user_id, date").execute()
        if sleep_batch:
            supabase.table("garmin_sleep").upsert(sleep_batch, on_conflict="user_id, date").execute()

        # 5. Finalize and Analytics
        update_progress(user_id, 90) # 90% - Data Sync Complete
        
        # Max metrics for today/latest
        try:
             max_m = garmin_api.get_max_metrics(end_date.isoformat())
             if max_m:
                 supabase.table("garmin_maxmetrics").upsert({
                     "user_id": user_id, "date": end_date.isoformat(), "max_metrics": max_m
                 }, on_conflict="user_id, date").execute()
        except:
            pass

        # Update Last Synced
        # Re-fetch goals to avoid overwriting race conditions (though low risk here)
        user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
        if user_response.data:
            goals = user_response.data[0].get("goals") or {}
            goals["garmin_last_synced"] = datetime.now(timezone.utc).isoformat()
            goals["sync_progress"] = 95
            supabase.table("users").update({"goals": goals}).eq("id", user_id).execute()

        # Trigger Analytics
        update_progress(user_id, 95)
        try:
            from app.analytics.analytics_service import AnalyticsService
            AnalyticsService.calculate_baselines(user_id)
        except Exception as e:
            log_to_file(f"Analytics failed: {e}")

        # Complete
        update_progress(user_id, 100)
        supabase.table("users").update({
            "garmin_sync_status": "synced",
            "garmin_sync_completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        log_to_file("Sync Complete.")

    except Exception as e:
        log_to_file(f"CRITICAL SYNC ERROR: {e}")
        supabase.table("users").update({
            "garmin_sync_status": "error",
            "garmin_last_sync_error": str(e)
        }).eq("id", user_id).execute()