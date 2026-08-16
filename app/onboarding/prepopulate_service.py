# app/onboarding/prepopulate_service.py
"""
Telemetry Pre-Population Service for GYMBro Onboarding Lifecycle.

Extracts demographic biometrics, rolling 14-day physiological baselines,
and acute athletic workload from connected hardware providers (Garmin, Strava, Apple HealthKit)
into draft Athlete Profiles with graceful manual fallback.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from app.supabase_client import supabase
from app.health_hub.ingestion_service import ingest_telemetry_payload

logger = logging.getLogger(__name__)


def format_duration(seconds) -> Optional[str]:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds is None:
        return None
    try:
        seconds = int(seconds)
        if seconds < 0:
            return None
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}" if minutes >= 10 else f"{minutes}:{secs:02d}"
    except (ValueError, TypeError):
        return None


class TelemetryPrepopulateService:
    """
    Coordinates multi-provider telemetry extraction and baseline pre-population for onboarding.
    """

    @classmethod
    def get_prepopulation_data(cls, user_id: Any, raw_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculates and returns pre-populated profile biometrics, 14-day rolling averages,
        and personal records from connected hardware providers or raw incoming payloads.
        """
        uid = int(user_id) if str(user_id).isdigit() else user_id

        # 0. Ingest raw HealthKit / client payload if provided
        if raw_payload:
            try:
                ingest_telemetry_payload(uid, raw_payload)
            except Exception as e:
                logger.warning(f"Failed to ingest raw payload in prepopulate for user {uid}: {e}")

        # Default structured result
        result: Dict[str, Any] = {
            "user_id": uid,
            "data_available": False,
            "age": None,
            "weight": None,
            "height": None,
            "biological_sex": None,
            "sport_history": "Running & Functional Fitness",
            "running_experience": "Beginner",
            "resting_hr": 65,  # Fallback default
            "hrv": None,
            "hrv_ms": None,
            "sleep_hours": 7.5,  # Fallback default
            "weekly_volume": 0.0,
            "acute_weekly_volume_km": 0.0,
            "connected_providers": [],
            "personal_records": {
                "run_5k": None,
                "run_10k": None,
                "run_half": None,
                "bike_longest": None,
                "swim_100m": None,
                "hike_peak": None
            }
        }

        if not supabase:
            return result

        try:
            # 1. Retrieve current profile fields from users table
            user_res = supabase.table("users").select(
                "age, weight, height, sport_history, running_experience, goals, "
                "garmin_email, strava_access_token"
            ).eq("id", uid).execute()

            has_connected_wearable = False
            if user_res.data:
                user = user_res.data[0]
                goals = user.get("goals") or {}
                result["age"] = user.get("age") or goals.get("age")
                result["weight"] = float(user.get("weight")) if user.get("weight") else (float(goals.get("weight")) if goals.get("weight") else None)
                result["height"] = float(user.get("height")) if user.get("height") else (float(goals.get("height")) if goals.get("height") else None)
                result["biological_sex"] = goals.get("biological_sex") or user.get("biological_sex")
                if user.get("sport_history"):
                    result["sport_history"] = user.get("sport_history")
                if user.get("running_experience"):
                    result["running_experience"] = user.get("running_experience")

                # Detect connected providers
                if user.get("garmin_email"):
                    result["connected_providers"].append("garmin")
                    has_connected_wearable = True
                if user.get("strava_access_token"):
                    result["connected_providers"].append("strava")
                    has_connected_wearable = True

            rhr_samples: List[int] = []
            hrv_samples: List[int] = []
            sleep_samples: List[float] = []

            # If raw_payload contains demographic biometrics, supplement missing profile fields
            if raw_payload:
                raw_bio = raw_payload.get("biometrics") if isinstance(raw_payload.get("biometrics"), dict) else raw_payload
                if not result["age"] and raw_bio.get("age"):
                    result["age"] = int(raw_bio["age"])
                if not result["weight"] and (raw_bio.get("weight_kg") or raw_bio.get("weight")):
                    result["weight"] = float(raw_bio.get("weight_kg") or raw_bio.get("weight"))
                if not result["height"] and (raw_bio.get("height_cm") or raw_bio.get("height")):
                    result["height"] = float(raw_bio.get("height_cm") or raw_bio.get("height"))
                if not result["biological_sex"] and raw_bio.get("biological_sex"):
                    result["biological_sex"] = str(raw_bio["biological_sex"])
                if raw_bio.get("resting_heart_rate") or raw_bio.get("resting_hr"):
                    rhr_samples.append(int(raw_bio.get("resting_heart_rate") or raw_bio.get("resting_hr")))
                if raw_bio.get("hrv_sdnn") or raw_bio.get("hrv_ms") or raw_bio.get("hrv"):
                    hrv_samples.append(int(raw_bio.get("hrv_sdnn") or raw_bio.get("hrv_ms") or raw_bio.get("hrv")))
                if raw_bio.get("sleep_hours"):
                    sleep_samples.append(float(raw_bio["sleep_hours"]))
                src = raw_payload.get("source") or "apple_health"
                if src not in result["connected_providers"]:
                    result["connected_providers"].append(src)
                    has_connected_wearable = True

            # 2. Fetch 14-day Daily Health Metrics (Resting HR, HRV, Sleep)
            two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()

            # 2a. biometrics_daily table
            try:
                bio_res = supabase.table("biometrics_daily").select(
                    "resting_hr, hrv, hrv_ms, sleep_hours, source"
                ).eq("user_id", uid).gte("date", two_weeks_ago).execute()

                if bio_res.data:
                    for b in bio_res.data:
                        if b.get("resting_hr"):
                            rhr_samples.append(int(b["resting_hr"]))
                        hrv_val = b.get("hrv") or b.get("hrv_ms")
                        if hrv_val:
                            hrv_samples.append(int(hrv_val))
                        if b.get("sleep_hours"):
                            sleep_samples.append(float(b["sleep_hours"]))
                        src = b.get("source")
                        if src and src in ["apple_health", "healthkit"] and "apple_health" not in result["connected_providers"]:
                            result["connected_providers"].append("apple_health")
                            has_connected_wearable = True
            except Exception as e:
                logger.warning(f"Error querying biometrics_daily for user {uid}: {e}")

            # 2b. garmin_daily table
            try:
                g_daily_res = supabase.table("garmin_daily").select("resting_hr").eq("user_id", uid).gte("date", two_weeks_ago).execute()
                if g_daily_res.data:
                    for gd in g_daily_res.data:
                        rhr_raw = gd.get("resting_hr")
                        if isinstance(rhr_raw, (int, float)):
                            rhr_samples.append(int(rhr_raw))
                        elif isinstance(rhr_raw, dict):
                            r_val = rhr_raw.get("restingHeartRate") or rhr_raw.get("value")
                            if r_val:
                                rhr_samples.append(int(r_val))
            except Exception as e:
                logger.warning(f"Error querying garmin_daily for user {uid}: {e}")

            # 2c. garmin_sleep table
            try:
                g_sleep_res = supabase.table("garmin_sleep").select("sleep_data").eq("user_id", uid).gte("date", two_weeks_ago).execute()
                if g_sleep_res.data:
                    for gs in g_sleep_res.data:
                        s_data = gs.get("sleep_data") or {}
                        secs = s_data.get("dailySleepDTO", {}).get("sleepTimeSeconds")
                        if secs:
                            sleep_samples.append(float(secs) / 3600.0)
            except Exception as e:
                logger.warning(f"Error querying garmin_sleep for user {uid}: {e}")

            # Aggregate averages
            if rhr_samples:
                result["resting_hr"] = int(round(sum(rhr_samples) / len(rhr_samples)))
                has_connected_wearable = True

            if hrv_samples:
                avg_hrv = int(round(sum(hrv_samples) / len(hrv_samples)))
                result["hrv"] = avg_hrv
                result["hrv_ms"] = avg_hrv
                has_connected_wearable = True

            if sleep_samples:
                result["sleep_hours"] = round(sum(sleep_samples) / len(sleep_samples), 1)
                has_connected_wearable = True

            # 3. Fetch & Normalize Activities
            normalized_activities: List[Dict[str, Any]] = []

            # Garmin
            try:
                g_res = supabase.table("garmin_activities").select("start_time_local, distance, duration, activity_type, elevation_gain").eq("user_id", uid).execute()
                for act in (g_res.data or []):
                    normalized_activities.append({
                        "start_time": str(act.get("start_time_local") or ""),
                        "activity_type": (act.get("activity_type") or "").lower(),
                        "distance_m": float(act.get("distance") or 0.0),
                        "duration_s": float(act.get("duration") or 0.0),
                        "elevation_gain_m": float(act.get("elevation_gain") or 0.0)
                    })
            except Exception as e:
                logger.warning(f"Garmin activities query error: {e}")

            # Strava
            try:
                s_res = supabase.table("strava_activities").select("start_date_local, distance, moving_time, elapsed_time, type, total_elevation_gain").eq("user_id", uid).execute()
                for act in (s_res.data or []):
                    normalized_activities.append({
                        "start_time": str(act.get("start_date_local") or ""),
                        "activity_type": (act.get("type") or "").lower(),
                        "distance_m": float(act.get("distance") or 0.0),
                        "duration_s": float(act.get("moving_time") or act.get("elapsed_time") or 0.0),
                        "elevation_gain_m": float(act.get("total_elevation_gain") or 0.0)
                    })
            except Exception as e:
                logger.warning(f"Strava activities query error: {e}")

            # Generic / Apple HealthKit
            try:
                gen_res = supabase.table("activities").select("start_time_local, distance, duration, activity_type, elevation_gain").eq("user_id", uid).execute()
                for act in (gen_res.data or []):
                    normalized_activities.append({
                        "start_time": str(act.get("start_time_local") or ""),
                        "activity_type": (act.get("activity_type") or "").lower(),
                        "distance_m": float(act.get("distance") or 0.0),
                        "duration_s": float(act.get("duration") or 0.0),
                        "elevation_gain_m": float(act.get("elevation_gain") or 0.0)
                    })
            except Exception as e:
                logger.warning(f"Generic activities query error: {e}")

            # 4. Calculate Rolling 14-Day Running Volume & PRs
            run_match_types = ["run", "running", "treadmill", "trailrun", "trail_running", "track_running"]
            bike_match_types = ["cycling", "road_biking", "mountain_biking", "ride", "virtualride", "ebikeride", "bike"]
            hike_match_types = ["hiking", "hike", "mountain_climbing", "alpineski"]

            fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
            recent_run_dist_m = 0.0
            total_runs = 0

            fastest_5k = None
            fastest_10k = None
            fastest_half = None
            longest_bike_m = 0.0
            max_hike_elev_m = 0.0

            for act in normalized_activities:
                act_type = act["activity_type"]
                dist = act["distance_m"]
                dur = act["duration_s"]
                elev = act["elevation_gain_m"]
                start_dt = act["start_time"]

                is_run = any(rt in act_type for rt in run_match_types)
                is_bike = any(bt in act_type for bt in bike_match_types)
                is_hike = any(ht in act_type for ht in hike_match_types)

                if is_run:
                    total_runs += 1
                    if start_dt >= fourteen_days_ago:
                        recent_run_dist_m += dist

                    # Running PR scans
                    if dur > 0:
                        if 4800 <= dist <= 5500:
                            if not fastest_5k or dur < fastest_5k:
                                fastest_5k = dur
                        elif 9500 <= dist <= 11000:
                            if not fastest_10k or dur < fastest_10k:
                                fastest_10k = dur
                        elif 20000 <= dist <= 23000:
                            if not fastest_half or dur < fastest_half:
                                fastest_half = dur

                elif is_bike:
                    if dist > longest_bike_m:
                        longest_bike_m = dist

                elif is_hike:
                    if elev > max_hike_elev_m:
                        max_hike_elev_m = elev

            # Rolling 14-day average weekly km (last 14 days / 2 weeks)
            weekly_vol_km = round((recent_run_dist_m / 1000.0) / 2.0, 1)
            result["weekly_volume"] = weekly_vol_km
            result["acute_weekly_volume_km"] = weekly_vol_km

            # 5. Estimate Running Experience Level
            if total_runs > 50 or weekly_vol_km > 40:
                result["running_experience"] = "Advanced"
            elif total_runs > 15 or weekly_vol_km > 15:
                result["running_experience"] = "Intermediate"
            elif total_runs > 0:
                result["running_experience"] = "Beginner"

            # 6. Format PRs
            if fastest_5k:
                result["personal_records"]["run_5k"] = format_duration(fastest_5k)
            if fastest_10k:
                result["personal_records"]["run_10k"] = format_duration(fastest_10k)
            if fastest_half:
                result["personal_records"]["run_half"] = format_duration(fastest_half)
            if longest_bike_m > 0:
                result["personal_records"]["bike_longest"] = f"{int(longest_bike_m / 1000)} km"
            if max_hike_elev_m > 0:
                result["personal_records"]["hike_peak"] = f"{int(max_hike_elev_m)}m"

            # Set data_available flag
            if (
                has_connected_wearable or
                len(rhr_samples) > 0 or
                len(hrv_samples) > 0 or
                len(sleep_samples) > 0 or
                total_runs > 0 or
                longest_bike_m > 0 or
                max_hike_elev_m > 0
            ):
                result["data_available"] = True

            return result

        except Exception as e:
            logger.error(f"Error computing telemetry prepopulate data for user {uid}: {e}")
            return result
