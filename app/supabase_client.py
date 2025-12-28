import os
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
mock_db: str = os.environ.get("MOCK_DB")

if mock_db == "true":
    from app.mock_supabase import MockSupabaseClient
    supabase = MockSupabaseClient()
elif url and key:
    supabase: Client = create_client(url, key)
else:
    supabase = None
