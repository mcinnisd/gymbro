from app.supabase_client import supabase

def query_hybrid_graph_rag(user_id: int, query: str) -> dict:
    memories = []
    graph_paths = []
    
    if supabase:
        try:
            mem_res = supabase.table('athlete_memories').select('*').eq('user_id', user_id).execute()
            if mem_res and hasattr(mem_res, 'data') and mem_res.data:
                memories = [m['content_text'] for m in mem_res.data]
        except Exception:
            pass
            
        try:
            graph_res = supabase.table('health_graph').select('*').eq('user_id', user_id).execute()
            if graph_res and hasattr(graph_res, 'data') and graph_res.data:
                graph_paths = [f"({g['source_node']}) --[{g['relationship_type']}]--> ({g['target_node']})" for g in graph_res.data]
        except Exception:
            pass
            
    return {
        "memories": memories,
        "graph_paths": graph_paths
    }
