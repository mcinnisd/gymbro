from app.supabase_client import supabase

def get_biomarker_history(user_id: int, marker_name: str) -> list:
    if not supabase:
        return []
    try:
        res = supabase.table('biomarkers').select('*').eq('user_id', user_id).ilike('marker_name', f"%{marker_name}%").execute()
        return res.data if res and hasattr(res, 'data') and res.data else []
    except Exception:
        return []

def generate_workout_routine(split_type: str = 'Push/Pull/Legs', fatigue_level: str = 'low') -> dict:
    if fatigue_level == 'high':
        return {
            "routine_name": "Deload & Recovery Session",
            "exercises": ["Zone 2 Foam Rolling", "Light Mobility Flow", "20min Incline Walk"]
        }
    return {
        "routine_name": f"Optimized {split_type} Routine",
        "exercises": [
            {"exercise": "Barbell Squat", "sets": 4, "reps": 6},
            {"exercise": "Romanian Deadlift", "sets": 3, "reps": 8},
            {"exercise": "Leg Extensions", "sets": 3, "reps": 12}
        ]
    }
