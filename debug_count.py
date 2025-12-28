
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: credentials missing")
    exit(1)

supabase: Client = create_client(url, key)

try:
    # Just fetch count
    res = supabase.table("garmin_activities").select("id", count="exact").execute()
    print(f"Total Activities in DB: {len(res.data)}")
    
    # Check if there are old ones
    if res.data:
        dates = sorted([r['start_time_local'] for r in supabase.table("garmin_activities").select("start_time_local").execute().data])
        print(f"Oldest: {dates[0]}")
        print(f"Newest: {dates[-1]}")

except Exception as e:
    print(f"Error: {e}")
