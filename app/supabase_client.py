# app/supabase_client.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")  # e.g., https://your-project.supabase.co
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # your API key

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
