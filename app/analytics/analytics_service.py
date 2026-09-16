import logging
from datetime import datetime, timezone, timedelta
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Service for calculating user fitness baselines from raw activity data.
    """

    @staticmethod
    def calculate_baselines(user_id: str):
        """
        Main entry point to calculate and store all multi-year baselines, PRs, and efficiency curves for a user.
        """
        logger.info(f"Starting baseline calculation for user {user_id}...")
        try:
            uid_parsed = int(user_id) if str(user_id).isdigit() else user_id
            
            # 1. Fetch All Historical Activities from Garmin and Strava
            raw_activities = []
            
            # Garmin activities
            try:
                g_res = supabase.table("garmin_activities")\
                    .select("start_time_local, distance, duration, activity_type, average_hr, elevation_gain")\
                    .eq("user_id", uid_parsed)\
                    .order("start_time_local", desc=True)\
                    .limit(5000)\
                    .execute()
                if g_res.data:
                    raw_activities.extend(g_res.data)
            except Exception as ge:
                logger.warning(f"Failed fetching Garmin activities for baseline calc: {ge}")

            # Strava activities
            try:
                s_res = supabase.table("strava_activities")\
                    .select("start_date_local, distance, moving_time, elapsed_time, type, average_hr, elevation_gain")\
                    .eq("user_id", uid_parsed)\
                    .order("start_date_local", desc=True)\
                    .limit(5000)\
                    .execute()
                if s_res.data:
                    for s in s_res.data:
                        raw_activities.append({
                            "start_time_local": s.get("start_date_local"),
                            "distance": s.get("distance"),
                            "duration": s.get("moving_time") or s.get("elapsed_time"),
                            "activity_type": s.get("type"),
                            "average_hr": s.get("average_hr"),
                            "elevation_gain": s.get("elevation_gain")
                        })
            except Exception as se:
                logger.warning(f"Failed fetching Strava activities for baseline calc: {se}")
            
            if not raw_activities:
                logger.info(f"No activities found for user {user_id} to analyze.")
                return None

            # Filter for running only
            valid_run_types = ['running', 'treadmill_running', 'trail_running', 'street_running', 'track_running', 'run']
            run_activities = [
                a for a in raw_activities 
                if str(a.get('activity_type', '')).lower() in valid_run_types
                and a.get('distance') and a.get('duration')
            ]

            # Filter for cycling
            valid_cycle_types = ['cycling', 'biking', 'ride', 'virtualride', 'gravel_cycling', 'road_biking', 'mountain_biking']
            cycle_activities = [
                a for a in raw_activities
                if str(a.get('activity_type', '')).lower() in valid_cycle_types
                and a.get('distance') and a.get('duration')
            ]

            # 2. Calculate Running Metrics & PRs
            pbs = AnalyticsService._calculate_pbs(run_activities) if run_activities else {}
            volume = AnalyticsService._calculate_volume_metrics(run_activities) if run_activities else {}
            longest_run = AnalyticsService._find_longest_run(run_activities) if run_activities else None
            
            # 3. Calculate Cycling Milestones
            cycling_milestones = AnalyticsService._calculate_cycling_milestones(cycle_activities) if cycle_activities else None

            # 4. Calculate Multi-Year Aerobic Efficiency Curves
            aerobic_efficiency = AnalyticsService._calculate_aerobic_efficiency_by_year(run_activities) if run_activities else {}

            # 5. Store Results in user_baselines table
            baselines = {
                "pbs": pbs,
                "volume": volume,
                "longest_run": longest_run,
                "cycling": cycling_milestones,
                "aerobic_efficiency_by_year": aerobic_efficiency,
                "dataset_size": len(raw_activities),
                "last_processed_date": datetime.now(timezone.utc).isoformat()
            }

            supabase.table("user_baselines").upsert({
                "user_id": uid_parsed,
                "metric_category": "running",
                "baselines": baselines,
                "computed_at": datetime.now(timezone.utc).isoformat()
            }, on_conflict="user_id, metric_category").execute()

            # 6. Update user's goals JSON with discovered PRs and Milestones for immediate profile access
            try:
                user_res = supabase.table("users").select("goals").eq("id", uid_parsed).execute()
                if user_res.data:
                    goals = user_res.data[0].get("goals") or {}
                    if pbs:
                        goals["personal_records"] = pbs
                    if cycling_milestones:
                        goals["cycling_milestones"] = cycling_milestones
                    if aerobic_efficiency:
                        goals["aerobic_efficiency_by_year"] = aerobic_efficiency
                    supabase.table("users").update({"goals": goals}).eq("id", uid_parsed).execute()
            except Exception as ue:
                logger.warning(f"Could not update user goals with PRs: {ue}")

            logger.info(f"Successfully calculated and stored longitudinal baselines for user {user_id}.")
            return baselines

        except Exception as e:
            logger.error(f"Error calculating baselines for user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _calculate_pbs(activities):
        """
        Find best efforts for standard distances based on Average Pace.
        Includes 1k, 1 Mile, 5k, 10k, Half Marathon, and Marathon.
        """
        best_efforts = {
            "1k": None,
            "1 Mile": None,
            "5k": None,
            "10k": None,
            "Half Marathon": None,
            "Marathon": None
        }

        # Target distances in meters
        targets = {
            "1k": 1000,
            "1 Mile": 1609.34,
            "5k": 5000,
            "10k": 10000,
            "Half Marathon": 21097.5,
            "Marathon": 42195
        }

        for act in activities:
            dist = act.get('distance', 0)
            dur = act.get('duration', 0)
            date_str = str(act.get('start_time_local', ''))[:10]
            
            if not dist or dist <= 0 or not dur or dur <= 0:
                continue

            for label, target_dist in targets.items():
                if dist >= (target_dist * 0.97):
                    est_seconds = (dur / dist) * target_dist
                    current_best = best_efforts[label]
                    
                    if current_best is None or est_seconds < current_best['time_seconds']:
                        best_efforts[label] = {
                            "time_seconds": round(est_seconds, 2),
                            "date": date_str,
                            "source_dist": dist,
                            "formatted_time": AnalyticsService._format_duration(est_seconds)
                        }
        
        return {k: v for k, v in best_efforts.items() if v}

    @staticmethod
    def _calculate_cycling_milestones(activities):
        """
        Extracts cycling milestones (longest ride km, max elevation gain, longest duration).
        """
        if not activities:
            return None
        max_dist = max((a.get('distance') or 0) for a in activities)
        max_elev = max((a.get('elevation_gain') or 0) for a in activities)
        max_dur = max((a.get('duration') or 0) for a in activities)
        return {
            "longest_ride_km": round(max_dist / 1000.0, 2),
            "max_elevation_m": round(float(max_elev), 2),
            "longest_duration_hours": round(max_dur / 3600.0, 2),
            "total_rides": len(activities)
        }

    @staticmethod
    def _calculate_aerobic_efficiency_by_year(activities):
        """
        Calculates multi-year aerobic efficiency trends (speed m/s / avg_hr * 1000, pace min/km vs HR).
        """
        yearly_data = {}
        for act in activities:
            dist = act.get('distance') or 0
            dur = act.get('duration') or 0
            hr = act.get('average_hr') or 0
            date_str = str(act.get('start_time_local') or '')
            if dist > 500 and dur > 180 and hr > 80 and date_str:
                year = date_str[:4]
                if year not in yearly_data:
                    yearly_data[year] = {
                        "efficiency_scores": [],
                        "paces": [],
                        "hrs": [],
                        "total_distance_m": 0,
                        "total_duration_s": 0,
                        "count": 0
                    }
                speed_m_s = dist / dur
                eff_score = (speed_m_s / hr) * 1000.0
                pace_min_km = (dur / (dist / 1000.0)) / 60.0
                yearly_data[year]["efficiency_scores"].append(eff_score)
                yearly_data[year]["paces"].append(pace_min_km)
                yearly_data[year]["hrs"].append(hr)
                yearly_data[year]["total_distance_m"] += dist
                yearly_data[year]["total_duration_s"] += dur
                yearly_data[year]["count"] += 1
        
        result = {}
        for yr, d in sorted(yearly_data.items()):
            cnt = d["count"]
            if cnt > 0:
                result[yr] = {
                    "efficiency_score": round(sum(d["efficiency_scores"]) / cnt, 2),
                    "avg_pace_min_km": round(sum(d["paces"]) / cnt, 2),
                    "avg_hr": round(sum(d["hrs"]) / cnt, 1),
                    "total_km": round(d["total_distance_m"] / 1000.0, 1),
                    "total_hours": round(d["total_duration_s"] / 3600.0, 1),
                    "activity_count": cnt
                }
        return result


    @staticmethod
    def _find_longest_run(activities):
        """
        Find the single longest run by distance.
        """
        if not activities:
            return None
            
        longest = max(activities, key=lambda x: x['distance'])
        dist_km = longest['distance'] / 1000.0
        
        return {
            "distance_km": round(dist_km, 2),
            "date": longest['start_time_local'][:10],
            "duration": longest['duration'],
            "formatted_time": AnalyticsService._format_duration(longest['duration'])
        }

    @staticmethod
    def _calculate_volume_metrics(activities):
        """
        Calculate weekly distances and averages using standard Python.
        """
        if not activities:
            return {
                "avg_weekly_dist_4w": 0, 
                "avg_weekly_dist_12w": 0, 
                "max_volume_week": 0, 
                "current_streak_weeks": 0
            }

        # Group by ISO week (Year-Week)
        weekly_sums = {}
        for act in activities:
            try:
                dt = datetime.fromisoformat(act['start_time_local'])
                year, week, _ = dt.isocalendar()
                key = (year, week)
                
                dist_km = act['distance'] / 1000.0
                weekly_sums[key] = weekly_sums.get(key, 0) + dist_km
            except (ValueError, TypeError):
                continue

        # Sort weeks descending (newest first)
        sorted_weeks = sorted(weekly_sums.keys(), reverse=True)
        
        # Create a contiguous list of volumes for recent weeks if we want accurate streaks/avgs including zeros?
        # For simplicity, let's just use the weeks we have data for, OR fill gaps.
        # Filling gaps is better for streak/avg.
        
        if not sorted_weeks:
            return {"avg_weekly_dist_4w": 0, "avg_weekly_dist_12w": 0, "max_volume_week": 0, "current_streak_weeks": 0}

        latest_year, latest_week = sorted_weeks[0]
        # Generate last 12 weeks keys back from latest
        
        last_12_vols = []
        current_y, current_w = latest_year, latest_week
        
        for _ in range(12):
            vol = weekly_sums.get((current_y, current_w), 0)
            last_12_vols.append(vol)
            
            # Decrement week
            current_w -= 1
            if current_w < 1:
                current_y -= 1
                current_w = 52 # approx (datetime logic better but this suffices for simple stats)
                # Correct way using date math:
                # dt = date.fromisocalendar(current_y, current_w, 1) - timedelta(days=7) ...
        
        last_4_vols = last_12_vols[:4]
        
        avg_4 = sum(last_4_vols) / 4
        avg_12 = sum(last_12_vols) / 12
        max_vol = max(weekly_sums.values()) if weekly_sums else 0
        
        # Streak: Count backwards from latest week (or today's week?)
        # If latest activity is weeks ago, streak should be 0.
        # Let's verify if "latest_week" is close to "now".
        now = datetime.now()
        now_y, now_w, _ = now.isocalendar()
        
        streak = 0
        # Check gap between now and latest activity
        # If gap > 1 week, streak is broken.
        # Simple approximated check:
        gap = (now_y - latest_year) * 52 + (now_w - latest_week)
        if gap > 1:
            streak = 0
        else:
            # Count consecutive non-zero in last_12_vols (which starts from latest activity week)
            for v in last_12_vols:
                if v > 1.0: # 1km threshold
                    streak += 1
                else:
                    break
        
        return {
            "avg_weekly_dist_4w": round(avg_4, 2),
            "avg_weekly_dist_12w": round(avg_12, 2),
            "max_volume_week":     round(max_vol, 2),
            "current_streak_weeks": streak
        }

    @staticmethod
    def _calculate_streak(weekly_series):
       # Deprecated helper, logic moved inline
       pass

    @staticmethod
    def get_aggregated_metrics(user_id: str, days=90):
        """
        Aggregates metrics for all available sports over the last N days.
        Returns a dictionary keyed by sport.
        """
        from datetime import datetime, timedelta, timezone
        
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        
        # 1. Fetch Activities
        # We need raw_data too for detailed parsing of swim/bike specifics if standard cols aren't enough.
        # But standard cols + activity_type covers a lot.
        res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("start_time_local", start_date)\
            .order("start_time_local", desc=True)\
            .execute()
            
        activities = res.data or []
        
        # 2. Group by Sport
        grouped = {
            "running": [], "cycling": [], "swimming": [], "strength": [], "hiking": [], "walking": [], "other": []
        }
        
        for act in activities:
            atype = act.get('activity_type', 'other').lower()
            if 'running' in atype: grouped['running'].append(act)
            elif 'cycling' in atype or 'biking' in atype: grouped['cycling'].append(act)
            elif 'swimming' in atype: grouped['swimming'].append(act)
            elif 'strength' in atype or 'weight' in atype: grouped['strength'].append(act)
            elif 'hiking' in atype: grouped['hiking'].append(act)
            elif 'walking' in atype: grouped['walking'].append(act)
            else: grouped['other'].append(act)

        # 2b. Calculate Global Stats (Breakdown & Weekly Volume)
        breakdown = {}
        weekly_volume = {}
        
        for act in activities:
            # Breakdown
            atype = act.get('activity_type', 'other').lower()
            if atype not in breakdown:
                breakdown[atype] = {"count": 0, "distance": 0, "duration": 0}
            breakdown[atype]["count"] += 1
            breakdown[atype]["distance"] += (act.get("distance") or 0)
            breakdown[atype]["duration"] += (act.get("duration") or 0)
            
            # Weekly Volume
            try:
                dt = datetime.fromisoformat(act['start_time_local'])
                year, week, _ = dt.isocalendar()
                week_key = f"{year}-{week:02d}"
                
                if week_key not in weekly_volume:
                    weekly_volume[week_key] = {"distance": 0, "duration": 0}
                
                weekly_volume[week_key]["distance"] += (act.get("distance") or 0)
                weekly_volume[week_key]["duration"] += (act.get("duration") or 0)
            except: pass

        # Convert Weekly Volume keys from YYYY-WW to Start Date (ISO) for better UI
        # Sort by key first to handle date math
        sorted_weeks = sorted(weekly_volume.keys())
        formatted_volume = {}
        for k in sorted_weeks:
            try:
                # k is "2023-45"
                y, w = map(int, k.split('-'))
                # Get Monday of that week
                from datetime import date
                # text replacement for date.fromisocalendar
                monday = date.fromisocalendar(y, w, 1).isoformat()
                formatted_volume[monday] = weekly_volume[k]
            except:
                formatted_volume[k] = weekly_volume[k] # Fallback

        # 3. Calculate Metrics per Sport
        response = {
            "breakdown": breakdown,
            "weekly_volume": formatted_volume, 
            "sports": {}
        }
        
        if grouped['running']:
            response['sports']['running'] = AnalyticsService._analyze_running(grouped['running'], user_id)
            
        if grouped['cycling']:
            response['sports']['cycling'] = AnalyticsService._analyze_cycling(grouped['cycling'])
            
        if grouped['swimming']:
            response['sports']['swimming'] = AnalyticsService._analyze_swimming(grouped['swimming'])
            
        if grouped['strength']:
            response['sports']['strength'] = AnalyticsService._analyze_strength(grouped['strength'])
            
        if grouped['hiking']:
            response['sports']['hiking'] = AnalyticsService._analyze_simple_distance(grouped['hiking'], "Hiking")

        # 4. Wellness (Standard for everyone)
        response['wellness'] = AnalyticsService._analyze_wellness(user_id, start_date)
        
        # 5. Raw Activities for Live UI Charts
        raw_acts_list = []
        for a in activities:
            dist = a.get("distance") or 0
            dur = a.get("duration") or 0
            dist_km = round(dist / 1000.0, 2) if dist > 100 else round(dist, 2)
            dur_min = round(dur / 60.0, 1) if dur > 300 else round(dur, 1)
            pace_min_km = round(dur_min / dist_km, 2) if dist_km > 0.2 else 0
            raw_acts_list.append({
                "id": a.get("activity_id") or a.get("id"),
                "title": a.get("activity_name") or "Workout",
                "date": str(a.get("start_time_local") or "")[:10],
                "type": a.get("activity_type") or "run",
                "distance_km": dist_km,
                "duration_min": dur_min,
                "avg_hr": a.get("average_hr") or 0,
                "max_hr": a.get("max_hr") or 0,
                "pace_min_km": pace_min_km,
                "elevation_gain": a.get("elevation_gain") or 0
            })
        response['raw_activities'] = raw_acts_list

        return response

    @staticmethod
    def _extract_val(val):
        """Helper to safely extract scalar from potential object/list garbage."""
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, dict):
            # Try common keys
            return val.get('value') or val.get('min') or 0
        return 0

    @staticmethod
    def _analyze_running(activities, user_id):
        # Existing logic recycled + new trends
        summary = AnalyticsService._basic_summary(activities)
        
        # Efficiency Trend
        efficiency = []
        for act in activities:
            speed = act.get('average_speed')
            hr = act.get('average_hr')
            if speed and hr and float(hr) > 0:
                efficiency.append({
                    "date": act['start_time_local'][:10],
                    "val": (float(speed) * 100) / float(hr),
                    "speed": float(speed),
                    "hr": float(hr)
                })
        efficiency.reverse()
        
        # Fetch PRs from Baselines (if they exist)
        pbs = {}
        try:
             res = supabase.table("user_baselines").select("baselines").eq("user_id", user_id).eq("metric_category", "running").execute()
             if res.data:
                 pbs = res.data[0].get("baselines", {}).get("pbs", {})
        except: pass
        
        return {
            **summary,
            "trends": {"efficiency": efficiency},
            "pbs": pbs
        }

    @staticmethod
    def _analyze_cycling(activities):
        summary = AnalyticsService._basic_summary(activities)
        
        # Check for Power Data in raw_data/details? 
        # For now, simplistic speed analysis.
        # Future: Parse raw_data['connectIQMeasurements'] or similar for power.
        
        return {
            **summary,
            "trends": {}
            # Placeholder for Power Curve
        }

    @staticmethod
    def _analyze_swimming(activities):
        # Basic: Dist, Duration, Pace
        total_dist = sum(a.get('distance') or 0 for a in activities)
        total_time = sum(a.get('duration') or 0 for a in activities)
        count = len(activities)
        
        # SWOLF average (if available in raw_data)
        # Garmin raw often has 'averageSwolf' key.
        swolf_vals = []
        for a in activities:
            raw = a.get('raw_data') or {}
            val = raw.get('averageSwolf')
            if val: swolf_vals.append(val)
            
        avg_swolf = sum(swolf_vals)/len(swolf_vals) if swolf_vals else None
        
        return {
            "total_distance_m": total_dist,
            "total_duration_s": total_time,
            "count": count,
            "avg_swolf": avg_swolf,
            "recent_sessions": [
                {"date": a['start_time_local'][:10], "dist": a.get('distance'), "pace_100m": (a.get('duration')/a.get('distance')*100) if a.get('distance') else 0}
                for a in activities[:5]
            ]
        }

    @staticmethod
    def _analyze_strength(activities):
        count = len(activities)
        total_dur = sum(a.get('duration') or 0 for a in activities)
        avg_hr = sum(a.get('average_hr') or 0 for a in activities) / count if count else 0
        
        return {
            "count": count,
            "total_duration_s": total_dur,
            "avg_hr": avg_hr,
            "freq_per_week": count / 12.0 # approx for 90 days (12 weeks)
        }
        
    @staticmethod
    def _analyze_simple_distance(activities, label):
        return AnalyticsService._basic_summary(activities)

    @staticmethod
    def _analyze_wellness(user_id, start_date):
        # Merge biometrics from biometrics_daily, garmin_daily, and garmin_sleep by date
        date_map = {}

        # 1. Fetch biometrics_daily
        try:
            bio_res = supabase.table("biometrics_daily")\
                .select("*")\
                .eq("user_id", user_id)\
                .gte("date", start_date)\
                .order("date")\
                .execute()
            for row in (bio_res.data or []):
                dt = row.get("date")
                if dt:
                    date_map[dt] = {
                        "date": dt,
                        "rhr": row.get("resting_hr"),
                        "hrv": row.get("hrv"),
                        "sleep_score": row.get("sleep_score"),
                        "sleep_hours": row.get("sleep_hours"),
                        "stress": row.get("stress_level"),
                        "vo2_max": row.get("vo2_max"),
                        "fitness_age": row.get("fitness_age"),
                        "body_battery": row.get("body_battery"),
                        "sleep_stages": row.get("sleep_stages"),
                        "training_status": row.get("training_status"),
                        "acute_load": row.get("acute_load"),
                        "spo2": row.get("spo2"),
                        "respiration": row.get("respiration")
                    }
        except Exception:
            pass

        # 2. Fetch garmin_daily
        try:
            daily_res = supabase.table("garmin_daily")\
                .select("*")\
                .eq("user_id", user_id)\
                .gte("date", start_date)\
                .order("date")\
                .execute()
            for row in (daily_res.data or []):
                dt = row.get("date")
                if not dt: continue
                if dt not in date_map: date_map[dt] = {"date": dt}
                if not date_map[dt].get("rhr") and row.get("resting_hr"):
                    date_map[dt]["rhr"] = AnalyticsService._extract_val(row.get("resting_hr"))
                if not date_map[dt].get("stress") and row.get("stress"):
                    date_map[dt]["stress"] = AnalyticsService._extract_val(row.get("stress"))
        except Exception:
            pass

        # 3. Fetch garmin_sleep
        try:
            sleep_res = supabase.table("garmin_sleep")\
                .select("*")\
                .eq("user_id", user_id)\
                .gte("date", start_date)\
                .order("date")\
                .execute()
            for row in (sleep_res.data or []):
                dt = row.get("date")
                if not dt: continue
                if dt not in date_map: date_map[dt] = {"date": dt}
                sdata = row.get("sleep_data") or {}
                if isinstance(sdata, dict):
                    dto = sdata.get("dailySleepDTO") or {}
                    scores = dto.get("sleepScores") or {}
                    overall = scores.get("overall") or {} if isinstance(scores, dict) else {}
                    score_val = overall.get("value") if isinstance(overall, dict) else None
                    if not score_val:
                        score_val = sdata.get("sleepQualityScore") or sdata.get("overallSleepScore")
                    sec = dto.get("sleepTimeSeconds") or sdata.get("totalSleepSeconds") or 0
                    if score_val and not date_map[dt].get("sleep_score"):
                        date_map[dt]["sleep_score"] = score_val
                    if sec > 0 and not date_map[dt].get("sleep_hours"):
                        date_map[dt]["sleep_hours"] = round(sec / 3600.0, 1)

                    if not date_map[dt].get("sleep_stages"):
                        deep_sec = dto.get("deepSleepSeconds")
                        rem_sec = dto.get("remSleepSeconds")
                        light_sec = dto.get("lightSleepSeconds")
                        awake_sec = dto.get("awakeSleepSeconds")
                        if any(x is not None for x in [deep_sec, rem_sec, light_sec, awake_sec]):
                            date_map[dt]["sleep_stages"] = {
                                "deep": deep_sec or 0,
                                "rem": rem_sec or 0,
                                "light": light_sec or 0,
                                "awake": awake_sec or 0
                            }
        except Exception:
            pass

        rhr_trend = []
        hrv_trend = []
        sleep_trend = []
        stress_trend = []
        training_load_trend = []
        vo2_max_trend = []
        body_battery_trend = []
        sleep_stage_trend = []
        spo2_trend = []
        respiration_trend = []

        latest_training_status = None
        latest_vo2_max = None
        latest_fitness_age = None
        latest_acute_load = None

        for date_str in sorted(date_map.keys()):
            d = date_map[date_str]
            rhr = AnalyticsService._extract_val(d.get('rhr'))
            if rhr > 0:
                rhr_trend.append({"date": date_str, "val": rhr})

            hrv = AnalyticsService._extract_val(d.get('hrv'))
            if hrv > 0:
                hrv_trend.append({"date": date_str, "val": hrv})

            sleep_sc = AnalyticsService._extract_val(d.get('sleep_score'))
            sleep_hr = AnalyticsService._extract_val(d.get('sleep_hours'))
            if sleep_sc > 0 or sleep_hr > 0:
                sleep_val = sleep_sc if sleep_sc > 0 else round(sleep_hr * 10)
                sleep_trend.append({"date": date_str, "val": sleep_val, "hours": sleep_hr})

            stress = AnalyticsService._extract_val(d.get('stress'))
            if stress > 0:
                stress_trend.append({"date": date_str, "val": stress})

            tload = AnalyticsService._extract_val(d.get('training_load') or d.get('load'))
            if tload > 0:
                training_load_trend.append({"date": date_str, "val": tload})

            vo2 = AnalyticsService._extract_val(d.get('vo2_max'))
            if vo2 > 0:
                vo2_max_trend.append({"date": date_str, "val": vo2})
                latest_vo2_max = vo2

            bb = AnalyticsService._extract_val(d.get('body_battery'))
            if bb > 0:
                body_battery_trend.append({"date": date_str, "val": bb})

            stages = d.get('sleep_stages')
            if isinstance(stages, dict):
                sleep_stage_trend.append({
                    "date": date_str,
                    "deep": stages.get("deep", 0),
                    "rem": stages.get("rem", 0),
                    "light": stages.get("light", 0),
                    "awake": stages.get("awake", 0)
                })

            spo2 = AnalyticsService._extract_val(d.get('spo2'))
            if spo2 > 0:
                spo2_trend.append({"date": date_str, "val": spo2})

            resp = AnalyticsService._extract_val(d.get('respiration'))
            if resp > 0:
                respiration_trend.append({"date": date_str, "val": resp})

            ts = d.get('training_status')
            if ts:
                latest_training_status = ts

            fa = AnalyticsService._extract_val(d.get('fitness_age'))
            if fa > 0:
                latest_fitness_age = fa

            al = AnalyticsService._extract_val(d.get('acute_load'))
            if al > 0:
                latest_acute_load = al

        # If training_load_trend is empty from daily records, derive from activities
        if not training_load_trend:
            try:
                act_res = supabase.table("garmin_activities")\
                    .select("start_time_local, duration, average_hr")\
                    .eq("user_id", user_id)\
                    .gte("start_time_local", start_date)\
                    .execute()
                acts = act_res.data or []
                daily_loads = {}
                for a in acts:
                    st = a.get("start_time_local", "")[:10]
                    dur = a.get("duration", 0) or 0
                    hr = a.get("average_hr", 130) or 130
                    load_val = round((dur / 60) * (hr / 100))
                    if st:
                        daily_loads[st] = daily_loads.get(st, 0) + load_val
                training_load_trend = [{"date": k, "val": v} for k, v in sorted(daily_loads.items())]
            except Exception:
                pass

        primary_src = "garmin"
        if date_map:
            first_key = next(iter(date_map))
            if isinstance(date_map[first_key], dict) and date_map[first_key].get("source"):
                primary_src = date_map[first_key].get("source")

        return {
            "rhr_trend": rhr_trend,
            "hrv_trend": hrv_trend,
            "sleep_trend": sleep_trend,
            "stress_trend": stress_trend,
            "training_load_trend": training_load_trend,
            "vo2_max_trend": vo2_max_trend,
            "body_battery_trend": body_battery_trend,
            "sleep_stage_trend": sleep_stage_trend,
            "spo2_trend": spo2_trend,
            "respiration_trend": respiration_trend,
            "training_status_summary": latest_training_status or "NO_DATA",
            "vo2_max": latest_vo2_max,
            "fitness_age": latest_fitness_age,
            "training_status": latest_training_status,
            "acute_load": latest_acute_load,
            "primary_source": primary_src
        }

    @staticmethod
    def _basic_summary(activities):
        count = len(activities)
        dist = sum(a.get('distance') or 0 for a in activities)
        dur = sum(a.get('duration') or 0 for a in activities)
        elev = sum(a.get('elevation_gain') or 0 for a in activities)
        
        return {
            "count": count,
            "total_distance": dist,
            "total_duration": dur,
            "total_elevation": elev,
            "avg_distance": dist / count if count else 0
        }

    @staticmethod
    def _format_duration(seconds):
        """Format seconds into HH:MM:SS or MM:SS"""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{int(h)}:{int(m):02d}:{int(s):02d}"
        else:
            return f"{int(m)}:{int(s):02d}"
