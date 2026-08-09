# app/coach/prepopulate_service.py

import logging
from datetime import datetime, timedelta, timezone
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

def format_duration(seconds):
    """Format seconds into HH:MM:SS or MM:SS."""
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    except:
        return None

def calculate_prepopulation_data(user_id):
    """
    Scrapes Garmin & Strava data from Supabase, estimates demographic and performance metrics,
    and returns a pre-populated profile dictionary for verification.
    """
    try:
        # Initialize default results
        result = {
            "age": None,
            "weight": None,
            "height": None,
            "sport_history": "Running",
            "running_experience": "Beginner",
            "weekly_volume": 0,
            "resting_hr": 0,
            "sleep_hours": 0.0,
            "personal_records": {
                "run_5k": None,
                "run_10k": None,
                "run_half": None,
                "bike_longest": None,
                "swim_100m": None,
                "hike_peak": None
            }
        }

        # 1. Retrieve current profile bio details (if already present in Supabase)
        user_res = supabase.table("users").select("age, weight, height, sport_history, running_experience").eq("id", user_id).execute()
        if user_res.data:
            user = user_res.data[0]
            result["age"] = user.get("age") or result["age"]
            result["weight"] = float(user.get("weight")) if user.get("weight") else result["weight"]
            result["height"] = float(user.get("height")) if user.get("height") else result["height"]
            result["sport_history"] = user.get("sport_history") or result["sport_history"]
            result["running_experience"] = user.get("running_experience") or result["running_experience"]

        # 2. Fetch last 14 days of Daily Health Metrics (RHR, Sleep)
        two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
        
        daily_res = supabase.table("garmin_daily").select("resting_hr").eq("user_id", user_id).gte("date", two_weeks_ago).execute()
        rhr_vals = [r["resting_hr"] for r in daily_res.data if r.get("resting_hr")] if daily_res.data else []
        if rhr_vals:
            result["resting_hr"] = int(sum(rhr_vals) / len(rhr_vals))

        sleep_res = supabase.table("garmin_sleep").select("sleep_data").eq("user_id", user_id).gte("date", two_weeks_ago).execute()
        sleep_hours = []
        if sleep_res.data:
            for s in sleep_res.data:
                try:
                    secs = s.get("sleep_data", {}).get("dailySleepDTO", {}).get("sleepTimeSeconds")
                    if secs:
                        sleep_hours.append(secs / 3600.0)
                except:
                    pass
        if sleep_hours:
            result["sleep_hours"] = round(sum(sleep_hours) / len(sleep_hours), 1)

        # 3. Fetch Garmin & Strava Activities (Last 28 days for volume, all-time for PRs)
        # Running types
        garmin_run_types = ['running', 'treadmill_running', 'trail_running', 'street_running', 'track_running']
        strava_run_types = ['Run', 'Treadmill', 'TrailRun']
        
        # Garmin Activities
        g_acts = []
        try:
            g_res = supabase.table("garmin_activities").select("start_time_local, distance, duration, activity_type, elevation_gain").eq("user_id", user_id).execute()
            g_acts = g_res.data if g_res.data else []
        except Exception as e:
            logger.error(f"Error prepopulating from Garmin: {e}")

        # Strava Activities
        s_acts = []
        try:
            s_res = supabase.table("strava_activities").select("start_date_local, distance, moving_time, elapsed_time, type, total_elevation_gain").eq("user_id", user_id).execute()
            s_acts = s_res.data if s_res.data else []
        except Exception as e:
            logger.error(f"Error prepopulating from Strava: {e}")

        # 4. Calculate Weekly Running Volume (Last 28 Days)
        twenty_eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=28)).isoformat()
        
        recent_run_dist_m = 0
        
        for act in g_acts:
            dt = act.get("start_time_local", "")
            if dt >= twenty_eight_days_ago and act.get("activity_type") in garmin_run_types:
                recent_run_dist_m += act.get("distance") or 0
                
        for act in s_acts:
            dt = act.get("start_date_local", "")
            if dt >= twenty_eight_days_ago and act.get("type") in strava_run_types:
                recent_run_dist_m += act.get("distance") or 0

        result["weekly_volume"] = round((recent_run_dist_m / 1000.0) / 4.0, 1)

        # 5. Estimate Running Experience Level
        total_runs = sum(1 for a in g_acts if a.get("activity_type") in garmin_run_types) + \
                     sum(1 for a in s_acts if a.get("type") in strava_run_types)
                     
        if total_runs > 50 or result["weekly_volume"] > 40:
            result["running_experience"] = "Advanced"
        elif total_runs > 15 or result["weekly_volume"] > 15:
            result["running_experience"] = "Intermediate"
        else:
            result["running_experience"] = "Beginner"

        # 6. Personal Records (PR) Scan
        fastest_5k = None
        fastest_10k = None
        fastest_half = None
        longest_bike_m = 0
        max_hike_elev_m = 0

        # Scan Garmin activities
        for act in g_acts:
            dist = act.get("distance") or 0
            dur = act.get("duration") or 0
            act_type = act.get("activity_type") or ""
            
            # Running PRs
            if act_type in garmin_run_types and dur > 0:
                if 4800 <= dist <= 5500: # 5k range
                    if not fastest_5k or dur < fastest_5k: fastest_5k = dur
                elif 9500 <= dist <= 11000: # 10k range
                    if not fastest_10k or dur < fastest_10k: fastest_10k = dur
                elif 20000 <= dist <= 23000: # Half Marathon range
                    if not fastest_half or dur < fastest_half: fastest_half = dur
            
            # Cycling longest ride
            if act_type in ["cycling", "road_biking", "mountain_biking"]:
                if dist > longest_bike_m: longest_bike_m = dist

            # Hiking peak elevation
            if act_type in ["hiking", "mountain_climbing"]:
                elev = act.get("elevation_gain") or 0
                if elev > max_hike_elev_m: max_hike_elev_m = elev

        # Scan Strava activities
        for act in s_acts:
            dist = act.get("distance") or 0
            dur = act.get("moving_time") or act.get("elapsed_time") or 0
            act_type = act.get("type") or ""
            
            # Running PRs
            if act_type in strava_run_types and dur > 0:
                if 4800 <= dist <= 5500:
                    if not fastest_5k or dur < fastest_5k: fastest_5k = dur
                elif 9500 <= dist <= 11000:
                    if not fastest_10k or dur < fastest_10k: fastest_10k = dur
                elif 20000 <= dist <= 23000:
                    if not fastest_half or dur < fastest_half: fastest_half = dur

            # Cycling
            if act_type in ["Ride", "VirtualRide", "EBikeRide"]:
                if dist > longest_bike_m: longest_bike_m = dist

            # Hiking
            if act_type in ["Hike", "AlpineSki"]:
                elev = act.get("total_elevation_gain") or 0
                if elev > max_hike_elev_m: max_hike_elev_m = elev

        # Format calculated PRs
        if fastest_5k: result["personal_records"]["run_5k"] = format_duration(fastest_5k)
        if fastest_10k: result["personal_records"]["run_10k"] = format_duration(fastest_10k)
        if fastest_half: result["personal_records"]["run_half"] = format_duration(fastest_half)
        if longest_bike_m > 0: result["personal_records"]["bike_longest"] = f"{int(longest_bike_m / 1000)} km"
        if max_hike_elev_m > 0: result["personal_records"]["hike_peak"] = f"{int(max_hike_elev_m)}m"

        return result
    except Exception as e:
        logger.error(f"Error calculating prepopulate data: {e}")
        return None
