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
                    "goals": {"llm_model": "gemini"},
                    "coach_name": "AI Coach",
                    "coach_status": "initial",
                    "interview_step": 1
                }
            ],
            "chats": [],
            "training_events": [],
            "garmin_activities": [],
            "strava_activities": [],
            "activities": [],
            "biometrics_daily": [],
            "garmin_daily": [],
            "garmin_sleep": [],
            "garmin_maxmetrics": [],
            "user_baselines": [],
            "daily_journals": [],
            "lab_panels": [],
            "biomarkers": [],
            "meals": [],
            "athlete_memories": [],
            "user_intelligence": [],
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
                keys = [k.strip() for k in conflict_key.split(",")]
                if all(k in item_copy for k in keys):
                    for row in self.data[self.current_table]:
                        if all(str(row.get(k)) == str(item_copy[k]) for k in keys):
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
        self.update_data = data
        return self

    def delete(self):
        self.delete_mode = True
        return self

    def eq(self, column, value):
        self.query_filters.append(lambda row: str(row.get(column)) == str(value))
        return self

    def gt(self, column, value):
        self.query_filters.append(lambda row: row.get(column) is not None and row.get(column) > value)
        return self

    def gte(self, column, value):
        self.query_filters.append(lambda row: row.get(column) is not None and row.get(column) >= value)
        return self

    def lte(self, column, value):
        self.query_filters.append(lambda row: row.get(column) is not None and row.get(column) <= value)
        return self
    
    def lt(self, column, value):
        self.query_filters.append(lambda row: row.get(column) is not None and row.get(column) < value)
        return self

    def ilike(self, column, pattern):
        clean_pattern = pattern.replace("%", "").lower()
        self.query_filters.append(lambda row: clean_pattern in str(row.get(column, "")).lower())
        return self

    @property
    def not_(self):
        class NotFilter:
            def __init__(self, parent):
                self.parent = parent
            def is_(self, column, value):
                if value == "null" or value is None:
                    self.parent.query_filters.append(lambda row: row.get(column) is not None and row.get(column) != "")
                else:
                    self.parent.query_filters.append(lambda row: str(row.get(column)) != str(value))
                return self.parent
            def eq(self, column, value):
                self.parent.query_filters.append(lambda row: str(row.get(column)) != str(value))
                return self.parent
        return NotFilter(self)

    def is_(self, column, value):
        if value == "null" or value is None:
            self.query_filters.append(lambda row: row.get(column) is None or row.get(column) == "")
        else:
            self.query_filters.append(lambda row: str(row.get(column)) == str(value))
        return self

    def order(self, column, desc=False):
        self.order_column = column
        self.order_desc = desc
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
                filter_cats = params.get("filter_categories")
                rows = self.data.get("user_intelligence", [])
                if match_uid is not None:
                    rows = [r for r in rows if str(r.get("user_id")) == str(match_uid)]
                if filter_cats:
                    rows = [r for r in rows if r.get("category") in filter_cats]
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
            self.data[self.current_table] = [r for r in self.data[self.current_table] if r not in rows]
            del self.delete_mode
            return MockResponse(None)

        # Apply order
        if hasattr(self, 'order_column'):
            col = self.order_column
            desc = getattr(self, 'order_desc', False)
            try:
                rows = sorted(rows, key=lambda x: str(x.get(col, '')), reverse=desc)
            except Exception:
                pass
            del self.order_column
            if hasattr(self, 'order_desc'):
                del self.order_desc

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
