import logging
from datetime import datetime
from app.supabase_client import supabase
from app.biomarkers.pdf_service import (
    normalize_analyte_name,
    parse_reference_range,
    evaluate_biomarker_status,
    generate_sports_science_insight
)

logger = logging.getLogger(__name__)

def evaluate_status(value: float, min_val: float = None, max_val: float = None, marker_name: str = None) -> str:
    return evaluate_biomarker_status(value, min_val, max_val, marker_name)


def save_lab_panel(user_id: int, provider_name: str, test_date: str, biomarkers: list, notes: str = None, pdf_storage_path: str = None) -> dict:
    """
    Save a new lab bloodwork panel and its extracted analyte records to Supabase.
    """
    panel_data = {
        'user_id': user_id,
        'provider_name': provider_name or 'Clinical Lab Report',
        'test_date': test_date or datetime.utcnow().strftime('%Y-%m-%d'),
        'notes': notes,
        'pdf_storage_path': pdf_storage_path
    }
    
    panel_id = 1
    if supabase:
        try:
            panel_res = supabase.table('lab_panels').insert(panel_data).execute()
            if panel_res and hasattr(panel_res, 'data') and panel_res.data:
                panel_id = panel_res.data[0]['id']
        except Exception as e:
            logger.warning(f"Error inserting lab_panels record: {e}")
    
    saved_biomarkers = []
    for b in biomarkers:
        raw_name = b.get('marker_name', '')
        norm_name, cat = normalize_analyte_name(raw_name)
        category = b.get('category') or cat
        val = float(b.get('value', 0.0))
        unit = b.get('unit', '')

        min_val = b.get('ref_range_min')
        max_val = b.get('ref_range_max')
        if min_val is None and max_val is None:
            raw_range = b.get('raw_reference_range') or b.get('reference_range')
            if raw_range:
                min_val, max_val = parse_reference_range(raw_range)

        status = b.get('status') or evaluate_status(val, min_val, max_val, norm_name)
        insight = b.get('coach_insight') or generate_sports_science_insight(norm_name, val, unit, status)

        b_record = {
            'panel_id': panel_id,
            'user_id': user_id,
            'marker_name': norm_name,
            'category': category,
            'value': val,
            'unit': unit,
            'ref_range_min': min_val,
            'ref_range_max': max_val,
            'status': status,
            'coach_insight': insight
        }

        if supabase:
            try:
                res = supabase.table('biomarkers').insert(b_record).execute()
                if res and hasattr(res, 'data') and res.data:
                    saved_biomarkers.append(res.data[0])
                else:
                    saved_biomarkers.append(b_record)
            except Exception as e:
                logger.warning(f"Error inserting biomarker record: {e}")
                saved_biomarkers.append(b_record)
        else:
            saved_biomarkers.append(b_record)
            
    return {
        'panel_id': panel_id,
        'provider_name': panel_data['provider_name'],
        'test_date': panel_data['test_date'],
        'notes': notes,
        'biomarkers': saved_biomarkers
    }


def get_user_panels(user_id: int) -> list:
    """
    Retrieve all lab panels for an athlete with summary stats.
    """
    if not supabase:
        return []
    try:
        panels_res = supabase.table('lab_panels').select('*').eq('user_id', user_id).order('test_date', desc=True).execute()
        panels = panels_res.data if panels_res and hasattr(panels_res, 'data') and panels_res.data else []

        # Enrich each panel with biomarker counts
        biomarkers_res = supabase.table('biomarkers').select('*').eq('user_id', user_id).execute()
        all_biomarkers = biomarkers_res.data if biomarkers_res and hasattr(biomarkers_res, 'data') and biomarkers_res.data else []

        enriched = []
        for p in panels:
            p_id = p.get('id')
            p_markers = [b for b in all_biomarkers if str(b.get('panel_id')) == str(p_id)]
            flagged = [b for b in p_markers if b.get('status') in ['flagged_low', 'flagged_high']]

            panel_copy = dict(p)
            panel_copy['total_biomarkers'] = len(p_markers)
            panel_copy['flagged_count'] = len(flagged)
            panel_copy['flagged_markers'] = [b.get('marker_name') for b in flagged]
            enriched.append(panel_copy)

        return enriched
    except Exception as e:
        logger.error(f"Error fetching user lab panels: {e}")
        return []


