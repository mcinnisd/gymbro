from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from app.supabase_client import supabase
from app.utils.llm_utils import get_embedding, generate_chat_response

logger = logging.getLogger(__name__)

class IntelligenceService:
    """
    Unified service for managing user intelligence (memories, facts, goals, preferences).
    Uses Gemini embeddings (768-dim) and the user_intelligence table.
    """
    
    @staticmethod
    def add_intelligence(user_id: str, content: str, category: str = "fact", metadata: Dict = None) -> Optional[Dict[str, Any]]:
        """Add a new piece of user intelligence with embedding."""
        try:
            embedding = get_embedding(content)
            if not embedding:
                logger.error("Failed to generate embedding for intelligence")
                return None
            
            data = {
                "user_id": int(user_id),
                "content": content,
                "category": category,
                "metadata": metadata or {},
                "embedding": embedding,
                "created_at": datetime.utcnow().isoformat()
            }
            
            res = supabase.table("user_intelligence").insert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error adding intelligence: {e}")
            return None

    @staticmethod
    def search_intelligence(user_id: str, query: str, limit: int = 5, categories: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search user intelligence using vector similarity.
        """
        try:
            query_embedding = get_embedding(query)
            if not query_embedding:
                logger.warning("No embedding generated for query, using keyword fallback.")
                return IntelligenceService._keyword_search(user_id, query, limit, categories)
            
            params = {
                "query_embedding": query_embedding,
                "match_user_id": int(user_id),
                "match_count": limit,
                "match_threshold": 0.4,
                "filter_categories": categories
            }
            
            res = supabase.rpc("match_intelligence", params).execute()
            return res.data or []
            
        except Exception as e:
            logger.error(f"Intelligence search failed: {e}")
            return IntelligenceService._keyword_search(user_id, query, limit, categories)

    @staticmethod
    def _keyword_search(user_id: str, query: str, limit: int, categories: List[str] = None) -> List[Dict]:
        """Simple keyword-based fallback search."""
        try:
            q = supabase.table("user_intelligence").select("id, content, category, created_at").eq("user_id", int(user_id))
            if categories:
                q = q.in_("category", categories)
            
            # Use the first word as a simple keyword
            keyword = query.split()[0] if query else ""
            if keyword:
                q = q.ilike("content", f"%{keyword}%")
                
            res = q.limit(limit).execute()
            return res.data or []
        except Exception:
            return []

    @staticmethod
    def extract_and_store(user_id: str, user_message: str, bot_response: str):
        """
        Extract key information from a chat and store it in user_intelligence.
        """
        try:
            import json
            import re
            
            prompt = f"""
            Analyze the following conversation between a User and an AI Coach.
            Extract any new facts, preferences, goals, or important context about the User.
            
            User: "{user_message}"
            Coach: "{bot_response}"
            
            Return a JSON list of objects with:
            - "content": A concise statement of the fact (e.g., "The user has a goal to run a marathon in May")
            - "category": One of ["goal", "preference", "fact", "injury", "nutrition"]
            
            If nothing worth remembering, return []. 
            Output ONLY valid JSON.
            """
            
            response = generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                mode="developer",
                provider="xai", # Fast model
                stream=False
            )
            
            # Extract JSON
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                items = json.loads(json_match.group(0))
                for item in items:
                    content = item.get("content")
                    category = item.get("category", "fact")
                    if content:
                        IntelligenceService.add_intelligence(user_id, content, category)
                        
        except Exception as e:
            logger.error(f"Intelligence extraction error: {e}")
