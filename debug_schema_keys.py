
import os
import sys
from dotenv import load_dotenv

# Load env before importing app modules
load_dotenv()

# Add current dir to path
sys.path.append(os.getcwd())

from app.supabase_client import supabase

def debug_keys():
    print("Fetching one daily record...")
    # Fetch where resting_hr is NOT null
    res = supabase.table("garmin_daily").select("resting_hr, stress").not_.is_("resting_hr", "null").limit(1).execute()
    
    if not res.data:
        print("No daily data found.")
        return

    row = res.data[0]
    rhr = row.get("resting_hr")
    stress = row.get("stress")
    
    print("-" * 20)
    print("RESTING HR Keys/Type:")
    if isinstance(rhr, dict):
        # Check allMetrics (usually a list)
        if 'allMetrics' in rhr:
             metrics = rhr['allMetrics']
             print(f"  allMetrics Type: {type(metrics)}")
             if isinstance(metrics, dict) and 'metricsMap' in metrics:
                 mmap = metrics['metricsMap']
                 print(f"  metricsMap Keys: {list(mmap.keys())}")
                 # Dump first key's value to see structure
                 if mmap:
                     k1 = list(mmap.keys())[0]
                     print(f"  metricsMap[{k1}]: {mmap[k1]}")

    print("-" * 20)
    print("SLEEP Check:")
    sleep_res = supabase.table("garmin_sleep").select("id", count="exact").limit(1).execute()
    print(f"Sleep Rows: {sleep_res.count}")
    if sleep_res.count > 0:
        s_data = supabase.table("garmin_sleep").select("sleep_data").limit(1).execute()
        print(f"Sleep Data Keys: {list(s_data.data[0]['sleep_data'].keys())}")
                 
        # Check groupedMetrics
        if 'groupedMetrics' in rhr:
            print(f"  groupedMetrics: {rhr['groupedMetrics']}")
    else:
        print(f"Type: {type(rhr)} Value: {rhr}")

    print("-" * 20)
    print("STRESS Keys/Type:")
    if isinstance(stress, dict):
        print(list(stress.keys()))
        # Print potential value keys
        for k in ['averageStressLevel', 'avgStressLevel', 'stressDuration', 'value']:
            if k in stress: print(f"  {k}: {stress[k]}")
    else:
        print(f"Type: {type(stress)} Value: {stress}")

if __name__ == "__main__":
    debug_keys()
