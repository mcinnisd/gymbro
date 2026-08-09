import json
from datetime import datetime, timedelta

class MockSupabaseClient:
    def __init__(self):
        self.data = {
            "users": [
                {
                    "id": "test1111", 
                    "username": "test1111", 
                    "password": "scrypt:32768:8:1$oDnQYjcKzdRegzNQ$10944e6fb485ecc53e47b5da73433bac65cdc29298c3d39f5acf068e89321a5c7bd0a5e6cc0710a0e68dd840f033718e10a3d9aa3b97ccbfec954dc2808fc57f",
                    "goals": {"llm_model": "gemini"}
                }
            ],
            "chats": [],
            "training_events": [],
            "garmin_activities": [],
            "biometrics_daily": [],
            "activities": [],
            "lab_panels": [],
            "biomarkers": [],
            "meals": [],
            "athlete_memories": [],
            "health_graph": []
        }
        self.current_table = None
        self.query_filters = []

    def table(self, table_name):
        self.current_table = table_name
        if table_name not in self.data:
            self.data[table_name] = []
        self.query_filters = []
        return self

    def select(self, *columns, **kwargs):
        return self

    def insert(self, data):
        if self.current_table:
            if isinstance(data, list):
                inserted = []
                for item in data:
                    item_copy = dict(item)
                    if "id" not in item_copy:
                        item_copy["id"] = len(self.data[self.current_table]) + 1
                    self.data[self.current_table].append(item_copy)
                    inserted.append(item_copy)
                self.last_result_data = inserted
            else:
                item_copy = dict(data)
                if "id" not in item_copy:
                    item_copy["id"] = len(self.data[self.current_table]) + 1
                self.data[self.current_table].append(item_copy)
                self.last_result_data = [item_copy]
        return self

    def upsert(self, data, on_conflict=None):
        if self.current_table:
            items = data if isinstance(data, list) else [data]
            results = []
            for item in items:
                item_copy = dict(item)
                conflict_key = on_conflict or "id"
                existing = None
                if conflict_key in item_copy:
                    for row in self.data[self.current_table]:
                        if str(row.get(conflict_key)) == str(item_copy[conflict_key]):
                            existing = row
                            break
                if existing:
                    existing.update(item_copy)
                    results.append(existing)
                else:
                    if "id" not in item_copy and conflict_key == "id":
                        item_copy["id"] = len(self.data[self.current_table]) + 1
                    self.data[self.current_table].append(item_copy)
                    results.append(item_copy)
            self.last_result_data = results
        return self

    def update(self, data):
        # Store update data to apply in execute
        self.update_data = data
        return self

    def delete(self):
        self.delete_mode = True
        return self

    def eq(self, column, value):
        self.query_filters.append(lambda row: str(row.get(column)) == str(value))
        return self

    def gte(self, column, value):
        self.query_filters.append(lambda row: row.get(column) >= value)
        return self

    def lte(self, column, value):
        self.query_filters.append(lambda row: row.get(column) <= value)
        return self
    
    def lt(self, column, value):
        self.query_filters.append(lambda row: row.get(column) < value)
        return self

    def ilike(self, column, pattern):
        # Simple containment check for mock
        clean_pattern = pattern.replace("%", "").lower()
        self.query_filters.append(lambda row: clean_pattern in str(row.get(column, "")).lower())
        return self

    def order(self, column, desc=False):
        # Store order to apply in execute (simplified: ignore for now or implement sort)
        return self

    def limit(self, count):
        self.limit_count = count
        return self
        
    def single(self):
        self.single_mode = True
        return self

    def rpc(self, fn_name, params=None):
        self.rpc_fn = fn_name
        self.rpc_params = params or {}
        return self

    def execute(self):
        if hasattr(self, 'rpc_fn'):
            fn = self.rpc_fn
            params = self.rpc_params
            del self.rpc_fn
            del self.rpc_params
            if fn == "match_intelligence":
                match_uid = params.get("match_user_id")
                rows = self.data.get("user_intelligence", [])
                if match_uid is not None:
                    rows = [r for r in rows if str(r.get("user_id")) == str(match_uid)]
                return MockResponse(rows)
            return MockResponse([])

        if hasattr(self, 'last_result_data'):
            res_data = self.last_result_data
            del self.last_result_data
            if hasattr(self, 'single_mode'):
                del self.single_mode
                return MockResponse(res_data[0] if res_data else None)
            return MockResponse(res_data)

        rows = self.data.get(self.current_table, [])
        
        # Apply filters
        for f in self.query_filters:
            rows = [r for r in rows if f(r)]
            
        # Apply updates
        if hasattr(self, 'update_data'):
            for row in rows:
                row.update(self.update_data)
            del self.update_data
            
        # Apply deletes
        if hasattr(self, 'delete_mode'):
            # Remove rows from main data
            self.data[self.current_table] = [r for r in self.data[self.current_table] if r not in rows]
            del self.delete_mode
            return MockResponse(None) # Delete returns null data usually

        # Apply limit
        if hasattr(self, 'limit_count'):
            rows = rows[:self.limit_count]
            del self.limit_count
            
        if hasattr(self, 'single_mode'):
            del self.single_mode
            if rows:
                return MockResponse(rows[0])
            return MockResponse(None)

        return MockResponse(rows)

class MockResponse:
    def __init__(self, data):
        self.data = data
        if isinstance(data, list):
            self.count = len(data)
        elif data is not None:
            self.count = 1
        else:
            self.count = 0
