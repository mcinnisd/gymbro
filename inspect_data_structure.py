import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def inspect_structure():
    print("--- Inspecting Garmin Data Structure ---")
    
    # 1. Inspect Activity Metrics Keys
    print("\n1. Activity Metrics Keys:")
    response = supabase.table("garmin_activities").select("details").neq("details", "null").limit(1).execute()
    if response.data and response.data[0].get('details'):
        details = response.data[0]['details']
        if 'metricDescriptors' in details:
            print("Metric Descriptors Keys:")
            for d in details['metricDescriptors']:
                print(f"  - Key: {d.get('key')} | Index: {d.get('metricsIndex')}")
        
        metrics = details.get('activityDetailMetrics')
        if metrics and len(metrics) > 0:
             if 'metrics' in metrics[0]:
                 print(f"Item 0 -> metrics List Sample: {str(metrics[0]['metrics'])[:200]}...")
                 # Print a few more samples to see if they are all zeros
                 for i in range(1, min(5, len(metrics))):
                     print(f"Item {i} -> metrics List Sample: {str(metrics[i]['metrics'])[:200]}...")
        else:
            print("No metrics found in details.")
    else:
        print("No activities with details found.")

    # 2. Inspect Sleep Data for HRV / Respiration / Score
    print("\n2. Sleep Data Content:")
    response = supabase.table("garmin_sleep").select("sleep_data").order("date", desc=True).limit(1).execute()
    if response.data:
        sleep_data = response.data[0].get("sleep_data")
        if isinstance(sleep_data, dict):
            print(f"Top Level Keys: {list(sleep_data.keys())}")
            
            # Check for Sleep Scores
            if "sleepScores" in sleep_data:
                 print(f"Sleep Scores: {sleep_data['sleepScores']}")
            
            # Check for HRV
            if "hrvData" in sleep_data:
                print(f"HRV Data Found (len): {len(sleep_data['hrvData']) if sleep_data['hrvData'] else 0}")
            
            # Check for Respiration in dailySleepDTO
            if "dailySleepDTO" in sleep_data:
                dto = sleep_data['dailySleepDTO']
                print(f"Avg Respiration: {dto.get('averageRespirationValue')}")
                print(f"Lowest Respiration: {dto.get('lowestRespirationValue')}")
                print(f"Highest Respiration: {dto.get('highestRespirationValue')}")
                print(f"Sleep Score (DTO): {dto.get('sleepScore')}")
                print(f"Quality: {dto.get('sleepQualityTypePK')}")
        else:
            print(f"Type: {type(sleep_data)}")

if __name__ == "__main__":
    inspect_structure()
