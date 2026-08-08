from app.supabase_client import supabase

def record_daily_biometrics(user_id: int, payload: dict) -> dict:
    record = {
        'user_id': user_id,
        'date': payload.get('date'),
        'resting_hr': payload.get('resting_hr'),
        'hrv_ms': payload.get('hrv_ms'),
        'sleep_hours': payload.get('sleep_hours'),
        'sleep_score': payload.get('sleep_score'),
        'recovery_score': payload.get('recovery_score'),
        'steps': payload.get('steps'),
        'calories_burned': payload.get('calories_burned'),
        'raw_source': payload.get('raw_source', 'manual')
    }
    
    if supabase:
        try:
            res = supabase.table('biometrics_daily').insert(record).execute()
            if res and hasattr(res, 'data') and res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            # Fallback for offline/unmigrated DB during development
            pass
    return record
