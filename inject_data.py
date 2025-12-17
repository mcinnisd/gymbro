from app.supabase_client import supabase
from datetime import datetime, timedelta
import json

USER_ID = 13

# Clear existing data
try:
    supabase.table("garmin_activities").delete().eq("user_id", USER_ID).execute()
    supabase.table("garmin_sleep").delete().eq("user_id", USER_ID).execute()
    print("Cleared existing data.")
except Exception as e:
    print(f"Error clearing data: {e}")

# Activities
activities = []
for i in range(10):
    date = (datetime.now() - timedelta(days=i)).isoformat()
    activities.append({
        "user_id": USER_ID,
        "activity_id": f"test_act_{i}",
        "activity_type": "running",
        "start_time_local": date,
        "distance": 5000 + (i * 100),
        "duration": 1800 + (i * 10),
        "raw_data": {
            "averageHR": 140 + i,
            "averageRunningCadenceInStepsPerMinute": 170 + (i % 5),
            "elevationGain": 50 + (i * 5),
            "activityTrainingLoad": 100 + (i * 2)
        },
        "details": {
            "metricDescriptors": [
                {"key": "directHeartRate", "unit": "bpm"},
                {"key": "directSpeed", "unit": "m/s"},
                {"key": "directCadence", "unit": "spm"},
                {"key": "directElevation", "unit": "m"}
            ],
            "activityDetailMetrics": [
                {"metrics": [140 + (j%5), 2.5 + (j%0.5), 170 + (j%3), 100 + j]} 
                for j in range(50) # 50 data points
            ]
        }
    })

try:
    supabase.table("garmin_activities").upsert(activities).execute()
    print("Activities injected.")
except Exception as e:
    print(f"Error injecting activities: {e}")

# Sleep
sleeps = []
for i in range(10):
    date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
    sleeps.append({
        "user_id": USER_ID,
        "date": date,
        "sleep_data": {
            "avgOvernightHrv": 40 + (i % 10),
            "sleepScores": {
                "overall": {
                    "value": 70 + (i % 20)
                }
            }
        }
    })

try:
    supabase.table("garmin_sleep").upsert(sleeps).execute()
    print("Sleep data injected.")
except Exception as e:
    print(f"Error injecting sleep: {e}")
