#!/usr/bin/env python3
"""
Context Verification Script
Verifies that context data matches actual database values.
Run this to debug any discrepancies in chat responses.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.supabase_client import supabase

def get_user_id(username="bigred"):
    """Get user ID by username."""
    res = supabase.table("users").select("id").eq("username", username).execute()
    return res.data[0]["id"] if res.data else None

def verify_activities(user_id, days=30):
    """Verify activity data and check filtering."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    result = supabase.table("garmin_activities")\
        .select("activity_type, distance, duration, average_hr, start_time_local")\
        .eq("user_id", user_id)\
        .gte("start_time_local", cutoff)\
        .order("start_time_local", desc=True)\
        .execute()
    
    activities = result.data or []
    
    print(f"\n{'='*60}")
    print(f"ACTIVITIES (Last {days} days)")
    print(f"{'='*60}")
    
    running_dist = 0
    running_dur = 0
    running_count = 0
    other_activities = []
    
    for a in activities:
        atype = a.get("activity_type", "unknown")
        dist_km = (a.get("distance") or 0) / 1000
        dur_min = (a.get("duration") or 0) / 60
        date = a.get("start_time_local", "")[:10]
        
        is_running = "running" in atype.lower()
        
        if is_running:
            running_dist += dist_km
            running_dur += dur_min
            running_count += 1
            print(f"  ✓ [RUN] {date}: {atype} - {dist_km:.2f} km in {dur_min:.1f} min")
        else:
            other_activities.append((date, atype, dist_km))
    
    print(f"\n--- Non-Running Activities ---")
    for date, atype, dist in other_activities:
        print(f"  ✗ {date}: {atype} - {dist:.2f} km")
    
    print(f"\n--- Running Totals ---")
    print(f"  Run count: {running_count}")
    print(f"  Total distance: {running_dist:.1f} km")
    print(f"  Total duration: {running_dur:.1f} min")
    if running_count > 0:
        print(f"  Avg distance per run: {running_dist/running_count:.1f} km")
        print(f"  Avg pace: {running_dur/running_dist:.2f} min/km" if running_dist > 0 else "  Avg pace: N/A")
    
    return {
        "running_count": running_count,
        "running_dist_km": running_dist,
        "running_dur_min": running_dur
    }

