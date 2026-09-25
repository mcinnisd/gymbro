"""
Rebuild biometrics_daily from garmin_daily + garmin_sleep already in Supabase.

Does not call Garmin Connect and does not read credentials.

Live gap (user 2, verified): garmin_daily/garmin_sleep ran through 2026-09-15,
while biometrics_daily missed the days whose resting heart rate was stored as a
JSON number like 48.0. biometrics_daily.resting_hr is integer. The sync upsert
sent that float, PostgREST rejected the row, and the exception was swallowed
after the raw tables had already been written.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.garmin.scope import normalize_garmin_user_id
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

# int4 columns. Floats such as 48.0 must be coerced before upsert.
_INT_FIELDS = (
    "resting_hr",
    "hrv_ms",
    "sleep_score",
    "sleep_duration_seconds",
    "recovery_score",
    "body_battery",
    "steps",
    "calories_burned",
    "active_calories",
)

# numeric(precision, scale) columns that overflow into a 22003 and fail the row.
_NUMERIC_LIMITS = {
    "sleep_hours": (4, 2),
    "deep_sleep_hours": (4, 2),
    "rem_sleep_hours": (4, 2),
    "light_sleep_hours": (4, 2),
    "vo2_max": (5, 2),
    "fitness_age": (4, 1),
    "spo2": (5, 2),
    "respiration": (4, 1),
}

_TEXT_FIELDS = ("hrv_status", "training_status", "source", "raw_source")

_SCORE_FIELDS = _INT_FIELDS + tuple(_NUMERIC_LIMITS) + (
    "hrv",
    "stress_level",
    "acute_load",
    "sleep_stages",
    "hrv_status",
    "training_status",
)

_DEDUP_SELECT = "id,user_id,date,updated_at," + ",".join(_SCORE_FIELDS)


def _date_key(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _as_int(value: Any) -> Optional[int]:
    num = _as_float(value)
    if num is None:
        return None
    rounded = math.floor(num + 0.5) if num >= 0 else math.ceil(num - 0.5)
    if rounded > 2147483647 or rounded < -2147483648:
        return None
    return int(rounded)


def _bounded_number(value: Any, precision: int, scale: int) -> Optional[float]:
    num = _as_float(value)
    if num is None:
        return None
    quant = round(num, scale)
    limit = (10 ** (precision - scale)) - (10 ** (-scale))
    if abs(quant) > limit:
        return None
    return quant


def extract_scalar(value: Any) -> Optional[float]:
    """Pull a number out of a Garmin JSON scalar or a small wrapper object."""
    if isinstance(value, dict):
        for key in (
            "value",
            "avgStressLevel",
            "average",
            "restingHeartRate",
            "averageSpO2",
            "latestSpO2",
            "avgSpO2",
            "avgWakingRespirationValue",
            "avgSleepRespirationValue",
            "averageRespirationValue",
        ):
            if value.get(key) is not None:
                return extract_scalar(value.get(key))
        return None
    if isinstance(value, list):
        return None
    return _as_float(value)


def coerce_biometrics_row(row: Dict[str, Any], *, drop_nulls: bool = False) -> Dict[str, Any]:
    """
    Cast a biometrics payload onto live column types.

    drop_nulls is for remirror: omitted keys keep existing vo2_max and other
    fields the raw tables do not store. Sync sends the full day, including nulls.
    """
    clean: Dict[str, Any] = {}
    for key, value in row.items():
        if key in ("user_id", "date"):
            clean[key] = value
            continue
        if key in _INT_FIELDS:
            coerced = _as_int(value)
        elif key in _NUMERIC_LIMITS:
            precision, scale = _NUMERIC_LIMITS[key]
            coerced = _bounded_number(value, precision, scale)
        elif key in ("hrv", "stress_level", "acute_load"):
            coerced = _as_float(value)
        elif key in _TEXT_FIELDS:
            coerced = value.strip() if isinstance(value, str) and value.strip() else None
        elif key == "sleep_stages":
            coerced = value if isinstance(value, dict) else None
        elif key == "updated_at":
            coerced = value if isinstance(value, str) else None
        else:
            continue
        if coerced is None and drop_nulls:
            continue
        clean[key] = coerced

    if "user_id" in row:
        clean["user_id"] = normalize_garmin_user_id(row.get("user_id"))
    if "date" in row:
        clean["date"] = _date_key(row.get("date"))
    return clean


def _sum_steps(steps: Any) -> Optional[int]:
    if isinstance(steps, list):
        total = 0
        found = False
        for item in steps:
            if isinstance(item, dict):
                part = _as_int(item.get("steps"))
            else:
                part = _as_int(item)
            if part is None:
                continue
            total += part
            found = True
        return total if found else None
    return _as_int(steps)


def _hours(seconds: Any, places: int) -> Optional[float]:
    sec = _as_float(seconds)
    if sec is None or sec <= 0:
        return None
    return round(sec / 3600.0, places)


def _body_battery_from_sleep(series: Any) -> Optional[int]:
    """Last sample in the overnight series (morning level), not the daily max."""
    if not isinstance(series, list):
        return None
    points = []
    for item in series:
        if not isinstance(item, dict):
            continue
        value = _as_int(item.get("value"))
        if value is None:
            continue
        points.append((str(item.get("startGMT") or ""), value))
    if not points:
        return None
    points.sort(key=lambda pair: pair[0])
    return points[-1][1]


def parse_sleep_biometrics(sleep_data: Any) -> Dict[str, Any]:
    """Scalars stored under garmin_sleep.sleep_data (or the live sleep API payload)."""
    if not isinstance(sleep_data, dict):
        return {}
    out: Dict[str, Any] = {}
    daily_dto = sleep_data.get("dailySleepDTO") or {}
    if not isinstance(daily_dto, dict):
        daily_dto = {}

    scores = daily_dto.get("sleepScores") or {}
    sleep_score = None
    if isinstance(scores, dict):
        overall = scores.get("overall") or {}
        if isinstance(overall, dict):
            sleep_score = _as_int(overall.get("value"))
    if sleep_score is None:
        sleep_score = _as_int(sleep_data.get("sleepQualityScore") or sleep_data.get("overallSleepScore"))
    if sleep_score is not None:
        out["sleep_score"] = sleep_score

    sleep_sec = daily_dto.get("sleepTimeSeconds") or sleep_data.get("totalSleepSeconds")
    sleep_hours = _hours(sleep_sec, 1)
    if sleep_hours is not None:
        out["sleep_hours"] = sleep_hours

    deep_sec = daily_dto.get("deepSleepSeconds")
    rem_sec = daily_dto.get("remSleepSeconds")
    light_sec = daily_dto.get("lightSleepSeconds")
    awake_sec = daily_dto.get("awakeSleepSeconds")
    for key, sec, places in (
        ("deep_sleep_hours", deep_sec, 2),
        ("rem_sleep_hours", rem_sec, 2),
        ("light_sleep_hours", light_sec, 2),
    ):
        hours = _hours(sec, places)
        if hours is not None:
            out[key] = hours
    if any(item is not None for item in (deep_sec, rem_sec, light_sec, awake_sec)):
        out["sleep_stages"] = {
            "deep": _as_int(deep_sec) or 0,
            "rem": _as_int(rem_sec) or 0,
            "light": _as_int(light_sec) or 0,
            "awake": _as_int(awake_sec) or 0,
        }

    summary = sleep_data.get("hrvSummary") if isinstance(sleep_data.get("hrvSummary"), dict) else {}
    hrv = extract_scalar(summary.get("lastNightAvg") or summary.get("weeklyAvg"))
    if hrv is None:
        hrv = extract_scalar(sleep_data.get("avgOvernightHrv") or sleep_data.get("lastNight5MinHigh"))
    if hrv is not None:
        out["hrv"] = hrv
        out["hrv_ms"] = hrv
    status = summary.get("status") or sleep_data.get("hrvStatus") or sleep_data.get("status")
    if isinstance(status, str) and status.strip():
        out["hrv_status"] = status.strip()

    rhr = extract_scalar(sleep_data.get("restingHeartRate"))
    if rhr is not None:
        out["resting_hr"] = rhr

    respiration = extract_scalar(
        daily_dto.get("averageRespirationValue") or sleep_data.get("averageRespirationValue")
    )
    if respiration is not None:
        out["respiration"] = respiration

    body_battery = _body_battery_from_sleep(sleep_data.get("sleepBodyBattery"))
    if body_battery is not None:
        out["body_battery"] = body_battery
    return out


def parse_daily_biometrics(daily_row: Any) -> Dict[str, Any]:
    """Scalars stored on garmin_daily (steps array, resting_hr number, stress number)."""
    if not isinstance(daily_row, dict):
        return {}
    out: Dict[str, Any] = {}
    rhr = extract_scalar(daily_row.get("resting_hr"))
    if rhr is None and isinstance(daily_row.get("heartrate"), dict):
        rhr = extract_scalar(daily_row["heartrate"].get("restingHeartRate"))
    if rhr is not None:
        out["resting_hr"] = rhr

    stress = extract_scalar(daily_row.get("stress"))
    if stress is not None:
        out["stress_level"] = stress

    steps = _sum_steps(daily_row.get("steps"))
    if steps is not None:
        out["steps"] = steps

    spo2 = extract_scalar(daily_row.get("spo2"))
    if spo2 is not None:
        out["spo2"] = spo2

    respiration = extract_scalar(daily_row.get("respiration"))
    if respiration is not None:
        out["respiration"] = respiration
    return out


def build_biometrics_from_raw(
    user_id: Any,
    day: Any,
    daily_row: Optional[dict] = None,
    sleep_row: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    One biometrics_daily payload for a date. Null metrics are omitted so a
    remirror does not wipe vo2_max / training_status already on the row.
    """
    merged = parse_daily_biometrics(daily_row)
    for key, value in parse_sleep_biometrics((sleep_row or {}).get("sleep_data")).items():
        if merged.get(key) is None and value is not None:
            merged[key] = value
    if not any(merged.get(key) is not None for key in _SCORE_FIELDS):
        return {}
    merged["user_id"] = user_id
    merged["date"] = _date_key(day)
    merged["source"] = "garmin"
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    return coerce_biometrics_row(merged, drop_nulls=True)


