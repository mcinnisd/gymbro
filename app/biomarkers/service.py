from app.supabase_client import supabase

def evaluate_status(value: float, min_val: float = None, max_val: float = None) -> str:
    if min_val is not None and value < min_val:
        return 'flagged_low'
    if max_val is not None and value > max_val:
        return 'flagged_high'
    return 'optimal'

def save_lab_panel(user_id: int, provider_name: str, test_date: str, biomarkers: list) -> dict:
    panel_data = {
        'user_id': user_id,
        'provider_name': provider_name,
        'test_date': test_date
    }
    panel_id = 1
    if supabase:
        try:
            panel_res = supabase.table('lab_panels').insert(panel_data).execute()
            if panel_res and hasattr(panel_res, 'data') and panel_res.data:
                panel_id = panel_res.data[0]['id']
        except Exception:
            pass
    
    saved_biomarkers = []
    for b in biomarkers:
        status = evaluate_status(b['value'], b.get('ref_range_min'), b.get('ref_range_max'))
        b_record = {
            'panel_id': panel_id,
            'user_id': user_id,
            'marker_name': b['marker_name'],
            'value': b['value'],
            'unit': b.get('unit', ''),
            'ref_range_min': b.get('ref_range_min'),
            'ref_range_max': b.get('ref_range_max'),
            'status': status
        }
        if supabase:
            try:
                res = supabase.table('biomarkers').insert(b_record).execute()
                if res and hasattr(res, 'data') and res.data:
                    saved_biomarkers.append(res.data[0])
                else:
                    saved_biomarkers.append(b_record)
            except Exception:
                saved_biomarkers.append(b_record)
        else:
            saved_biomarkers.append(b_record)
            
    return {'panel_id': panel_id, 'biomarkers': saved_biomarkers}

def get_flagged_biomarkers(user_id: int) -> list:
    if not supabase:
        return []
    try:
        res = supabase.table('biomarkers').select('*').eq('user_id', user_id).execute()
        if not res or not hasattr(res, 'data') or not res.data:
            return []
        return [b for b in res.data if b.get('status') in ['flagged_low', 'flagged_high']]
    except Exception:
        return []
