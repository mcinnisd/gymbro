from datetime import datetime
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Source Priority Ranking (Lower numerical value = higher priority)
SOURCE_PRIORITY = {
    'garmin': 1,
    'strava': 2,
    'apple_health': 3,
    'manual': 4
}

def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string into datetime object."""
    try:
        dt_str = dt_str.replace('Z', '+00:00')
        return datetime.fromisoformat(dt_str)
    except Exception:
        return datetime.now()

def deduplicate_activities(activities: List[Dict]) -> List[Dict]:
    """
    Deduplicate activities occurring within +-5 minutes with similar distance/duration.
    Marks native recording device (Garmin > Strava > Apple Health) as primary.
    """
    if not activities:
        return []

    # Sort activities by start_time
    sorted_activities = sorted(activities, key=lambda a: parse_iso_datetime(a.get('start_time', '')))
    
    deduped: List[Dict] = []
    used_ids = set()

    for i, act in enumerate(sorted_activities):
        act_id = act.get('id')
        if act_id in used_ids:
            continue

        act_time = parse_iso_datetime(act.get('start_time', ''))
        act_dist = act.get('distance_m', 0)
        
        # Group matching duplicates
        matching_cluster = [act]
        used_ids.add(act_id)

        for j in range(i + 1, len(sorted_activities)):
            other = sorted_activities[j]
            other_id = other.get('id')
            if other_id in used_ids:
                continue

            other_time = parse_iso_datetime(other.get('start_time', ''))
            time_diff_s = abs((other_time - act_time).total_seconds())

            # Match within 5 minutes (300 seconds)
            if time_diff_s <= 300:
                other_dist = other.get('distance_m', 0)
                # If distance within 5% or both 0
                if act_dist == 0 or abs(act_dist - other_dist) / max(act_dist, 1) <= 0.08:
                    matching_cluster.append(other)
                    used_ids.add(other_id)
            else:
                break # Sorted by time, so no further matches

        # Select primary source based on SOURCE_PRIORITY
        matching_cluster.sort(key=lambda x: SOURCE_PRIORITY.get(x.get('source', 'manual'), 99))
        primary_act = dict(matching_cluster[0])
        primary_act['is_primary'] = True
        
        duplicate_ids = [a.get('id') for a in matching_cluster[1:] if a.get('id') is not None]
        primary_act['duplicate_source_ids'] = duplicate_ids
        
        deduped.append(primary_act)

    return deduped

def resolve_biometrics_priority(biometrics_list: List[Dict]) -> Dict:
    """
    Resolve biometrics from multiple sources using continuous wearable priority hierarchy.
    """
    if not biometrics_list:
        return {}

    # Sort list by SOURCE_PRIORITY
    sorted_sources = sorted(
        biometrics_list,
        key=lambda x: SOURCE_PRIORITY.get(x.get('raw_source', 'manual'), 99)
    )

    primary = dict(sorted_sources[0])
    primary['primary_source'] = primary.get('raw_source', 'manual')
    return primary
