from typing import List, Dict, Any, Optional
import threading
from app.utils.llm_utils import generate_chat_response
from app.config import Config

class CouncilService:
    """
    Orchestrates the "Council of Coaches" - a multi-agent system where
    specialized coaches (Running, Strength, Nutrition) provide perspectives
    on a user's query, synthesized into a single cohesive response.
    """
    
    COACH_PROMPTS = {
        "Running Coach": """You are an elite Running Coach.
Focus on: Mileage, pacing, race strategy, periodization, and running mechanics.
Be specific about run types (tempo, intervals, long run).
Keep your advice concise (max 3-4 sentences).""",

        "Strength Coach": """You are an expert Strength & Conditioning Coach for runners.
Focus on: Injury prevention, gym workouts, core stability, and mobility.
Recommend specific exercises (squats, lunges, plyometrics).
Keep your advice concise (max 3-4 sentences).""",

        "Nutrition Coach": """You are a Sports Nutritionist specializing in endurance athletes.
Focus on: Fueling for performance, hydration, recovery nutrition, and timing.
Recommend specific foods or macros.
Keep your advice concise (max 3-4 sentences)."""
    }

    @staticmethod
    def get_council_advice(user_id: str, user_message: str, context_str: str) -> str:
        """
        Get advice from all coaches in parallel and synthesize it.
        """
        responses = {}
        threads = []
        
        # 1. Gather advice from each coach in parallel
        def ask_coach(role: str, system_prompt: str):
            try:
                # Combine role prompt with user context
                full_system_prompt = f"{system_prompt}\n\n{context_str}"
                
                response = generate_chat_response(
                    messages=[{"role": "user", "content": user_message}],
                    mode="custom", # Use custom mode to pass raw system prompt
                    system_prompt=full_system_prompt,
                    provider=Config.LLM_PROVIDER
                )
                responses[role] = response
            except Exception as e:
                responses[role] = f"Error: {e}"

        for role, prompt in CouncilService.COACH_PROMPTS.items():
            t = threading.Thread(target=ask_coach, args=(role, prompt))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # 2. Synthesize the advice
        return CouncilService._synthesize_responses(user_message, responses)

    @staticmethod
    def _synthesize_responses(user_message: str, responses: Dict[str, str]) -> str:
        """
        Synthesize individual coach responses into a final answer.
        """
        synthesis_prompt = f"""
        You are the Head Coach of a performance team.
        You have gathered advice from your specialist coaches on the user's question: "{user_message}"
        
        Here is their advice:
        
        [RUNNING COACH]
        {responses.get('Running Coach', 'No advice')}
        
        [STRENGTH COACH]
        {responses.get('Strength Coach', 'No advice')}
        
        [NUTRITION COACH]
        {responses.get('Nutrition Coach', 'No advice')}
        
        Synthesize this into a single, cohesive response.
        - Start with a direct answer.
        - Use sections or bullet points for the different perspectives.
        - Resolve any conflicts between coaches (e.g., if Strength says lift heavy leg day before long run, but Running says rest, suggest a compromise).
        - Keep the tone professional, encouraging, and holistic.
        """
        
        try:
            final_response = generate_chat_response(
                messages=[{"role": "user", "content": synthesis_prompt}],
                mode="developer",
                provider=Config.LLM_PROVIDER
            )
            return final_response
        except Exception as e:
            return f"Error synthesizing council advice: {e}"
