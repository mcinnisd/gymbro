import os
import logging
import json
from app import create_app
from app.supabase_client import supabase
from flask_jwt_extended import create_access_token
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_coach_flow():
    app = create_app()
    with app.app_context():
        # 1. Get Test User
        test_username = "garmin_integration_user"
        res = supabase.table("users").select("*").eq("username", test_username).execute()
        if not res.data:
            logger.error(f"Test user {test_username} not found. Run verify_full_stack.py first.")
            return
        user = res.data[0]
        user_id = user["id"]
        logger.info(f"User ID: {user_id}")

        # 2. Generate Token
        # We need a token to call the endpoints because they are @jwt_required
        # But we can't easily make a request to the app without running the server.
        # Instead, we can call the view functions directly if we mock the request context and jwt.
        # OR, simpler: just call the logic directly or use app.test_client().
        
        client = app.test_client()
        token = create_access_token(identity=str(user_id))
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Start Interview
        logger.info("--- Testing /coach/start_interview ---")
        resp = client.post("/coach/start_interview", headers=headers)
        if resp.status_code != 200:
            logger.error(f"Start Interview Failed: {resp.json}")
            return
        
        data = resp.json
        chat_id = data["chat_id"]
        questions = data["questions"]
        logger.info(f"Interview Started. Chat ID: {chat_id}")
        logger.info(f"Questions Generated:\n{questions[:200]}...") # Print first 200 chars

        # 4. Simulate User Response (Mock)
        # We need to add a user message to the chat so generate_plan has something to work with.
        logger.info("--- Simulating User Response ---")
        user_msg = {
            "sender": "user",
            "content": "I want to run a marathon in 4 hours. I can train 4 days a week.",
            "timestamp": "2023-01-01T12:00:00Z" # Mock timestamp
        }
        # Fetch chat first to append
        chat_res = supabase.table("chats").select("*").eq("id", chat_id).execute()
        chat = chat_res.data[0]
        messages = chat["messages"] + [user_msg]
        
        supabase.table("chats").update({"messages": messages}).eq("id", chat_id).execute()
        logger.info("User response added to chat.")

        # 5. Generate Plan
        logger.info("--- Testing /coach/generate_plan ---")
        resp = client.post("/coach/generate_plan", headers=headers, json={"chat_id": chat_id})
        if resp.status_code != 200:
            logger.error(f"Generate Plan Failed: {resp.json}")
            return
        
        plan = resp.json["plan"]
        logger.info("Plan Generated Successfully.")
        # logger.info(json.dumps(plan, indent=2)[:500])

        # 6. Organize Plan
        logger.info("--- Testing /coach/organize_plan ---")
        resp = client.post("/coach/organize_plan", headers=headers)
        if resp.status_code != 200:
            logger.error(f"Organize Plan Failed: {resp.json}")
            return
        
        phased_plan = resp.json["phased_plan"]
        logger.info("Plan Organized Successfully.")
        # logger.info(json.dumps(phased_plan, indent=2)[:500])

        logger.info("ALL COACH TESTS PASSED.")

if __name__ == "__main__":
    verify_coach_flow()
