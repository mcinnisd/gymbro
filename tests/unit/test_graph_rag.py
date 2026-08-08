import pytest
from app.mock_supabase import MockSupabaseClient
import app.memory.graph_rag as graph_rag

def test_query_hybrid_graph_rag(monkeypatch):
    monkeypatch.setattr(graph_rag, 'supabase', MockSupabaseClient())
    
    # Pre-populate memory and graph edge
    db = graph_rag.supabase
    db.table('athlete_memories').insert({
        'user_id': 1, 'content_text': 'Ferritin dropped to 14 in August blood panel', 'category': 'lab_flag'
    }).execute()
    db.table('health_graph').insert({
        'user_id': 1, 'source_node': 'Ferritin', 'target_node': 'Oxygen Transport', 'relationship_type': 'INFLUENCES'
    }).execute()
    
    result = graph_rag.query_hybrid_graph_rag(user_id=1, query="why am I feeling exhausted on long runs?")
    assert 'memories' in result
    assert 'graph_paths' in result
    assert len(result['memories']) > 0
    assert len(result['graph_paths']) > 0
