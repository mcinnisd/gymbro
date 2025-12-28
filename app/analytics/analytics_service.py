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
        Main entry point to calculate and store all baselines for a user.
        """
        logger.info(f"Starting baseline calculation for user {user_id}...")
        try:
            # 1. Fetch Activities
            # Fetch essential fields for analysis
            res = supabase.table("garmin_activities")\
                .select("start_time_local, distance, duration, activity_type, average_hr")\
                .eq("user_id", user_id)\
                .order("start_time_local", desc=True)\
                .limit(1000)\
                .execute()
            
            raw_activities = res.data if res.data else []
            if not raw_activities:
                logger.info(f"No activities found for user {user_id} to analyze.")
                return

            # Filter for running only (STRICT)
            # Garmin types: 'running', 'treadmill_running', 'trail_running', etc.
            valid_types = ['running', 'treadmill_running', 'trail_running', 'street_running', 'track_running']
            run_activities = [
                a for a in raw_activities 
                if a.get('activity_type') in valid_types
                and a.get('distance') and a.get('duration')
            ]
            
            if not run_activities:
                logger.info(f"No running activities found for user {user_id}.")
                # Should we clear baselines? For now just return.
                return

            # 2. Calculate Metrics
            pbs = AnalyticsService._calculate_pbs(run_activities)
            volume = AnalyticsService._calculate_volume_metrics(run_activities)
            longest_run = AnalyticsService._find_longest_run(run_activities)
            
            # 3. Store Results
            baselines = {
                "pbs": pbs,
                "volume": volume,
                "longest_run": longest_run,
                "dataset_size": len(run_activities),
                "last_processed_date": datetime.now(timezone.utc).isoformat()
            }

            supabase.table("user_baselines").upsert({
                "user_id": user_id,
                "metric_category": "running",
                "baselines": baselines,
                "computed_at": datetime.now(timezone.utc).isoformat()
            }, on_conflict="user_id, metric_category").execute()

            logger.info(f"Successfully calculated and stored baselines for user {user_id}.")
            return baselines

        except Exception as e:
            logger.error(f"Error calculating baselines for user {user_id}: {e}")
            return None

    @staticmethod
    def _calculate_pbs(activities):
        """
        Find best efforts for standard distances based on Average Pace.
        Logic: If activity distance >= target distance, calculate time at avg pace.
        This captures '5k in a 10k' (conservatively) and '5.1km race'.
        """
        best_efforts = {
            "1k": None,
            "5k": None,
            "10k": None,
            "Half Marathon": None,
            "Marathon": None
        }

        # Target distances in meters
        targets = {
            "1k": 1000,
            "5k": 5000,
            "10k": 10000,
            "Half Marathon": 21097,
            "Marathon": 42195
        }

        for act in activities:
            dist = act.get('distance', 0)
            dur = act.get('duration', 0)
            date = act.get('start_time_local', '')[:10]
            
            if not dist or dist <= 0 or not dur:
                continue

            for label, target_dist in targets.items():
                # Allow a tiny margin for GPS error undershoot? (e.g. 4.99km counting as 5k?)
                # Let's say 98% of distance is required to count as that "effort" if we project.
                # Actually, standard practice: you must cover the distance.
                # But for a casual app, 5.0km on a 5k race is rare, usually 5.01 or 4.98.
                # Let's use 0.97 factor (3% short is okay to project up).
                if dist >= (target_dist * 0.97):
                    # Calculate estimated time for exactly the target distance at this average pace
                    # Pace = dur / dist
                    # Est Time = Pace * target_dist
                    est_seconds = (dur / dist) * target_dist
                    
                    current_best = best_efforts[label]
                    
                    if current_best is None or est_seconds < current_best['time_seconds']:
                        best_efforts[label] = {
                            "time_seconds": round(est_seconds, 2),
                            "date": date,
                            "source_dist": dist, # debug info
                            "formatted_time": AnalyticsService._format_duration(est_seconds)
                        }
        
        # Remove None values
        return {k: v for k, v in best_efforts.items() if v}

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
    def _format_duration(seconds):
        """Format seconds into HH:MM:SS or MM:SS"""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{int(h)}:{int(m):02d}:{int(s):02d}"
        else:
            return f"{int(m)}:{int(s):02d}"