def get_panel_details(user_id: int, panel_id) -> dict | None:
    """
    Retrieve full details for a single lab panel including categorized biomarkers.
    """
    if not supabase:
        return None
    try:
        panel_res = supabase.table('lab_panels').select('*').eq('user_id', user_id).eq('id', panel_id).single().execute()
        panel = panel_res.data if panel_res and hasattr(panel_res, 'data') and panel_res.data else None
        if not panel:
            # Check without single if needed
            all_p = supabase.table('lab_panels').select('*').eq('user_id', user_id).eq('id', panel_id).execute()
            if all_p and hasattr(all_p, 'data') and all_p.data:
                panel = all_p.data[0]

        if not panel:
            return None

        biomarkers_res = supabase.table('biomarkers').select('*').eq('user_id', user_id).eq('panel_id', panel_id).execute()
        markers = biomarkers_res.data if biomarkers_res and hasattr(biomarkers_res, 'data') and biomarkers_res.data else []

        categories = {}
        for m in markers:
            cat = m.get('category') or 'General Health'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)

        return {
            'id': panel.get('id'),
            'user_id': user_id,
            'provider_name': panel.get('provider_name'),
            'test_date': panel.get('test_date'),
            'notes': panel.get('notes'),
            'pdf_storage_path': panel.get('pdf_storage_path'),
            'created_at': panel.get('created_at'),
            'biomarkers': markers,
            'categories': categories,
            'total_biomarkers': len(markers),
            'flagged_count': len([m for m in markers if m.get('status') in ['flagged_low', 'flagged_high']])
        }
    except Exception as e:
        logger.error(f"Error fetching panel details: {e}")
        return None


def get_flagged_biomarkers(user_id: int, panel_id=None, all_time: bool = False) -> list:
    """
    Retrieve flagged biomarkers for a user.
    If panel_id is supplied, filters to that panel.
    If all_time is False and panel_id is None, defaults to the most recent panel.
    """
    if not supabase:
        return []
    try:
        if panel_id is not None:
            res = supabase.table('biomarkers').select('*').eq('user_id', user_id).eq('panel_id', panel_id).execute()
            rows = res.data if res and hasattr(res, 'data') and res.data else []
            return [b for b in rows if b.get('status') in ['flagged_low', 'flagged_high']]

        if not all_time:
            # Find latest panel
            panels_res = supabase.table('lab_panels').select('*').eq('user_id', user_id).order('test_date', desc=True).execute()
            panels = panels_res.data if panels_res and hasattr(panels_res, 'data') and panels_res.data else []
            if panels:
                latest_id = panels[0]['id']
                res = supabase.table('biomarkers').select('*').eq('user_id', user_id).eq('panel_id', latest_id).execute()
                rows = res.data if res and hasattr(res, 'data') and res.data else []
                return [b for b in rows if b.get('status') in ['flagged_low', 'flagged_high']]

        # All-time flagged
        res = supabase.table('biomarkers').select('*').eq('user_id', user_id).execute()
        if not res or not hasattr(res, 'data') or not res.data:
            return []
        return [b for b in res.data if b.get('status') in ['flagged_low', 'flagged_high']]
    except Exception as e:
        logger.error(f"Error retrieving flagged biomarkers: {e}")
        return []


def calculate_trend_direction(marker_name: str, baseline_val: float, latest_val: float, status: str) -> str:
    """
    Determine if a longitudinal trend is 'improving', 'worsening', or 'stable'.
    """
    if baseline_val == 0:
        return 'stable'

    pct_diff = ((latest_val - baseline_val) / abs(baseline_val)) * 100.0
    if abs(pct_diff) < 3.0:
        return 'stable'

    norm_name, _ = normalize_analyte_name(marker_name)

    # Lower is better markers (inflammatory, atherogenic lipids, fasting glucose, cortisol)
    lower_is_better = ["hs-CRP", "ApoB", "LDL-C", "Triglycerides", "Total Cholesterol", "Fasting Glucose", "HbA1c", "Cortisol", "Creatine Kinase", "ALT", "AST", "ESR"]
    
    # Higher is better (or optimal target range)
    higher_is_better = ["Ferritin", "Vitamin D 25-OH", "Vitamin B12", "Testosterone, Total", "Free Testosterone", "HDL-C", "DHEA-S", "Magnesium, RBC"]

    if norm_name in lower_is_better:
        return 'improving' if latest_val < baseline_val else 'worsening'
    elif norm_name in higher_is_better:
        return 'improving' if latest_val > baseline_val else 'worsening'
    else:
        # Default based on current clinical status
        if status == 'optimal':
            return 'improving'
        return 'worsening'


