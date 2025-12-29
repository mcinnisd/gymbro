import unittest
from unittest.mock import MagicMock, patch
import json
from app.tools.registry import TOOLS
from app.tools import calendar_tools

class TestTools(unittest.TestCase):
    def test_registry_format(self):
        """Verify that TOOLS list follows OpenAI function calling format."""
        print("\nVerifying Tool Registry Format...")
        self.assertIsInstance(TOOLS, list)
        for tool in TOOLS:
            self.assertEqual(tool["type"], "function")
            self.assertIn("name", tool["function"])
            self.assertIn("description", tool["function"])
            self.assertIn("parameters", tool["function"])
            print(f"  - Verified tool: {tool['function']['name']}")
            
    @patch('app.tools.calendar_tools.supabase')
    def test_calendar_tools_return_dict(self, mock_supabase):
        """Verify that calendar tools return dicts, not strings."""
        print("\nVerifying Calendar Tools Return Types...")
        
        # Mock supabase responses
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "title": "Test Event"}]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response
        mock_supabase.table.return_value.select.return_value.eq.return_value = mock_supabase.table.return_value.select.return_value # chain
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        # 1. create_event
        res = calendar_tools.create_event(1, "2023-01-01", "Test", "run")
        self.assertIsInstance(res, dict)
        self.assertEqual(res["status"], "success")
        print("  - create_event returns dict: OK")
        
        # 2. get_events
        mock_response.data = [{"date": "2023-01-01", "title": "Test", "event_type": "run"}]
        # Need to fix the chaining for get_events complex query
        # Just testing basic return type is enough for now, assuming mocks hold up or even if it errors gracefully
        
        # Simulating get_events path
        mock_query = MagicMock()
        mock_query.execute.return_value = mock_response
        mock_supabase.table.return_value.select.return_value.eq.return_value = mock_query
        
        res = calendar_tools.get_events(1)
        self.assertIsInstance(res, dict)
        self.assertEqual(res["status"], "success")
        print("  - get_events returns dict: OK")

if __name__ == '__main__':
    unittest.main()
