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
from app.garmin.biometrics_mirror import upsert_biometrics_daily
from app.garmin.scope import normalize_garmin_user_id

logger = logging.getLogger(__name__)

GARMIN_ACTIVITIES_ON_CONFLICT = "user_id,activity_id"

def robust_api_call(func, *args, retries=3, backoff_base=1.5, **kwargs):
    """
    Helper to execute Garmin API calls with retries and exponential backoff for
    SSL/Connection, 429 Rate Limit, or transient Garth HTTP errors.
    """
    last_exception = None
    import time
    
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, GarminConnectConnectionError) as e:
            last_exception = e
            logger.warning(f"Network error in Garmin API call (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(1 * (attempt + 1))
        except (GarminConnectTooManyRequestsError, GarthHTTPError) as e:
            last_exception = e
            sleep_sec = (backoff_base ** attempt) * 2
            logger.warning(f"Rate limit / HTTP error in Garmin API call ({func.__name__}, Attempt {attempt+1}/{retries}): {e}. Backing off for {sleep_sec:.1f}s")
            time.sleep(sleep_sec)
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "rate limit" in err_msg or "too many requests" in err_msg:
                last_exception = e
                sleep_sec = (backoff_base ** attempt) * 2
                logger.warning(f"Rate limit in Garmin API call ({func.__name__}, Attempt {attempt+1}/{retries}): {e}. Sleeping {sleep_sec:.1f}s")
                time.sleep(sleep_sec)
            else:
                logger.warning(f"Garmin API call non-retryable error in {func.__name__}: {e}")
                return None
            
    if last_exception:
        logger.warning(f"Garmin API call exhausted retries: {func.__name__} ({last_exception})")
        return None
    return None

def generate_monthly_chunks(start_date: date, end_date: date, chunk_size_days: int = 30):
    """
    Slices a date range [start_date, end_date] into reverse-chronological chunks of size chunk_size_days.
    Returns list of (chunk_start, chunk_end) tuples.
    """
    if start_date > end_date:
        return []
    chunks = []
    current_end = end_date
    while current_end >= start_date:
        current_start = max(start_date, current_end - timedelta(days=chunk_size_days - 1))
        chunks.append((current_start, current_end))
        current_end = current_start - timedelta(days=1)
    return chunks



def safe_garmin_call(api, method_name, *args):
    """
    Safely invokes a GarminConnect method if available, handling missing methods or exceptions gracefully.
    """
    if not hasattr(api, method_name):
        return None
    try:
        method = getattr(api, method_name)
        return robust_api_call(method, *args)
    except Exception as e:
        logger.debug(f"Garmin API call {method_name} failed: {e}")
        return None



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

# Cached after the first 42703 / successful metrics write.
_TRAINING_EVENTS_HAS_METRICS = None


def reset_training_events_metrics_column_cache(value=None):
    """Test helper: None = unknown, True/False = force include/omit metrics."""
    global _TRAINING_EVENTS_HAS_METRICS
    _TRAINING_EVENTS_HAS_METRICS = value


def _without_metrics(row: dict) -> dict:
    from app.calendar.constraints import strip_metrics_column
    return strip_metrics_column(row)


def _is_missing_metrics_column(exc: BaseException) -> bool:
    from app.calendar.constraints import is_undefined_column_error
    return is_undefined_column_error(exc, "metrics")


def _upsert_training_events(batch: list) -> None:
    """Upsert calendar rows, omitting metrics when live Postgres lacks the column."""
    global _TRAINING_EVENTS_HAS_METRICS
    if not batch:
        return
    from app.calendar.constraints import map_activity_type_to_event_type

    payload = [
        {**row, "event_type": map_activity_type_to_event_type(row.get("event_type"))}
        for row in batch
    ]
    if _TRAINING_EVENTS_HAS_METRICS is False:
        payload = [_without_metrics(row) for row in payload]
    try:
        supabase.table("training_events").upsert(payload).execute()
        if _TRAINING_EVENTS_HAS_METRICS is None and any("metrics" in row for row in payload):
            _TRAINING_EVENTS_HAS_METRICS = True
        return
    except Exception as exc:
        if _TRAINING_EVENTS_HAS_METRICS is not False and _is_missing_metrics_column(exc):
            _TRAINING_EVENTS_HAS_METRICS = False
            logger.warning(
                "training_events.metrics is missing (42703); remirror continues without that column. "
                "Apply migrations/20260916_training_events_metrics.sql when convenient."
            )
            supabase.table("training_events").upsert(
                [_without_metrics(row) for row in payload]
            ).execute()
            return
        raise


def upsert_garmin_activities(user_id, batch: list) -> None:
    """
    Write garmin_activities for one athlete without stealing another user's rows.

    Conflict target is (user_id, activity_id). A global UNIQUE(activity_id) used
    to reassign Santa Monica workouts from user 2 onto user 100.
    """
    if not supabase or not batch:
        return
    uid = normalize_garmin_user_id(user_id)
    payload = []
    for doc in batch:
        row = dict(doc)
        row["user_id"] = uid
        row["activity_id"] = str(row.get("activity_id") or "")
        payload.append(row)
    try:
        supabase.table("garmin_activities").upsert(
            payload, on_conflict=GARMIN_ACTIVITIES_ON_CONFLICT
        ).execute()
        return
    except Exception as exc:
        logger.warning(
            "garmin_activities upsert on (user_id, activity_id) failed (%s); "
            "trying legacy on_conflict=activity_id. Apply "
            "migrations/20260916_garmin_activities_user_scoped.sql.",
            exc,
        )
    supabase.table("garmin_activities").upsert(payload, on_conflict="activity_id").execute()


def _garmin_calendar_existing_keys(user_id):
    """Return (activity_ids, date+title pairs) already mirrored as created_by=garmin."""
    from app.calendar.constraints import parse_garmin_activity_id_from_row

    uid = int(user_id) if str(user_id).isdigit() else user_id
    # Do not select metrics: live Postgres 42703s if the column is undeployed.
    res = (
        supabase.table("training_events")
        .select("date,title,description")
        .eq("user_id", uid)
        .eq("created_by", "garmin")
        .execute()
    )
    activity_ids = set()
    date_titles = set()
    for row in res.data or []:
        aid = parse_garmin_activity_id_from_row(row)
        if aid:
            activity_ids.add(str(aid))
        date_titles.add((str(row.get("date") or "")[:10], row.get("title")))
    return activity_ids, date_titles


def _sync_activities_to_calendar(user_id: str, activities: list):
    """
    Populates Garmin activities into the training_events table for calendar strip display.
    created_by is 'garmin' (allowed by training_events_created_by_check).
    event_type is mapped onto the calendar enum (running → run, etc.).
    Skips rows already mirrored so a remirror after a failed CHECK is idempotent.
    """
    if not supabase or not activities:
        return {"inserted": 0, "skipped": 0}
    try:
        from app.calendar.constraints import (
            assert_training_event_row,
            calendar_event_from_garmin_activity,
            map_activity_type_to_event_type,
        )
        calendar_batch = []
        uid = int(user_id) if str(user_id).isdigit() else user_id
        existing_ids, existing_titles = _garmin_calendar_existing_keys(uid)
        skipped = 0
        for doc in activities:
            event = calendar_event_from_garmin_activity(uid, doc)
            if not event:
                skipped += 1
                continue
            event["event_type"] = map_activity_type_to_event_type(event.get("event_type"))
            aid = (event.get("metrics") or {}).get("garmin_activity_id")
            title_key = (event["date"], event["title"])
            event["event_type"] = map_activity_type_to_event_type(event.get("event_type"))
            already = (aid and str(aid) in existing_ids) or title_key in existing_titles
            if already:
                skipped += 1
                continue
            assert_training_event_row(event)
            calendar_batch.append(event)
            if aid:
                existing_ids.add(str(aid))
            existing_titles.add(title_key)
        if calendar_batch:
            _upsert_training_events(calendar_batch)
            logger.info(
                "Synced %s Garmin activities to training_events calendar for user %s (skipped %s)",
                len(calendar_batch),
                user_id,
                skipped,
            )
        return {"inserted": len(calendar_batch), "skipped": skipped}
    except Exception as e:
        logger.warning(f"Failed to sync Garmin activities to training_events calendar: {e}")
        return {"inserted": 0, "skipped": 0, "error": str(e)}


def remirror_garmin_calendar(user_id: str, page_size: int = 200) -> dict:
    """
    Write training_events from garmin_activities already in Supabase.

    Does not call Garmin Connect or decrypt passwords. Use this after
    training_events_created_by_check allows created_by=garmin, when an earlier
    sync stored activities but calendar upserts failed.
    """
    if not supabase:
        return {"user_id": str(user_id), "source": 0, "inserted": 0, "skipped": 0, "error": "supabase not configured"}

    uid = int(user_id) if str(user_id).isdigit() else user_id
    source = 0
    inserted = 0
    skipped = 0
    errors = []
    start = 0
    while True:
        end = start + page_size - 1
        query = supabase.table("garmin_activities").select("*").eq("user_id", uid)
        if hasattr(query, "range"):
            query = query.range(start, end)
        else:
            query = query.limit(page_size)
        page = query.execute().data or []
        if not page:
            break
        source += len(page)
        result = _sync_activities_to_calendar(str(uid), page) or {}
        inserted += int(result.get("inserted") or 0)
        skipped += int(result.get("skipped") or 0)
        if result.get("error"):
            errors.append(result["error"])
        if len(page) < page_size:
            break
        start += page_size

    out = {
        "user_id": str(user_id),
        "source": source,
        "inserted": inserted,
        "skipped": skipped,
    }
    if errors:
        out["error"] = errors[-1]
    return out

def discover_garmin_inception_date(garmin_api, batch_size: int = 100):
    """
    Discovers the earliest activity timestamp from Garmin Connect.
    Paginates backwards through activities to identify account inception date.
    Falls back to 5 years ago (1825 days) if no activities exist.
    """
    fallback_date = (datetime.now(timezone.utc) - timedelta(days=1825)).date()
    if not garmin_api:
        return fallback_date
    try:
        start = 0
        earliest_dt = None
        while True:
            acts = garmin_api.get_activities(start, batch_size)
            if not acts:
                break
            for act in acts:
                dt_str = act.get("startTimeLocal") or act.get("startTimeGMT")
                if dt_str:
                    try:
                        clean_str = dt_str.replace("Z", "").split("+")[0]
                        parsed_dt = datetime.fromisoformat(clean_str).date()
                        if earliest_dt is None or parsed_dt < earliest_dt:
                            earliest_dt = parsed_dt
                    except Exception:
                        pass
            if len(acts) < batch_size:
                break
            start += len(acts)
        return earliest_dt if earliest_dt else fallback_date
    except Exception as e:
        logger.warning(f"Failed to discover Garmin inception date, using fallback: {e}")
        return fallback_date



def update_progress(user_id: str, progress: int, stage: str = None, inception_date: str = None):
    """
    Updates the sync progress, active tier stage, and archive inception date in the user's goals and garmin_sync_progress.
    """
    try:
        res = supabase.table("users").select("goals").eq("id", user_id).execute()
        if res.data:
            goals = res.data[0].get("goals") or {}
            goals["sync_progress"] = progress
            if stage:
                goals["sync_stage"] = stage
            if inception_date:
                goals["archive_inception_date"] = inception_date
            
            update_payload = {
                "goals": goals,
                "garmin_sync_progress": progress
            }
            supabase.table("users").update(update_payload).eq("id", user_id).execute()
    except Exception as e:
        logger.warning(f"Failed to update sync progress: {e}")


def sync_all_garmin_data_for_user(user_id: str, days_back: int = 365, encryption_key: str = None, force_resync: bool = False, mode: str = "all_time"):
    """
    Unified Multi-Tier Sync Logic:
    - Automatically discovers athlete inception date for all-time deep backfills.
    - Coordinates 3-Tier State Machine:
        * Tier 1 (snapshot_30d): Recent 30 days biometrics + activities.
        * Tier 2 (deep_365d): 1-year longitudinal deep backfill (days 31-365).
        * Tier 3 (lifetime_archive): Multi-year history back to account inception.
    - Smart Delta date skipping to avoid redundant API hits.
    - Updates sync_stage, archive_inception_date, and progress in users.goals.
    """
    log_to_file(f"Starting unified sync for user {user_id} (Mode: {mode}, Force Resync: {force_resync}, Days Back: {days_back})")
    biometrics_failures = 0

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
        user_goals["sync_stage"] = "snapshot_30d"
        supabase.table("users").update({
            "garmin_sync_status": "syncing",
            "garmin_sync_progress": 0,
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
            
        update_progress(user_id, 5, stage="snapshot_30d") # 5% - Login Complete

        # Discover archive inception date
        inception_date = discover_garmin_inception_date(garmin_api)
        inception_str = inception_date.isoformat()
        log_to_file(f"Discovered Garmin inception date for user {user_id}: {inception_str}")
        update_progress(user_id, 8, stage="snapshot_30d", inception_date=inception_str)

        # 2. Determine Scope
        end_date = date.today()
        start_date = None
        daily_start_date = None
        is_initial_sync = False

        if mode == "incremental" or (last_synced and not force_resync and mode != "all_time"):
            # Incremental Sync
            is_initial_sync = False
            incremental_days = min(days_back, 7) if (days_back and days_back < 30) else 7
            start_date = max(last_synced - timedelta(days=3), end_date - timedelta(days=incremental_days)) # Overlap for safety
            daily_start_date = start_date
            log_to_file(f"Incremental Sync detected. Fetching from {start_date} to {end_date}")
        else:
            # Initial Sync OR Forced Resync OR Deep Historical Backfill
            is_initial_sync = True
            start_date = inception_date # Back to inception date for all activities
            if mode == "deep_365":
                daily_start_date = end_date - timedelta(days=365)
            elif mode == "all_time":
                daily_start_date = inception_date
            else:
                backfill_days = days_back if (days_back and days_back > 0) else 365
                daily_start_date = end_date - timedelta(days=backfill_days)
            log_to_file(f"Multi-tier Sync detected (Mode: {mode}). Activities from: {start_date}, Daily Biometrics from: {daily_start_date}")

        # 3. Process Activities
        update_progress(user_id, 10, stage="snapshot_30d", inception_date=inception_str)

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
                    "user_id": normalize_garmin_user_id(user_id),
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
                    upsert_garmin_activities(user_id, batch_activities)
                    _sync_activities_to_calendar(user_id, batch_activities)
                    batch_activities = []
            
            if batch_activities:
                upsert_garmin_activities(user_id, batch_activities)
                _sync_activities_to_calendar(user_id, batch_activities)

        except Exception as e:
            log_to_file(f"Error processing activities: {e}")
            # Continue to daily data even if activities fail partial

        # 4. Process Daily Data using Reverse-Chronological Monthly Chunks
        update_progress(user_id, 30, stage="snapshot_30d", inception_date=inception_str)
        
        chunks = generate_monthly_chunks(daily_start_date, end_date, chunk_size_days=30)
        total_chunks = len(chunks)
        uid_parsed = int(user_id) if str(user_id).isdigit() else user_id
        
        daily_batch = []
        sleep_batch = []
        bio_batch = []

        def _flush_raw_and_biometrics():
            nonlocal biometrics_failures, daily_batch, sleep_batch, bio_batch
            if daily_batch:
                supabase.table("garmin_daily").upsert(daily_batch, on_conflict="user_id, date").execute()
                daily_batch = []
            if sleep_batch:
                supabase.table("garmin_sleep").upsert(sleep_batch, on_conflict="user_id, date").execute()
                sleep_batch = []
            if bio_batch:
                # Coerced in upsert_biometrics_daily. A float resting_hr (48.0)
                # used to 22P02 the int column; that error was swallowed and
                # garmin_daily/garmin_sleep still committed.
                biometrics_failures += upsert_biometrics_daily(bio_batch)
                bio_batch = []

        for c_idx, (chunk_start, chunk_end) in enumerate(chunks):
            # Determine active stage
            if chunk_end >= end_date - timedelta(days=30):
                current_stage = "snapshot_30d"
            elif chunk_end >= end_date - timedelta(days=365):
                current_stage = "deep_365d"
            else:
                current_stage = "lifetime_archive"
            
            chunk_pct = 30 + int(((c_idx + 1) / max(total_chunks, 1)) * 60)
            update_progress(user_id, chunk_pct, stage=current_stage, inception_date=inception_str)
            log_to_file(f"Processing chunk {c_idx+1}/{total_chunks}: {chunk_start} to {chunk_end} (Stage: {current_stage})")

            # Fetch existing populated dates in this chunk for smart delta skipping
            chunk_existing_dates = set()
            if not force_resync:
                try:
                    ex_res = supabase.table("biometrics_daily")\
                        .select("date, resting_hr, sleep_score, hrv")\
                        .eq("user_id", uid_parsed)\
                        .gte("date", chunk_start.isoformat())\
                        .lte("date", chunk_end.isoformat())\
                        .execute()
                    for r in (ex_res.data or []):
                        if r.get("resting_hr") is not None or r.get("sleep_score") is not None or r.get("hrv") is not None:
                            chunk_existing_dates.add(r["date"])
                except Exception as e_ex:
                    log_to_file(f"Could not load existing biometrics dates for chunk {chunk_start}..{chunk_end}: {e_ex}")

            current_day = chunk_start
            while current_day <= chunk_end:
                day_str = current_day.isoformat()
                current_day += timedelta(days=1)

                # Skip if already exists AND we are not forcing resync
                if not force_resync and day_str in chunk_existing_dates:
                    continue

                try:
                    log_to_file(f"Fetching daily: {day_str}")
                    # Wrap in robust calls
                    steps = robust_api_call(garmin_api.get_steps_data, day_str)
                    sleep = robust_api_call(garmin_api.get_sleep_data, day_str)
                    hr = robust_api_call(garmin_api.get_heart_rates, day_str)
                    rhr_raw = robust_api_call(garmin_api.get_rhr_day, day_str)
                    stress_raw = robust_api_call(garmin_api.get_stress_data, day_str)
                    hrv_raw = robust_api_call(garmin_api.get_hrv_data, day_str)

                    # Normalize RHR (Extract scalar from heavy JSON)
                    rhr_val = None
                    try:
                        if isinstance(rhr_raw, dict):
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

                    # Normalize Sleep Score, Hours, and Stages
                    sleep_score = None
                    sleep_hours = None
                    sleep_stages = None
                    deep_sleep_sec = None
                    rem_sleep_sec = None
                    light_sleep_sec = None
                    awake_sleep_sec = None
                    try:
                        if isinstance(sleep, dict):
                            daily_dto = sleep.get('dailySleepDTO') or {}
                            scores = daily_dto.get('sleepScores') or {}
                            if isinstance(scores, dict):
                                overall = scores.get('overall') or {}
                                if isinstance(overall, dict):
                                    sleep_score = overall.get('value')
                            if not sleep_score:
                                sleep_score = sleep.get('sleepQualityScore') or sleep.get('overallSleepScore')
                            sleep_sec = daily_dto.get('sleepTimeSeconds') or sleep.get('totalSleepSeconds') or 0
                            if sleep_sec > 0:
                                sleep_hours = round(sleep_sec / 3600.0, 1)

                            deep_sleep_sec = daily_dto.get('deepSleepSeconds')
                            rem_sleep_sec = daily_dto.get('remSleepSeconds')
                            light_sleep_sec = daily_dto.get('lightSleepSeconds')
                            awake_sleep_sec = daily_dto.get('awakeSleepSeconds')
                            if any(x is not None for x in [deep_sleep_sec, rem_sleep_sec, light_sleep_sec, awake_sleep_sec]):
                                sleep_stages = {
                                    "deep": deep_sleep_sec or 0,
                                    "rem": rem_sleep_sec or 0,
                                    "light": light_sleep_sec or 0,
                                    "awake": awake_sleep_sec or 0
                                }
                    except:
                        pass

                    # Deep telemetry extraction: VO2 Max, Fitness Age, Body Battery, Training Status, SpO2, Respiration
                    vo2_max_val = None
                    fitness_age_val = None
                    body_battery_val = None
                    training_status_val = None
                    acute_load_val = None
                    spo2_val = None
                    respiration_val = None

                    max_m = safe_garmin_call(garmin_api, "get_max_metrics", day_str)
                    if isinstance(max_m, list) and max_m:
                        max_m = max_m[0]
                    if isinstance(max_m, dict):
                        generic = max_m.get("generic") or {}
                        if isinstance(generic, dict):
                            vo2_max_val = generic.get("vo2MaxValue") or generic.get("vo2MaxPrecision")
                        if not vo2_max_val:
                            vo2_max_val = max_m.get("vo2Max") or max_m.get("vo2MaxRunning") or max_m.get("vo2MaxValue")
                        fitness_age_val = max_m.get("fitnessAge")

                    ts_raw = safe_garmin_call(garmin_api, "get_training_status", day_str)
                    if isinstance(ts_raw, dict):
                        training_status_val = (
                            ts_raw.get("trainingStatusKey") or 
                            ts_raw.get("trainingStatus") or 
                            ts_raw.get("userTrainingStatus", {}).get("trainingStatusKey")
                        )
                        acute_load_val = ts_raw.get("acuteTrainingLoad") or ts_raw.get("acuteLoad")
                        if not vo2_max_val:
                            most_recent_vo2 = ts_raw.get("mostRecentVO2Max", {})
                            if isinstance(most_recent_vo2, dict):
                                vo2_max_val = most_recent_vo2.get("generic", {}).get("vo2MaxValue") or most_recent_vo2.get("vo2Max")

                    bb_raw = safe_garmin_call(garmin_api, "get_body_battery", day_str)
                    if isinstance(bb_raw, list) and bb_raw:
                        item = bb_raw[0]
                        if isinstance(item, dict):
                            body_battery_val = item.get("charged") or item.get("highestBodyBattery") or item.get("value")
                            if body_battery_val is None and "bodyBatteryValuesArray" in item:
                                vals = [v[1] for v in item.get("bodyBatteryValuesArray", []) if isinstance(v, (list, tuple)) and len(v) > 1 and v[1] is not None]
                                if vals:
                                    body_battery_val = max(vals)
                    elif isinstance(bb_raw, dict):
                        body_battery_val = bb_raw.get("charged") or bb_raw.get("highestBodyBattery") or bb_raw.get("value")
                    elif isinstance(bb_raw, (int, float)):
                        body_battery_val = int(bb_raw)

                    spo2_raw = safe_garmin_call(garmin_api, "get_spo2_data", day_str)
                    if isinstance(spo2_raw, dict):
                        spo2_val = spo2_raw.get("averageSpO2") or spo2_raw.get("latestSpO2") or spo2_raw.get("avgSpO2")
                    elif isinstance(spo2_raw, (int, float)):
                        spo2_val = spo2_raw

                    resp_raw = safe_garmin_call(garmin_api, "get_respiration_data", day_str)
                    if isinstance(resp_raw, dict):
                        respiration_val = (
                            resp_raw.get("avgWakingRespirationValue") or 
                            resp_raw.get("avgSleepRespirationValue") or 
                            resp_raw.get("averageRespirationValue")
                        )
                    elif isinstance(resp_raw, (int, float)):
                        respiration_val = resp_raw

                    # Normalize HRV
                    hrv_val = None
                    hrv_status = None
                    try:
                        if isinstance(hrv_raw, dict):
                            summary = hrv_raw.get('hrvSummary') or {}
                            hrv_val = summary.get('lastNightAvg') or summary.get('weeklyAvg') or hrv_raw.get('lastNight5MinHigh')
                            hrv_status = summary.get('status') or hrv_raw.get('status')
                        elif isinstance(hrv_raw, (int, float)):
                            hrv_val = hrv_raw
                    except:
                        pass

                    daily_doc = {
                        "user_id": user_id,
                        "date": day_str,
                        "steps": steps,
                        "heartrate": hr,
                        "resting_hr": rhr_val,
                        "stress": stress_val,
                        "synced_at": datetime.now(timezone.utc).isoformat()
                    }

                    # Build the athlete-facing row before queueing raw rows so a
                    # parse error cannot commit garmin_daily without biometrics.
                    bio_doc = {
                        "user_id": uid_parsed,
                        "date": day_str,
                        "resting_hr": rhr_val,
                        "hrv": hrv_val,
                        "hrv_ms": hrv_val,
                        "hrv_status": hrv_status,
                        "sleep_score": sleep_score,
                        "sleep_hours": sleep_hours,
                        "deep_sleep_hours": round(deep_sleep_sec / 3600.0, 2) if deep_sleep_sec else None,
                        "rem_sleep_hours": round(rem_sleep_sec / 3600.0, 2) if rem_sleep_sec else None,
                        "light_sleep_hours": round(light_sleep_sec / 3600.0, 2) if light_sleep_sec else None,
                        "sleep_stages": sleep_stages,
                        "stress_level": stress_val,
                        "body_battery": body_battery_val,
                        "vo2_max": vo2_max_val,
                        "fitness_age": fitness_age_val,
                        "training_status": training_status_val,
                        "acute_load": acute_load_val,
                        "spo2": spo2_val,
                        "respiration": respiration_val,
                        "source": "garmin",
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    daily_batch.append(daily_doc)
                    bio_batch.append(bio_doc)

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

                # Upsert batches of 7 (weekly). Biometrics flush with the raw rows.
                if len(daily_batch) >= 7 or len(sleep_batch) >= 7 or len(bio_batch) >= 7:
                    _flush_raw_and_biometrics()

        # Final flush
        _flush_raw_and_biometrics()


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

        # Complete. Do not report synced when athlete-facing rows were dropped.
        update_progress(user_id, 100)
        completed_at = datetime.now(timezone.utc).isoformat()
        if biometrics_failures:
            log_to_file(f"Biometrics upsert failures: {biometrics_failures}")
            supabase.table("users").update({
                "garmin_sync_status": "error",
                "garmin_sync_progress": 100,
                "garmin_last_sync_error": (
                    f"biometrics_daily upsert failed for {biometrics_failures} day(s) "
                    "while garmin_daily and garmin_sleep were written. "
                    "Run remirror-biometrics for this user."
                ),
                "garmin_sync_completed_at": completed_at,
            }).eq("id", user_id).execute()
        else:
            supabase.table("users").update({
                "garmin_sync_status": "synced",
                "garmin_sync_progress": 100,
                "garmin_last_sync_error": None,
                "garmin_sync_completed_at": completed_at,
            }).eq("id", user_id).execute()
            log_to_file("Sync Complete.")

    except Exception as e:
        log_to_file(f"CRITICAL SYNC ERROR: {e}")
        supabase.table("users").update({
            "garmin_sync_status": "error",
            "garmin_last_sync_error": str(e)
        }).eq("id", user_id).execute()