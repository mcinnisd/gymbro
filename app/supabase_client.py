from app.config import Config
from supabase import create_client, Client

url: str = Config.SUPABASE_URL
key: str = Config.SUPABASE_KEY
mock_db: bool = Config.MOCK_DB

if mock_db:
    from app.mock_supabase import MockSupabaseClient
    supabase = MockSupabaseClient()
elif url and key:
    supabase: Client = create_client(url, key)
else:
    supabase = None
