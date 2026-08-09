# tests/unit/test_multihop_rag.py
from unittest.mock import patch, MagicMock
from app.context.intelligence_service import IntelligenceService

@patch("app.context.intelligence_service.supabase")
@patch("app.context.intelligence_service.get_embedding")
def test_multihop_rag_intelligence_search(mock_embed, mock_supa):
    mock_embed.return_value = [0.1] * 768
    
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value.data = [
        {"content": "Journal (2026-08-08): Energy=8/10, Sore=False. Notes: Slept well 8 hours.", "category": "fact"}
    ]
    mock_supa.rpc.return_value = mock_rpc
    
    results = IntelligenceService.search_intelligence("1", "sleep trend")
    assert isinstance(results, list)
    assert len(results) > 0
    assert "Energy=8/10" in results[0]["content"]
