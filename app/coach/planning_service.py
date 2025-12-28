import json
import logging
from datetime import datetime, timedelta
from app.supabase_client import supabase
from app.utils.llm_utils import generate_chat_response

logger = logging.getLogger(__name__)

class PlanningService:
    @staticmethod
    def generate_plan(user_id, goal, weeks=4, start_date=None):
        """
        Generates a multi-week training plan for the user.
        
        Args:
            user_id (int): User ID.
            goal (str): The specific goal (e.g., "Marathon under 4 hours").
            weeks (int): Duration of the plan.
            start_date (str): Start date YYYY-MM-DD (defaults to tomorrow).
            
        Returns:
            str: Summary of the created plan.
        """
        try:
            # 1. Fetch User Profile
            user_res = supabase.table("users").select("*").eq("id", user_id).execute()
            if not user_res.data:
                return "User not found."
            user = user_res.data[0]
            profile = user.get("profile", {})
            
            # 2. Determine Start Date
            if not start_date:
                start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                
            # 3. Construct Prompt
            prompt = f"""
            Create a {weeks}-week training plan for a runner with the following profile:
            - Goal: {goal}
            - Current Fitness: {profile.get('running_experience', 'Unknown')}
            - Weekly Availability: {profile.get('weekly_availability', 'Unknown')}
            - Injuries: {profile.get('past_injuries', 'None')}
            
            The plan should start on {start_date}.
            
            OUTPUT FORMAT:
            Return ONLY a valid JSON array of event objects. Do not include any markdown formatting or explanation.
            Each object must have:
            - "date": "YYYY-MM-DD"
            - "title": "Short title"
            - "event_type": "run" | "strength" | "rest" | "race" | "other"
            - "description": "Detailed workout description"
            
            Example:
            [
                {{"date": "2023-10-01", "title": "Easy Run", "event_type": "run", "description": "5km at easy pace"}},
                {{"date": "2023-10-02", "title": "Rest Day", "event_type": "rest", "description": "Active recovery"}}
            ]
            """
            
            # 4. Call LLM
            # We use a specific model or the default one
            response_text = generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                mode="developer", # Use developer mode for strict JSON output
                system_prompt="You are a JSON generator. Output only valid JSON."
            )
            
            # 5. Parse JSON
            # Clean up potential markdown code blocks
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            events = json.loads(clean_text)
            
            if not isinstance(events, list):
                return "Failed to generate a valid plan format."
                
            # 6. Insert Events
            events_to_insert = []
            for e in events:
                events_to_insert.append({
                    "user_id": user_id,
                    "date": e["date"],
                    "title": e["title"],
                    "event_type": e["event_type"],
                    "description": e["description"],
                    "status": "planned",
                    "created_by": "coach_plan",
                    "created_at": datetime.now().isoformat()
                })
                
            if events_to_insert:
                supabase.table("training_events").insert(events_to_insert).execute()
                return f"Successfully created a {weeks}-week plan with {len(events_to_insert)} events starting {start_date}."
            else:
                return "No events were generated."
                
        except Exception as e:
            logger.error(f"Error generating plan: {e}")
            return f"Error generating plan: {e}"
