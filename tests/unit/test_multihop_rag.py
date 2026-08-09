# tests/unit/test_multihop_rag.py
from unittest.mock import patch, MagicMock
from app.context.intelligence_service import IntelligenceService
from app.supabase_client import supabase


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


def test_multihop_context_builder_includes_notes_and_activities():
    from app.context.builder import build_user_context
    context = build_user_context(user_id="synthetic_user_1", query="How has my sleep affected my running pace?")
    assert "sleep" in context.lower() or "activities" in context.lower()
    assert "notes" in context.lower() or "journal" in context.lower()


def test_multihop_rag_bundle_aggregation():
    from app.memory.rag import build_multihop_rag_bundle, retrieve_relational_metrics, retrieve_vector_notes

    # Seed mock data
    user_id = "test_user_rag_99"
    if supabase:
        supabase.table("garmin_sleep").insert({
            "user_id": user_id,
            "date": "2026-08-08",
            "sleep_hours": 7.5,
            "hrv": 65,
            "sleep_data": {"sleepTimeSeconds": 27000, "avgOvernightHrv": 65, "sleepScores": {"overall": {"value": 85}}}
        }).execute()

        supabase.table("garmin_activities").insert({
            "user_id": user_id,
            "activity_name": "Morning Tempo Run",
            "activity_type": "running",
            "start_time_local": "2026-08-08T07:00:00",
            "distance": 8000,
            "duration": 2400,
            "average_hr": 155
        }).execute()

        supabase.table("daily_journals").insert({
            "user_id": user_id,
            "date": "2026-08-08",
            "answers": {
                "energy_level": 8,
                "felt_sore": False,
                "journal_text": "Felt great during the run after 8 hours sleep."
            }
        }).execute()

    bundle = build_multihop_rag_bundle(user_id=user_id, query="sleep and pace")
    assert bundle["user_id"] == user_id
    assert len(bundle["notes"]) > 0
    assert len(bundle["relational_metrics"]["sleep"]) > 0
    assert len(bundle["relational_metrics"]["activities"]) > 0


def test_multihop_context_builder_formatting_with_data():
    from app.context.builder import build_user_context

    user_id = "test_user_rag_99"
    context = build_user_context(user_id=user_id, query="Analyze my recovery and tempo run")
    assert "Multi-Hop Context for Query" in context
    assert "Sleep & HRV Metrics" in context
    assert "Recent Activities" in context
    assert "Relevant Notes & Journal Entries" in context
    assert "Morning Tempo Run" in context or "Activities" in context