def _is_missing_unique_constraint(exc: BaseException) -> bool:
    blob = " ".join(
        str(part) for part in (
            exc,
            getattr(exc, "code", ""),
            getattr(exc, "message", ""),
        )
    ).lower()
    return "42p10" in blob or "no unique or exclusion constraint" in blob


def _paged(table: str, user_id: Any, columns: str, page_size: int) -> List[dict]:
    rows: List[dict] = []
    start = 0
    uid = normalize_garmin_user_id(user_id)
    while True:
        query = supabase.table(table).select(columns).eq("user_id", uid)
        end = start + page_size - 1
        if hasattr(query, "range"):
            query = query.range(start, end)
        else:
            query = query.limit(page_size)
        page = query.execute().data or []
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _richness(row: dict) -> int:
    score = 0
    for key in _SCORE_FIELDS:
        if row.get(key) is not None:
            score += 1
    return score


def dedupe_biometrics_daily(user_id: Any, page_size: int = 200) -> int:
    """
    Collapse duplicate (user_id, date) rows. Keeps the row with the most
    populated metrics (then the newest updated_at). Live Postgres has
    UNIQUE(user_id, date) today; older loads did not, and a plain upsert
    cannot target a date that appears twice.
    """
    if not supabase:
        return 0
    rows = _paged("biometrics_daily", user_id, _DEDUP_SELECT, page_size)
    groups: Dict[str, List[dict]] = {}
    for row in rows:
        groups.setdefault(_date_key(row.get("date")), []).append(row)

    removed = 0
    uid = normalize_garmin_user_id(user_id)
    for day, group in groups.items():
        if not day or len(group) < 2:
            continue
        ranked = sorted(
            group,
            key=lambda row: (
                _richness(row),
                str(row.get("updated_at") or ""),
                -1 if row.get("id") is None else 0,
            ),
            reverse=True,
        )
        for loser in ranked[1:]:
            loser_id = loser.get("id")
            if loser_id is None:
                continue
            supabase.table("biometrics_daily").delete().eq("user_id", uid).eq("id", loser_id).execute()
            removed += 1
    return removed


