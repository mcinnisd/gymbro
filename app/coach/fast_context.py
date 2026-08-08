from app.supabase_client import supabase

def get_fast_context_prompt(user_id: int) -> str:
    # 1. Fetch biometrics
    bio_text = "No recent biometrics recorded."
    if supabase:
        try:
            res = supabase.table('biometrics_daily').select('*').eq('user_id', user_id).limit(7).execute()
            if res and hasattr(res, 'data') and res.data:
                latest = res.data[0]
                bio_text = f"HRV: {latest.get('hrv_ms')}ms | Resting HR: {latest.get('resting_hr')}bpm | Sleep: {latest.get('sleep_hours')}h | Recovery: {latest.get('recovery_score')}/100"
        except Exception:
            pass
            
    # 2. Fetch flagged biomarkers
    flagged_text = "No flagged biomarkers."
    if supabase:
        try:
            res = supabase.table('biomarkers').select('*').eq('user_id', user_id).execute()
            if res and hasattr(res, 'data') and res.data:
                flagged = [b for b in res.data if b.get('status') in ['flagged_low', 'flagged_high']]
                if flagged:
                    flagged_text = ", ".join([f"{b['marker_name']} ({b['value']} {b.get('unit','')}, {b['status']})" for b in flagged])
        except Exception:
            pass

    return f"""=== 7-DAY ATHLETE HEALTH SUMMARY ===
Biometrics: {bio_text}
Flagged Biomarkers: {flagged_text}
===================================="""
