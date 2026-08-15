# app/health_hub/ingestion_service.py
from datetime import datetime, timezone
import logging
from typing import Dict, List, Any, Optional
from app.supabase_client import supabase
from app.health_hub.deduplication_service import deduplicate_activities, resolve_biometrics_priority

logger = logging.getLogger(__name__)

def record_daily_biometrics(user_id: Any, payload: dict) -> dict:
    """
    Normalizes and upserts a single day's biometric telemetry into biometrics_daily.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id
    date_val = payload.get('date')
    if not date_val:
        date_val = datetime.now(timezone.utc).date().isoformat()
    
    record = {
        'user_id': uid,
        'date': str(date_val)[:10],
        'resting_hr': payload.get('resting_hr'),
        'hrv': payload.get('hrv') or payload.get('hrv_ms'),
        'hrv_ms': payload.get('hrv_ms') or payload.get('hrv'),
        'hrv_status': payload.get('hrv_status'),
        'sleep_hours': payload.get('sleep_hours'),
        'sleep_score': payload.get('sleep_score'),
        'deep_sleep_hours': payload.get('deep_sleep_hours'),
        'rem_sleep_hours': payload.get('rem_sleep_hours'),
        'light_sleep_hours': payload.get('light_sleep_hours'),
        'sleep_stages': payload.get('sleep_stages'),
        'recovery_score': payload.get('recovery_score'),
        'body_battery': payload.get('body_battery'),
        'stress_level': payload.get('stress_level'),
        'vo2_max': payload.get('vo2_max'),
        'fitness_age': payload.get('fitness_age'),
        'training_status': payload.get('training_status'),
        'acute_load': payload.get('acute_load'),
        'spo2': payload.get('spo2'),
        'respiration': payload.get('respiration'),
        'steps': payload.get('steps'),
        'calories_burned': payload.get('calories_burned'),
        'source': payload.get('source') or payload.get('raw_source', 'manual'),
        'raw_source': payload.get('raw_source') or payload.get('source', 'manual'),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Filter out None values to avoid overwriting existing non-null fields during merge
    clean_record = {k: v for k, v in record.items() if v is not None}
    clean_record['user_id'] = uid
    clean_record['date'] = str(date_val)[:10]

    if supabase:
        try:
            res = supabase.table('biometrics_daily').upsert(clean_record, on_conflict="user_id, date").execute()
            if res and hasattr(res, 'data') and res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            logger.warning(f"Error upserting biometrics_daily for user {user_id} on {date_val}: {e}")
            
    return clean_record

def ingest_telemetry_payload(user_id: Any, payload: dict) -> dict:
    """
    Ingests comprehensive multi-metric telemetry payload (e.g. from Apple HealthKit or custom client sync).
    Processes daily biometrics, workouts/activities, and updates training baselines.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id
    default_source = payload.get('source') or payload.get('raw_source') or 'apple_health'
    
    biometrics_ingested = 0
    activities_ingested = 0
    
    # 1. Process Biometrics (list or single dict)
    biometrics_data = payload.get('biometrics') or payload.get('samples') or []
    if isinstance(biometrics_data, dict):
        biometrics_data = [biometrics_data]
    elif not biometrics_data and ('resting_hr' in payload or 'sleep_hours' in payload or 'steps' in payload or 'hrv' in payload):
        # Single top-level biometric payload
        biometrics_data = [payload]
        
    for bio in biometrics_data:
        bio_copy = dict(bio)
        if 'source' not in bio_copy and 'raw_source' not in bio_copy:
            bio_copy['source'] = default_source
            bio_copy['raw_source'] = default_source
        record_daily_biometrics(uid, bio_copy)
        biometrics_ingested += 1

    # 2. Process Activities / Workouts
    activities_data = payload.get('activities') or payload.get('workouts') or []
    inserted_activities = []
    
    for act in activities_data:
        start_time = (
            act.get('start_time_local') or 
            act.get('start_time') or 
            act.get('start_date_local') or 
            act.get('start_date') or 
            datetime.now(timezone.utc).isoformat()
        )
        
        act_id = act.get('activity_id') or act.get('id') or f"{default_source}_{int(datetime.now().timestamp())}_{activities_ingested}"
        
        act_record = {
            'user_id': uid,
            'activity_type': act.get('activity_type') or act.get('type') or 'workout',
            'name': act.get('name') or act.get('activity_name') or f"{default_source.capitalize()} Workout",
            'start_time_local': start_time,
            'distance': float(act.get('distance') or act.get('distance_m') or 0.0),
            'duration': float(act.get('duration') or act.get('duration_s') or act.get('moving_time') or 0.0),
            'calories': float(act.get('calories') or act.get('calories_burned') or 0.0),
            'average_hr': act.get('average_hr') or act.get('average_heartrate'),
            'max_hr': act.get('max_hr') or act.get('max_heartrate'),
            'elevation_gain': act.get('elevation_gain') or act.get('total_elevation_gain'),
            'notes': act.get('notes') or f"Source: {default_source}",
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        if supabase:
            try:
                res = supabase.table('activities').insert(act_record).execute()
                if res and hasattr(res, 'data') and res.data:
                    inserted_activities.append(res.data[0])
                else:
                    inserted_activities.append(act_record)
            except Exception as e:
                logger.warning(f"Failed to insert workout for user {user_id}: {e}")
                inserted_activities.append(act_record)
        else:
            inserted_activities.append(act_record)
            
        activities_ingested += 1

    # 3. Trigger baseline calculation in background
    try:
        from app.analytics.analytics_service import AnalyticsService
        AnalyticsService.calculate_baselines(str(uid))
    except Exception as e:
        logger.debug(f"Baseline recalculation triggered: {e}")

    return {
        "status": "success",
        "source": default_source,
        "biometrics_ingested": biometrics_ingested,
        "activities_ingested": activities_ingested,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def get_unified_activities(
    user_id: Any, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None,
    activity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    custom_priority: Optional[Dict[str, int]] = None
) -> List[Dict]:
    """
    Fetches raw activities across garmin_activities, strava_activities, and activities,
    normalizes their data representation, applies deterministic deduplication, and returns
    the unified stream sorted by start time descending.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id
    raw_activities: List[Dict] = []
    
    if not supabase:
        return []

    # 1. Fetch Garmin Activities
    try:
        g_query = supabase.table("garmin_activities").select("*").eq("user_id", uid)
        if start_date:
            g_query = g_query.gte("start_time_local", start_date)
        if end_date:
            g_query = g_query.lte("start_time_local", end_date)
        g_res = g_query.order("start_time_local", desc=True).limit(500).execute()
        for g in (g_res.data or []):
            raw_activities.append({
                "id": g.get("id"),
                "activity_id": str(g.get("activity_id") or g.get("id")),
                "source": "garmin",
                "name": g.get("activity_name") or "Garmin Activity",
                "activity_name": g.get("activity_name") or "Garmin Activity",
                "activity_type": g.get("activity_type") or "running",
                "type": g.get("activity_type") or "running",
                "start_time_local": g.get("start_time_local"),
                "start_time": g.get("start_time_local"),
                "distance": g.get("distance") or 0.0,
                "distance_m": g.get("distance") or 0.0,
                "duration": g.get("duration") or 0.0,
                "duration_s": g.get("duration") or 0.0,
                "calories": g.get("calories") or 0.0,
                "average_hr": g.get("average_hr"),
                "max_hr": g.get("max_hr"),
                "elevation_gain": g.get("elevation_gain"),
                "average_speed": g.get("average_speed"),
                "max_speed": g.get("max_speed"),
                "average_cadence": g.get("average_cadence"),
                "details": g.get("details") or {},
                "synced_at": g.get("synced_at")
            })
    except Exception as e:
        logger.error(f"Error fetching Garmin activities for user {user_id}: {e}")

    # 2. Fetch Strava Activities
    try:
        s_query = supabase.table("strava_activities").select("*").eq("user_id", uid)
        if start_date:
            s_query = s_query.gte("start_date_local", start_date)
        if end_date:
            s_query = s_query.lte("start_date_local", end_date)
        s_res = s_query.order("start_date_local", desc=True).limit(500).execute()
        for s in (s_res.data or []):
            raw_activities.append({
                "id": s.get("id"),
                "activity_id": str(s.get("activity_id") or s.get("id")),
                "source": "strava",
                "name": s.get("name") or "Strava Activity",
                "activity_name": s.get("name") or "Strava Activity",
                "activity_type": s.get("type") or "running",
                "type": s.get("type") or "running",
                "start_time_local": s.get("start_date_local"),
                "start_time": s.get("start_date_local"),
                "distance": s.get("distance") or 0.0,
                "distance_m": s.get("distance") or 0.0,
                "duration": s.get("moving_time") or s.get("elapsed_time") or 0.0,
                "duration_s": s.get("moving_time") or s.get("elapsed_time") or 0.0,
                "calories": s.get("calories") or 0.0,
                "average_hr": s.get("average_hr"),
                "max_hr": s.get("max_hr"),
                "elevation_gain": s.get("total_elevation_gain") or s.get("elevation_gain"),
                "average_speed": s.get("average_speed") or s.get("average_speed_perf"),
                "max_speed": s.get("max_speed") or s.get("max_speed_perf"),
                "average_cadence": s.get("average_cadence"),
                "details": s.get("raw_data") or {},
                "synced_at": s.get("synced_at")
            })
    except Exception as e:
        logger.error(f"Error fetching Strava activities for user {user_id}: {e}")

    # 3. Fetch Generic / Apple HealthKit / Manual Activities
    try:
        a_query = supabase.table("activities").select("*").eq("user_id", uid)
        if start_date:
            a_query = a_query.gte("start_time_local", start_date)
        if end_date:
            a_query = a_query.lte("start_time_local", end_date)
        a_res = a_query.order("start_time_local", desc=True).limit(500).execute()
        for a in (a_res.data or []):
            src = "apple_health" if "apple_health" in str(a.get("notes", "")).lower() else "manual"
            raw_activities.append({
                "id": a.get("id"),
                "activity_id": str(a.get("id")),
                "source": src,
                "name": a.get("name") or "Workout",
                "activity_name": a.get("name") or "Workout",
                "activity_type": a.get("activity_type") or "other",
                "type": a.get("activity_type") or "other",
                "start_time_local": a.get("start_time_local"),
                "start_time": a.get("start_time_local"),
                "distance": a.get("distance") or 0.0,
                "distance_m": a.get("distance") or 0.0,
                "duration": a.get("duration") or 0.0,
                "duration_s": a.get("duration") or 0.0,
                "calories": a.get("calories") or 0.0,
                "average_hr": a.get("average_hr"),
                "max_hr": a.get("max_hr"),
                "elevation_gain": a.get("elevation_gain"),
                "notes": a.get("notes"),
                "details": {"notes": a.get("notes")},
                "synced_at": a.get("created_at")
            })
    except Exception as e:
        logger.error(f"Error fetching generic activities for user {user_id}: {e}")

    # 4. Deduplicate across sources
    deduped = deduplicate_activities(raw_activities, custom_priority=custom_priority)

    # 5. Filter by activity_type if requested
    if activity_type:
        target_type = activity_type.lower()
        deduped = [
            act for act in deduped 
            if target_type in str(act.get("activity_type", "")).lower() or target_type in str(act.get("type", "")).lower()
        ]

    # 6. Sort descending by start time
    from app.health_hub.deduplication_service import parse_iso_datetime, extract_activity_start_time
    deduped.sort(key=lambda x: parse_iso_datetime(extract_activity_start_time(x)), reverse=True)

    # 7. Apply pagination
    return deduped[offset:offset + limit]

def get_telemetry_status(user_id: Any) -> Dict[str, Any]:
    """
    Returns connection and synchronization status across Garmin, Strava, and Apple HealthKit.
    """
    uid = int(user_id) if str(user_id).isdigit() else user_id
    status_summary = {
        "user_id": uid,
        "garmin": {
            "connected": False,
            "status": "disconnected",
            "last_synced": None,
            "progress": 0,
            "last_error": None
        },
        "strava": {
            "connected": False,
            "status": "disconnected",
            "last_updated": None,
            "athlete": None
        },
        "apple_health": {
            "connected": False,
            "last_synced": None
        },
        "primary_source_priority": ["garmin", "strava", "apple_health", "manual"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if not supabase:
        return status_summary

    try:
        user_res = supabase.table("users").select(
            "garmin_email, garmin_sync_status, garmin_sync_completed_at, garmin_last_sync_error, "
            "strava_access_token, strava_last_updated, goals"
        ).eq("id", uid).execute()
        
        if user_res.data:
            u = user_res.data[0]
            goals = u.get("goals") or {}
            
            # Garmin
            garmin_connected = bool(u.get("garmin_email"))
            status_summary["garmin"]["connected"] = garmin_connected
            status_summary["garmin"]["status"] = u.get("garmin_sync_status") or ("synced" if garmin_connected else "disconnected")
            status_summary["garmin"]["last_synced"] = u.get("garmin_sync_completed_at") or goals.get("garmin_last_synced")
            status_summary["garmin"]["progress"] = goals.get("sync_progress", 100 if garmin_connected else 0)
            status_summary["garmin"]["last_error"] = u.get("garmin_last_sync_error")

            # Strava
            strava_connected = bool(u.get("strava_access_token"))
            status_summary["strava"]["connected"] = strava_connected
            status_summary["strava"]["status"] = "connected" if strava_connected else "disconnected"
            status_summary["strava"]["last_updated"] = u.get("strava_last_updated")
            status_summary["strava"]["athlete"] = goals.get("strava_athlete")

        # Check latest biometrics_daily for Apple Health activity
        bio_res = supabase.table("biometrics_daily").select("date, source, updated_at").eq("user_id", uid).order("date", desc=True).limit(5).execute()
        if bio_res.data:
            for b in bio_res.data:
                if b.get("source") in ["apple_health", "healthkit"]:
                    status_summary["apple_health"]["connected"] = True
                    status_summary["apple_health"]["last_synced"] = b.get("updated_at") or b.get("date")
                    break

    except Exception as e:
        logger.error(f"Error fetching telemetry status for user {user_id}: {e}")

    return status_summary