def _upsert_one(row: dict) -> None:
    try:
        supabase.table("biometrics_daily").upsert(row, on_conflict="user_id, date").execute()
        return
    except Exception as exc:
        if not _is_missing_unique_constraint(exc):
            raise
    existing = (
        supabase.table("biometrics_daily")
        .select("id")
        .eq("user_id", row["user_id"])
        .eq("date", row["date"])
        .execute()
    )
    if existing.data:
        supabase.table("biometrics_daily").update(row).eq("user_id", row["user_id"]).eq("date", row["date"]).execute()
        return
    supabase.table("biometrics_daily").insert(row).execute()


def upsert_biometrics_daily(rows: Iterable[dict], *, drop_nulls: bool = False) -> int:
    """
    Upsert coerced rows. Returns how many days still failed.

    A batch failure is retried per day so one bad payload cannot drop the rest.
    Failures are counted and not re-raised: callers record them on the user row
    instead of marking the sync clean.
    """
    if not supabase:
        return 0
    coerced = []
    for row in rows:
        clean = coerce_biometrics_row(row, drop_nulls=drop_nulls)
        if clean.get("user_id") is None or not clean.get("date"):
            continue
        coerced.append(clean)
    if not coerced:
        return 0
    try:
        supabase.table("biometrics_daily").upsert(coerced, on_conflict="user_id, date").execute()
        return 0
    except Exception as exc:
        logger.warning(
            "biometrics_daily batch upsert failed (%s); retrying per day",
            type(exc).__name__,
        )
    failed = 0
    for row in coerced:
        try:
            _upsert_one(row)
        except Exception as exc:
            failed += 1
            logger.warning(
                "biometrics_daily upsert failed for date=%s (%s)",
                row.get("date"),
                type(exc).__name__,
            )
    return failed


