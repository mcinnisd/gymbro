# app/health_hub/deduplication_service.py
from datetime import datetime, timezone
import json
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Default Source Priority Ranking (Lower numerical value = higher priority).
# Fitbit is a reserved wearable slot: no API client and no OAuth. healthkit is
# an alias of apple_health and shares its rank. Do not reorder Garmin, Strava,
# and Apple Health relative to each other.
DEFAULT_SOURCE_PRIORITY = {
    'garmin': 1,
    'strava': 2,
    'apple_health': 3,
    'healthkit': 3,
    'fitbit': 4,
    'manual': 5,
}

# One name per rank for status listings. healthkit is omitted because it shares
# apple_health's rank.
SOURCE_PRIORITY_ORDER = ["garmin", "strava", "apple_health", "fitbit", "manual"]

# Daily metrics merged field-by-field. The same rule covers sleep, HRV, and
# daytime totals such as steps: the highest-priority source with a real value
# wins, and a null from a higher source does not hide a lower source.
BIOMETRIC_METRIC_FIELDS = [
    'resting_hr', 'hrv', 'hrv_ms', 'hrv_status', 'sleep_score', 'sleep_hours',
    'deep_sleep_hours', 'rem_sleep_hours', 'light_sleep_hours', 'sleep_stages',
    'recovery_score', 'body_battery', 'stress_level', 'vo2_max', 'fitness_age',
    'training_status', 'acute_load', 'spo2', 'respiration', 'steps', 'calories_burned',
]

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
    Marks native recording device (Garmin > Strava > Apple Health > Fitbit > Manual) as primary unless custom priority is supplied.
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

def source_name(record: Optional[Dict]) -> str:
    """Normalized source label. Missing records count as manual."""
    if not record:
        return "manual"
    name = str(record.get("raw_source") or record.get("source") or "manual").strip().lower()
    return name or "manual"


def metric_value_present(value: Any) -> bool:
    """True when a source actually measured the field.

    Null, blank text, and empty containers are not measurements, so an empty
    Garmin day cannot hide Apple Health steps. Numeric zero is a real value.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple)):
        return len(value) > 0
    return True


def _provenance_map(existing: Optional[Dict]) -> Dict[str, str]:
    if not existing:
        return {}
    raw = existing.get("field_sources")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}
    owners = {}
    for key, value in raw.items():
        if value is None or not str(value).strip():
            continue
        owners[str(key)] = str(value).strip().lower()
    return owners


def resolve_biometrics_priority(biometrics_list: List[Dict], custom_priority: Optional[Dict[str, int]] = None) -> Dict:
    """
    Field-level biometric merge.

    For each metric, use the highest-priority source that has a real value.
    Sleep and HRV follow that rule, so Garmin wins when it has them and the
    next source fills the gap when it does not. Steps and other daytime
    metrics follow the same rule: an empty higher-priority row does not block
    a lower source. Null never overwrites a real value.

    ``primary_source`` is the highest-priority source that contributed at least
    one metric. ``field_sources`` records the winner of each field.
    """
    if not biometrics_list:
        return {}

    priority_map = get_effective_priority_map(custom_priority)

    def rank(record: Dict) -> int:
        return priority_map.get(source_name(record), 99)

    ordered = sorted(biometrics_list, key=rank)
    merged: Dict[str, Any] = {}
    for key in ("user_id", "date"):
        for record in ordered:
            if record.get(key) is not None:
                merged[key] = record.get(key)
                break

    field_sources: Dict[str, str] = {}
    for field in BIOMETRIC_METRIC_FIELDS:
        for record in ordered:
            value = record.get(field)
            if not metric_value_present(value):
                continue
            merged[field] = value
            field_sources[field] = source_name(record)
            break

    if field_sources:
        primary = min(set(field_sources.values()), key=lambda name: priority_map.get(name, 99))
    else:
        primary = source_name(ordered[0])

    merged["primary_source"] = primary
    merged["source"] = primary
    merged["raw_source"] = primary
    merged["field_sources"] = field_sources
    return merged


def merge_daily_biometrics(
    existing: Optional[Dict],
    incoming: Dict,
    custom_priority: Optional[Dict[str, int]] = None,
) -> Dict:
    """Merge one source write onto the stored day.

    Incoming nulls and omitted fields do not erase a stored value. A later
    Garmin remirror that has sleep but no steps keeps Apple Health steps, and
    a later Apple Health write can refresh those steps without replacing
    Garmin sleep or HRV.
    """
    incoming = dict(incoming or {})
    inc_source = source_name(incoming)
    incoming["source"] = inc_source
    incoming["raw_source"] = inc_source

    groups: Dict[str, Dict] = {}
    if existing:
        owners = _provenance_map(existing)
        row_source = source_name(existing)
        for field in BIOMETRIC_METRIC_FIELDS:
            if not metric_value_present(existing.get(field)):
                continue
            owner = owners.get(field) or row_source
            bucket = groups.setdefault(owner, {"source": owner, "raw_source": owner})
            bucket[field] = existing.get(field)
        if existing.get("user_id") is not None:
            incoming.setdefault("user_id", existing.get("user_id"))
        if existing.get("date"):
            incoming.setdefault("date", existing.get("date"))

    bucket = groups.setdefault(inc_source, {"source": inc_source, "raw_source": inc_source})
    for field in BIOMETRIC_METRIC_FIELDS:
        if metric_value_present(incoming.get(field)):
            bucket[field] = incoming.get(field)
    if incoming.get("user_id") is not None:
        bucket["user_id"] = incoming.get("user_id")
    if incoming.get("date"):
        bucket["date"] = incoming.get("date")
    if incoming.get("updated_at"):
        bucket["updated_at"] = incoming.get("updated_at")

    merged = resolve_biometrics_priority(list(groups.values()), custom_priority)
    if incoming.get("updated_at"):
        merged["updated_at"] = incoming.get("updated_at")
    elif existing and existing.get("updated_at") and "updated_at" not in merged:
        merged["updated_at"] = existing.get("updated_at")
    return merged


def persistable_biometrics_row(merged: Dict) -> Dict:
    """Columns safe to upsert. Nulls are omitted so a partial write cannot clear a filled value."""
    row: Dict[str, Any] = {}
    for key in ("user_id", "date", "source", "raw_source", "updated_at"):
        if merged.get(key) is not None:
            row[key] = merged.get(key)
    for field in BIOMETRIC_METRIC_FIELDS:
        if metric_value_present(merged.get(field)):
            row[field] = merged.get(field)
    sources = merged.get("field_sources")
    if isinstance(sources, dict) and sources:
        row["field_sources"] = sources
    return row


def is_undefined_column_error(exc: BaseException, column: str) -> bool:
    """True when PostgREST/Postgres rejects a column the migration has not added yet."""
    parts = [str(exc)]
    for attr in ("message", "details", "hint", "code"):
        value = getattr(exc, attr, None)
        if value:
            parts.append(str(value))
    blob = " ".join(parts).lower()
    if column.lower() not in blob:
        return False
    return (
        "42703" in blob
        or "pgrst204" in blob
        or "does not exist" in blob
        or "schema cache" in blob
    )
