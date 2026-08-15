# app/health_hub/deduplication_service.py
from datetime import datetime, timezone
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Default Source Priority Ranking (Lower numerical value = higher priority)
DEFAULT_SOURCE_PRIORITY = {
    'garmin': 1,
    'strava': 2,
    'apple_health': 3,
    'healthkit': 3,
    'manual': 4
}

def parse_iso_datetime(dt_str: Any) -> datetime:
    """Parse ISO datetime string or return datetime object."""
    if isinstance(dt_str, datetime):
        return dt_str
    if not dt_str or not isinstance(dt_str, str):
        return datetime.now(timezone.utc)
    
    clean_str = dt_str.strip().replace('Z', '+00:00')
    # If space separated "2026-08-08 08:00:00", replace space with T
    if ' ' in clean_str and 'T' not in clean_str:
        clean_str = clean_str.replace(' ', 'T')
    
    try:
        return datetime.fromisoformat(clean_str)
    except Exception:
        # Fallback formats
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(clean_str[:19], fmt)
            except Exception:
                continue
        return datetime.now(timezone.utc)

def get_effective_priority_map(custom_priority: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    p_map = dict(DEFAULT_SOURCE_PRIORITY)
    if custom_priority:
        for k, v in custom_priority.items():
            p_map[k.lower()] = v
    return p_map

def extract_activity_start_time(act: Dict) -> str:
    return str(
        act.get('start_time') or 
        act.get('start_time_local') or 
        act.get('start_date_local') or 
        act.get('start_date') or 
        act.get('created_at') or 
        ''
    )

def extract_activity_distance(act: Dict) -> float:
    dist = act.get('distance_m')
    if dist is None:
        dist = act.get('distance')
    if dist is None:
        dist = act.get('total_distance')
    try:
        return float(dist or 0.0)
    except (ValueError, TypeError):
        return 0.0

def extract_activity_duration(act: Dict) -> float:
    dur = act.get('duration_s')
    if dur is None:
        dur = act.get('duration')
    if dur is None:
        dur = act.get('moving_time')
    if dur is None:
        dur = act.get('elapsed_time')
    try:
        return float(dur or 0.0)
    except (ValueError, TypeError):
        return 0.0

def deduplicate_activities(activities: List[Dict], custom_priority: Optional[Dict[str, int]] = None) -> List[Dict]:
    """
    Deduplicate activities occurring within +-5 minutes with similar distance/duration (within 5%).
    Marks native recording device (Garmin > Strava > Apple Health > Manual) as primary unless custom priority is supplied.
    Preserves all detailed telemetry from primary source and records duplicate IDs and merged sources.
    """
    if not activities:
        return []

    priority_map = get_effective_priority_map(custom_priority)

    # Sort activities by start_time
    sorted_activities = sorted(activities, key=lambda a: parse_iso_datetime(extract_activity_start_time(a)))
    
    deduped: List[Dict] = []
    used_ids = set()

    for i, act in enumerate(sorted_activities):
        act_id = act.get('id') if act.get('id') is not None else act.get('activity_id')
        if act_id is not None and act_id in used_ids:
            continue

        act_time = parse_iso_datetime(extract_activity_start_time(act))
        act_dist = extract_activity_distance(act)
        
        # Group matching duplicates
        matching_cluster = [act]
        if act_id is not None:
            used_ids.add(act_id)

        for j in range(i + 1, len(sorted_activities)):
            other = sorted_activities[j]
            other_id = other.get('id') if other.get('id') is not None else other.get('activity_id')
            if other_id is not None and other_id in used_ids:
                continue

            other_time = parse_iso_datetime(extract_activity_start_time(other))
            time_diff_s = abs((other_time - act_time).total_seconds())

            # Match within 5 minutes (300 seconds)
            if time_diff_s <= 300:
                other_dist = extract_activity_distance(other)
                # If distance within 5% or both 0
                if act_dist == 0 and other_dist == 0:
                    matching_cluster.append(other)
                    if other_id is not None:
                        used_ids.add(other_id)
                elif act_dist > 0 and abs(act_dist - other_dist) / max(act_dist, 1.0) <= 0.05:
                    matching_cluster.append(other)
                    if other_id is not None:
                        used_ids.add(other_id)
            else:
                break # Sorted by time, so no further matches within 5 minutes

        # Select primary source based on priority_map
        def get_source_rank(x):
            src = str(x.get('source') or x.get('raw_source') or x.get('created_by') or 'manual').lower()
            return priority_map.get(src, 99)

        matching_cluster.sort(key=get_source_rank)
        primary_act = dict(matching_cluster[0])
        primary_act['is_primary'] = True
        
        duplicate_ids = []
        duplicate_sources = []
        for a in matching_cluster[1:]:
            aid = a.get('id') if a.get('id') is not None else a.get('activity_id')
            if aid is not None:
                duplicate_ids.append(aid)
            asrc = a.get('source') or a.get('raw_source') or a.get('created_by')
            if asrc:
                duplicate_sources.append(asrc)
        
        primary_act['duplicate_source_ids'] = duplicate_ids
        if duplicate_sources:
            primary_act['merged_sources'] = duplicate_sources
        
        # Ensure source is explicitly set
        if 'source' not in primary_act or not primary_act['source']:
            primary_act['source'] = primary_act.get('raw_source') or primary_act.get('created_by') or 'manual'

        deduped.append(primary_act)

    return deduped

def resolve_biometrics_priority(biometrics_list: List[Dict], custom_priority: Optional[Dict[str, int]] = None) -> Dict:
    """
    Resolve biometrics from multiple sources using continuous wearable priority hierarchy.
    Merges non-null metrics across sources prioritizing higher-tier sources (Garmin > Apple Health > Manual).
    """
    if not biometrics_list:
        return {}

    priority_map = get_effective_priority_map(custom_priority)

    def get_rank(x):
        src = str(x.get('raw_source') or x.get('source') or 'manual').lower()
        return priority_map.get(src, 99)

    # Sort list from highest priority (lowest rank) to lowest priority
    sorted_sources = sorted(biometrics_list, key=get_rank)

    # Start with highest priority source
    merged = dict(sorted_sources[0])
    primary_src = merged.get('raw_source') or merged.get('source') or 'manual'
    merged['primary_source'] = primary_src
    merged['source'] = primary_src

    # Fill in any missing/null metrics from lower priority sources
    metric_fields = [
        'resting_hr', 'hrv', 'hrv_ms', 'hrv_status', 'sleep_score', 'sleep_hours',
        'deep_sleep_hours', 'rem_sleep_hours', 'light_sleep_hours', 'sleep_stages',
        'recovery_score', 'body_battery', 'stress_level', 'vo2_max', 'fitness_age',
        'training_status', 'acute_load', 'spo2', 'respiration', 'steps', 'calories_burned'
    ]

    for fallback in sorted_sources[1:]:
        for field in metric_fields:
            if merged.get(field) is None and fallback.get(field) is not None:
                merged[field] = fallback.get(field)

    return merged
