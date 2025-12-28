from typing import List, Dict, Any, Optional
from datetime import datetime
from app.supabase_client import supabase

class MemoryService:
    @staticmethod
    def add_memory(user_id: str, content: str, memory_type: str = "fact") -> Optional[Dict[str, Any]]:
        """Add a new memory with embedding."""
        try:
            from app.utils.llm_utils import get_embedding
            embedding = get_embedding(content)
            
            data = {
                "user_id": user_id,
                "content": content,
                "memory_type": memory_type,
                "created_at": datetime.utcnow().isoformat(),
                "embedding": embedding
            }
            res = supabase.table("memories").insert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Error adding memory: {e}")
            return None

    @staticmethod
    def get_memories(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent memories."""
        try:
            res = supabase.table("memories")\
                .select("id, content, memory_type, created_at")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return res.data or []
        except Exception as e:
            print(f"Error fetching memories: {e}")
            return []
            
    @staticmethod
    def search_memories(user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search memories using vector similarity (if available) or keyword fallback.
        """
        try:
            from app.utils.llm_utils import get_embedding
            query_embedding = get_embedding(query)
            
            if query_embedding:
                # Use vector search via RPC
                params = {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.4, # Lower threshold to be more inclusive
                    "match_count": limit,
                    "p_user_id": user_id
                }
                try:
                    res = supabase.rpc("match_memories", params).execute()
                    return res.data or []
                except Exception as rpc_error:
                    print(f"RPC Error (falling back to keyword): {rpc_error}")
            
            # Fallback to keyword search
            if len(query) < 3:
                return MemoryService.get_memories(user_id, limit)
            
            res = supabase.table("memories")\
                .select("id, content, memory_type, created_at")\
                .eq("user_id", user_id)\
                .ilike("content", f"%{query}%")\
                .limit(limit)\
                .execute()
                
            return res.data or []
        except Exception as e:
            print(f"Error searching memories: {e}")
            return []

    @staticmethod
    def extract_memories_from_chat(user_id: str, user_message: str, bot_response: str):
        """
        Extract memories from a chat interaction using LLM.
        """
        try:
            from app.utils.llm_utils import generate_chat_response
            import json
            import re
            
            prompt = f"""
            Analyze the following conversation between a User and an AI Coach.
            Extract any new facts, preferences, goals, or important context about the User.
            Ignore transient info (like "I'm tired today") unless it indicates a pattern.
            Ignore questions asked by the user.
            Focus on:
            - Long-term goals (e.g., "I want to run a marathon")
            - Preferences (e.g., "I hate running in the rain")
            - Personal facts (e.g., "I have a knee injury", "I work 9-5")
            
            User: {user_message}
            Coach: {bot_response}
            
            Return the extracted memories as a JSON list of objects with 'content' and 'type' (fact, preference, goal).
            If nothing worth remembering, return an empty list [].
            Output JSON ONLY.
            """
            
            from app.config import Config
            
            response = generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                mode="developer",
                provider=Config.LLM_PROVIDER # Use configured provider (e.g., local)
            )
            
            # Extract JSON block if needed
            if isinstance(response, str):
                json_match = re.search(r"\[.*\]", response, re.DOTALL)
                if json_match:
                    memories = json.loads(json_match.group(0))
                    for mem in memories:
                        content = mem.get("content")
                        m_type = mem.get("type", "fact")
                        if content:
                            MemoryService.add_memory(user_id, content, m_type)
                        
        except Exception as e:
            print(f"Memory extraction error: {e}")