def verify_health_data(user_id, days=7):
    """Verify health/sleep data."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # Get sleep data
    sleep_res = supabase.table("garmin_sleep")\
        .select("date, sleep_data")\
        .eq("user_id", user_id)\
        .gte("date", cutoff)\
        .order("date", desc=True)\
        .execute()
    
    # Get daily data for RHR
    daily_res = supabase.table("garmin_daily")\
        .select("date, resting_hr")\
        .eq("user_id", user_id)\
        .gte("date", cutoff)\
        .order("date", desc=True)\
        .execute()
    
    print(f"\n{'='*60}")
    print(f"HEALTH DATA (Last {days} days)")
    print(f"{'='*60}")
    
    hrv_values = []
    sleep_hours = []
    rhr_values = []
    
    print("\n--- Sleep/HRV Data ---")
    for s in sleep_res.data or []:
        sd = s.get("sleep_data") or {}
        hrv = sd.get("avgOvernightHrv")
        sleep_sec = sd.get("sleepTimeSeconds")
        sleep_h = sleep_sec / 3600 if sleep_sec else None
        
        print(f"  {s['date']}: HRV={hrv}, Sleep={sleep_h:.1f}h" if sleep_h else f"  {s['date']}: HRV={hrv}")
        
        if hrv:
            hrv_values.append(hrv)
        if sleep_h:
            sleep_hours.append(sleep_h)
    
    print("\n--- RHR Data ---")
    for d in daily_res.data or []:
        rhr = d.get("resting_hr")
        rhr_val = None
        if isinstance(rhr, int) and rhr > 0:
            rhr_val = rhr
        elif isinstance(rhr, dict) and rhr.get("restingHeartRate"):
            rhr_val = rhr["restingHeartRate"]
        
        if rhr_val:
            rhr_values.append(rhr_val)
            print(f"  {d['date']}: RHR={rhr_val}")
    
    print(f"\n--- Health Averages ---")
    if hrv_values:
        print(f"  Avg HRV: {sum(hrv_values)/len(hrv_values):.1f} ms (from {len(hrv_values)} days)")
    if sleep_hours:
        print(f"  Avg Sleep: {sum(sleep_hours)/len(sleep_hours):.1f} hours")
    if rhr_values:
        print(f"  Avg RHR: {sum(rhr_values)/len(rhr_values):.0f} bpm")
    
    return {
        "avg_hrv": sum(hrv_values)/len(hrv_values) if hrv_values else None,
        "avg_sleep": sum(sleep_hours)/len(sleep_hours) if sleep_hours else None,
        "avg_rhr": sum(rhr_values)/len(rhr_values) if rhr_values else None
    }

def verify_yoy_data(user_id):
    """Verify year-over-year comparison data."""
    now = datetime.now()
    
    # Current 30 days
    current_start = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # Same period last year
    last_year = now.replace(year=now.year - 1)
    ly_start = (last_year - timedelta(days=30)).strftime('%Y-%m-%d')
    ly_end = last_year.strftime('%Y-%m-%d')
    
    # Current period
    current_res = supabase.table("garmin_activities")\
        .select("activity_type, distance")\
        .eq("user_id", user_id)\
        .gte("start_time_local", current_start)\
        .execute()
    
    # Last year period
    ly_res = supabase.table("garmin_activities")\
        .select("activity_type, distance")\
        .eq("user_id", user_id)\
        .gte("start_time_local", ly_start)\
        .lte("start_time_local", ly_end)\
        .execute()
    
    def calc_running(activities):
        running = [a for a in activities if "running" in (a.get("activity_type") or "").lower()]
        total_dist = sum(a.get("distance") or 0 for a in running) / 1000
        return len(running), total_dist
    
    current_count, current_dist = calc_running(current_res.data or [])
    ly_count, ly_dist = calc_running(ly_res.data or [])
    
    print(f"\n{'='*60}")
    print(f"YEAR-OVER-YEAR COMPARISON")
    print(f"{'='*60}")
    print(f"Current period: {current_start} to {now.strftime('%Y-%m-%d')}")
    print(f"Last year period: {ly_start} to {ly_end}")
    print(f"\n  This year: {current_count} runs, {current_dist:.1f} km")
    print(f"  Last year: {ly_count} runs, {ly_dist:.1f} km")
    
    if ly_dist > 0:
        change = ((current_dist - ly_dist) / ly_dist) * 100
        print(f"\n  Distance change: {change:+.1f}%")
    
    return {
        "current_runs": current_count,
        "current_dist": current_dist,
        "ly_runs": ly_count,
        "ly_dist": ly_dist
    }

def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "bigred"
    
    print(f"\n{'#'*60}")
    print(f"# CONTEXT VERIFICATION FOR USER: {username}")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")
    
    user_id = get_user_id(username)
    if not user_id:
        print(f"ERROR: User '{username}' not found")
        return
    
    print(f"\nUser ID: {user_id}")
    
    # Verify all data sources
    activity_data = verify_activities(user_id, days=30)
    health_data = verify_health_data(user_id, days=7)
    yoy_data = verify_yoy_data(user_id)
    
    print(f"\n{'='*60}")
    print("SUMMARY - Use these values to verify context accuracy")
    print(f"{'='*60}")
    print(f"Activities (30 days): {activity_data['running_count']} runs, {activity_data['running_dist_km']:.1f} km")
    print(f"Health (7 days): HRV={health_data['avg_hrv']:.1f if health_data['avg_hrv'] else 'N/A'}, RHR={health_data['avg_rhr']:.0f if health_data['avg_rhr'] else 'N/A'}")
    print(f"YoY: This year {yoy_data['current_dist']:.1f}km vs Last year {yoy_data['ly_dist']:.1f}km")
    
if __name__ == "__main__":
    main()