def remirror_biometrics_daily(user_id: str, page_size: int = 200) -> dict:
    """
    Write biometrics_daily from garmin_daily and garmin_sleep already stored
    for this athlete. Idempotent. Does not call Garmin.
    """
    uid_label = str(user_id)
    if not supabase:
        return {
            "user_id": uid_label,
            "source_days": 0,
            "upserted": 0,
            "duplicates_removed": 0,
            "failed": 0,
            "error": "supabase not configured",
        }

    try:
        duplicates_removed = dedupe_biometrics_daily(user_id, page_size=page_size)
        daily_rows = _paged(
            "garmin_daily",
            user_id,
            "date,steps,heartrate,stress,respiration,spo2,resting_hr",
            page_size,
        )
        sleep_rows = _paged("garmin_sleep", user_id, "date,sleep_data", page_size)
        by_date: Dict[str, Dict[str, Optional[dict]]] = {}
        for row in daily_rows:
            day = _date_key(row.get("date"))
            if not day:
                continue
            by_date.setdefault(day, {"daily": None, "sleep": None})["daily"] = row
        for row in sleep_rows:
            day = _date_key(row.get("date"))
            if not day:
                continue
            by_date.setdefault(day, {"daily": None, "sleep": None})["sleep"] = row

        payloads = []
        for day in sorted(by_date):
            pair = by_date[day]
            doc = build_biometrics_from_raw(user_id, day, pair.get("daily"), pair.get("sleep"))
            if doc:
                payloads.append(doc)

        failed = upsert_biometrics_daily(payloads, drop_nulls=True) if payloads else 0
        duplicates_removed += dedupe_biometrics_daily(user_id, page_size=page_size)
        result = {
            "user_id": uid_label,
            "source_days": len(by_date),
            "upserted": len(payloads),
            "duplicates_removed": duplicates_removed,
            "failed": failed,
        }
        if failed:
            result["error"] = f"biometrics_daily upsert failed for {failed} day(s)"
        return result
    except Exception as exc:
        logger.warning("remirror_biometrics_daily failed for user_id=%s (%s)", uid_label, type(exc).__name__)
        return {
            "user_id": uid_label,
            "source_days": 0,
            "upserted": 0,
            "duplicates_removed": 0,
            "failed": 0,
            "error": type(exc).__name__,
        }
