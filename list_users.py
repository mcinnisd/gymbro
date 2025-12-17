from app.supabase_client import supabase

res = supabase.table("users").select("id, username").execute()
for user in res.data:
    print(f"ID: {user['id']}, Username: {user['username']}")