def get_biomarker_trends(user_id: int, marker_names: list = None, category: str = None, start_date: str = None, end_date: str = None) -> list:
    """
    Calculate longitudinal trends across all historical lab panels for an athlete.
    """
    if not supabase:
        return []
    try:
        # Fetch panels to map test dates
        panels_res = supabase.table('lab_panels').select('*').eq('user_id', user_id).order('test_date', desc=False).execute()
        panels = panels_res.data if panels_res and hasattr(panels_res, 'data') and panels_res.data else []
        panel_date_map = {str(p.get('id')): p.get('test_date', '') for p in panels}

        # Fetch biomarkers
        query = supabase.table('biomarkers').select('*').eq('user_id', user_id)
        if marker_names:
            norm_filter_names = [normalize_analyte_name(m)[0] for m in marker_names]
            # Since mock client or supabase supports in_, we query
            query = query.in_('marker_name', norm_filter_names)

        b_res = query.execute()
        rows = b_res.data if b_res and hasattr(b_res, 'data') and b_res.data else []

        # Group by marker_name
        grouped = {}
        for r in rows:
            m_name, m_cat = normalize_analyte_name(r.get('marker_name', ''))
            if category and m_cat.lower() != category.lower() and r.get('category', '').lower() != category.lower():
                continue

            test_date = panel_date_map.get(str(r.get('panel_id')), r.get('created_at', '')[:10] if r.get('created_at') else '2026-01-01')
            if start_date and test_date < start_date:
                continue
            if end_date and test_date > end_date:
                continue

            if m_name not in grouped:
                grouped[m_name] = {
                    'marker_name': m_name,
                    'category': r.get('category') or m_cat,
                    'unit': r.get('unit', ''),
                    'ref_range_min': r.get('ref_range_min'),
                    'ref_range_max': r.get('ref_range_max'),
                    'observations': []
                }

            grouped[m_name]['observations'].append({
                'date': test_date,
                'value': float(r.get('value', 0.0)),
                'unit': r.get('unit', ''),
                'status': r.get('status', 'optimal'),
                'ref_min': r.get('ref_range_min'),
                'ref_max': r.get('ref_range_max'),
                'coach_insight': r.get('coach_insight', '')
            })

        trends = []
        for m_name, m_data in grouped.items():
            obs = sorted(m_data['observations'], key=lambda x: x['date'])
            if not obs:
                continue

            baseline = obs[0]
            latest = obs[-1]
            delta = round(latest['value'] - baseline['value'], 2)
            pct_change = round(((latest['value'] - baseline['value']) / baseline['value']) * 100.0, 1) if baseline['value'] != 0 else 0.0
            direction = calculate_trend_direction(m_name, baseline['value'], latest['value'], latest['status'])

            trend_insight = f"{m_name} moved from {baseline['value']} to {latest['value']} {latest['unit']} ({'+' if delta > 0 else ''}{delta}, {pct_change}%) over {len(obs)} lab tests."
            if latest['status'] == 'optimal' and direction == 'improving':
                trend_insight += " Currently in optimal physiological range."

            trends.append({
                'marker_name': m_name,
                'category': m_data['category'],
                'unit': m_data['unit'],
                'ref_range_min': m_data['ref_range_min'],
                'ref_range_max': m_data['ref_range_max'],
                'baseline_value': baseline['value'],
                'baseline_date': baseline['date'],
                'latest_value': latest['value'],
                'latest_date': latest['date'],
                'latest_status': latest['status'],
                'delta': delta,
                'percent_change': pct_change,
                'trend_direction': direction,
                'data_points': obs,
                'insight': trend_insight
            })

        return sorted(trends, key=lambda x: x['marker_name'])
    except Exception as e:
        logger.error(f"Error calculating biomarker trends: {e}")
        return []


def get_biomarker_summary(user_id: int) -> dict:
    """
    Provide top-level overview of latest bloodwork panel, optimization breakdown, and key alerts.
    """
    panels = get_user_panels(user_id)
    if not panels:
        return {
            'has_data': False,
            'message': 'No lab bloodwork panels on file. Upload a blood test PDF report to extract biomarkers.'
        }

    latest_panel = panels[0]
    panel_details = get_panel_details(user_id, latest_panel.get('id'))
    markers = panel_details.get('biomarkers', []) if panel_details else []

    optimal_markers = [m for m in markers if m.get('status') == 'optimal']
    flagged_low = [m for m in markers if m.get('status') == 'flagged_low']
    flagged_high = [m for m in markers if m.get('status') == 'flagged_high']

    # Focus recommendations
    focus_areas = []
    for m in (flagged_low + flagged_high):
        focus_areas.append({
            'marker_name': m.get('marker_name'),
            'status': m.get('status'),
            'value': f"{m.get('value')} {m.get('unit', '')}",
            'insight': m.get('coach_insight') or generate_sports_science_insight(m.get('marker_name'), float(m.get('value', 0)), m.get('unit', ''), m.get('status'))
        })

    # Trends
    trends = get_biomarker_trends(user_id)
    top_improvements = [t for t in trends if t.get('trend_direction') == 'improving' and abs(t.get('percent_change', 0)) > 5.0]

    return {
        'has_data': True,
        'latest_panel_id': latest_panel.get('id'),
        'latest_panel_date': latest_panel.get('test_date'),
        'provider_name': latest_panel.get('provider_name'),
        'total_biomarkers_tracked': len(markers),
        'optimal_count': len(optimal_markers),
        'flagged_low_count': len(flagged_low),
        'flagged_high_count': len(flagged_high),
        'flagged_biomarkers': focus_areas,
        'top_improvements': top_improvements,
        'categories_summary': {cat: len(items) for cat, items in (panel_details.get('categories', {}) if panel_details else {}).items()}
    }


def delete_lab_panel(user_id: int, panel_id) -> bool:
    """
    Delete a lab panel and its associated biomarkers.
    """
    if not supabase:
        return False
    try:
        supabase.table('biomarkers').delete().eq('user_id', user_id).eq('panel_id', panel_id).execute()
        supabase.table('lab_panels').delete().eq('user_id', user_id).eq('id', panel_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting lab panel: {e}")
        return False
