# tests/unit/test_plan_calendar_population.py
from unittest.mock import patch, MagicMock
from app.coach.plan_service import populate_calendar_from_plan

@patch("app.coach.plan_service.supabase")
def test_populate_calendar_from_plan_success(mock_supa):
    mock_plan = {
        "weeks": [
            {
                "week_number": 1,
                "days": [
                    {"day": "Monday", "activity": "Rest Day", "details": "Full recovery"},
                    {"day": "Tuesday", "activity": "5km Easy Run", "details": "Zone 2 pace"}
                ]
            }
        ]
    }
    
    # Mock user query
    user_query = MagicMock()
    user_query.select.return_value.eq.return_value.execute.return_value.data = [{"training_plan": mock_plan}]
    
    # Mock insert
    insert_query = MagicMock()
    insert_query.insert.return_value.execute.return_value.data = [{"id": 1}]
    
    def table_side_effect(table_name):
        if table_name == "users":
            return user_query
        elif table_name == "training_events":
            return insert_query
        return MagicMock()

    mock_supa.table.side_effect = table_side_effect
    
    result = populate_calendar_from_plan("1")
    assert result.get("success") is True
    assert result.get("events_created") == 2
