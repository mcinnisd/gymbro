from app.supabase_client import supabase
import json

def update_user():
    # Find user test1111
    res = supabase.table("users").select("*").eq("username", "test1111").execute()
    if not res.data:
        print("User test1111 not found")
        return

    user = res.data[0]
    goals = user.get("goals") or {}
    
    # Update to use local LLM
    goals["llm_model"] = "local"
    
    update_res = supabase.table("users").update({"goals": goals}).eq("id", user["id"]).execute()
    print(f"Updated user {user['username']} goals: {update_res.data[0]['goals']}")

if __name__ == "__main__":
    update_user()
