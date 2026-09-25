"""Rebuild biometrics_daily from garmin_daily + garmin_sleep. No Garmin API."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from app.garmin.scope import normalize_garmin_user_id
from app.supabase_client import supabase

logger = logging.getLogger(__name__)

_INTS = {"resting_hr", "hrv_ms", "sleep_score", "body_battery", "steps", "recovery_score", "calories_burned"}
_FLOATS = {
    "hrv", "stress_level", "acute_load", "sleep_hours", "deep_sleep_hours", "rem_sleep_hours",
    "light_sleep_hours", "vo2_max", "fitness_age", "spo2", "respiration",
}
_TEXTS = {"hrv_status", "training_status", "source", "raw_source"}


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, dict):
        for key in ("value", "avgStressLevel", "restingHeartRate"):
            if value.get(key) is not None:
                return _num(value.get(key))
        return None
    if isinstance(value, list):
        return None
    try:
        num = float(str(value).strip() if isinstance(value, str) else value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(num) or math.isinf(num) else num


def _int(value: Any) -> Optional[int]:
    num = _num(value)
    if num is None:
        return None
    rounded = int(math.floor(num + 0.5) if num >= 0 else math.ceil(num - 0.5))
    return rounded if -2147483648 <= rounded <= 2147483647 else None


def _day(value: Any) -> str:
    if value is None:
        return ""
    return (value.isoformat() if hasattr(value, "isoformat") else str(value))[:10]


def coerce_biometrics_row(row: dict, *, drop_nulls: bool = False) -> dict:
    """Cast onto column types. drop_nulls keeps vo2_max the raw tables do not store."""
    clean = {}
    for key, value in row.items():
        if key in _INTS:
            coerced = _int(value)
        elif key in _FLOATS:
            coerced = _num(value)
            if coerced is not None and key.endswith("_hours") and abs(coerced) > 99.99:
                coerced = None
        elif key in _TEXTS:
            coerced = value.strip() if isinstance(value, str) and value.strip() else None
        elif key == "sleep_stages" and isinstance(value, dict):
            coerced = value
        elif key == "updated_at" and isinstance(value, str):
            coerced = value
        else:
            continue
        if coerced is None and drop_nulls:
            continue
        clean[key] = coerced
    if "user_id" in row:
        clean["user_id"] = normalize_garmin_user_id(row.get("user_id"))
    if "date" in row:
        clean["date"] = _day(row.get("date"))
    return clean


def _hours(seconds: Any, places: int) -> Optional[float]:
    sec = _num(seconds)
    return round(sec / 3600.0, places) if sec and sec > 0 else None


def _steps(steps: Any) -> Optional[int]:
    if not isinstance(steps, list):
        return _int(steps)
    parts = [_int(item.get("steps") if isinstance(item, dict) else item) for item in steps]
    nums = [n for n in parts if n is not None]
    return sum(nums) if nums else None


def _set(out: dict, key: str, value: Any) -> None:
    if value is not None and out.get(key) is None:
        out[key] = value


def metrics_from_garmin(daily: Any, sleep: Any) -> dict:
    daily = daily if isinstance(daily, dict) else {}
    sleep = sleep if isinstance(sleep, dict) else {}
    dto = sleep.get("dailySleepDTO") if isinstance(sleep.get("dailySleepDTO"), dict) else {}
    hr = daily.get("heartrate") if isinstance(daily.get("heartrate"), dict) else {}
    summary = sleep.get("hrvSummary") if isinstance(sleep.get("hrvSummary"), dict) else {}
    scores = dto.get("sleepScores") if isinstance(dto.get("sleepScores"), dict) else {}
    overall = scores.get("overall") if isinstance(scores.get("overall"), dict) else {}
    out: dict = {}
    _set(out, "resting_hr", _num(daily.get("resting_hr")) or _num(hr.get("restingHeartRate")) or _num(sleep.get("restingHeartRate")))
    _set(out, "stress_level", _num(daily.get("stress")))
    _set(out, "steps", _steps(daily.get("steps")))
    _set(out, "spo2", _num(daily.get("spo2")))
    _set(out, "respiration", _num(daily.get("respiration")) or _num(dto.get("averageRespirationValue")))
    _set(out, "sleep_score", _int(overall.get("value")) or _int(sleep.get("sleepQualityScore") or sleep.get("overallSleepScore")))
    _set(out, "sleep_hours", _hours(dto.get("sleepTimeSeconds") or sleep.get("totalSleepSeconds"), 1))
    hrv = _num(summary.get("lastNightAvg") or summary.get("weeklyAvg") or sleep.get("avgOvernightHrv"))
    _set(out, "hrv", hrv)
    if hrv is not None:
        out["hrv_ms"] = hrv
    status = summary.get("status") or sleep.get("hrvStatus")
    if isinstance(status, str) and status.strip():
        out["hrv_status"] = status.strip()
    stages = {}
    for name in ("deep", "rem", "light", "awake"):
        sec = dto.get(f"{name}SleepSeconds")
        if sec is None:
            continue
        stages[name] = _int(sec) or 0
        if name != "awake":
            _set(out, f"{name}_sleep_hours", _hours(sec, 2))
    if stages:
        out["sleep_stages"] = {name: stages.get(name, 0) for name in ("deep", "rem", "light", "awake")}
    series = sleep.get("sleepBodyBattery")
    if isinstance(series, list):
        points = [(str(item.get("startGMT") or ""), _int(item.get("value"))) for item in series if isinstance(item, dict)]
        points = [(stamp, value) for stamp, value in points if value is not None]
        if points:
            out["body_battery"] = sorted(points)[-1][1]
    return out


def build_biometrics_from_raw(user_id, day, daily_row=None, sleep_row=None) -> dict:
    sleep = (sleep_row or {}).get("sleep_data") if isinstance(sleep_row, dict) else None
    merged = metrics_from_garmin(daily_row, sleep)
    if not merged:
        return {}
    merged.update({
        "user_id": user_id,
        "date": _day(day),
        "source": "garmin",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return coerce_biometrics_row(merged, drop_nulls=True)


def _paged(table: str, user_id, columns: str, page_size: int) -> list:
    uid, rows, start = normalize_garmin_user_id(user_id), [], 0
    while True:
        query = supabase.table(table).select(columns).eq("user_id", uid)
        query = query.range(start, start + page_size - 1) if hasattr(query, "range") else query.limit(page_size)
        page = query.execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def dedupe_biometrics_daily(user_id, page_size: int = 200) -> int:
    """Keep the fullest row per date so upsert has a single target."""
    if not supabase:
        return 0
    groups: dict = {}
    for row in _paged("biometrics_daily", user_id, "*", page_size):
        groups.setdefault(_day(row.get("date")), []).append(row)
    removed, uid = 0, normalize_garmin_user_id(user_id)
    fields = _INTS | _FLOATS | {"sleep_stages", "hrv_status", "training_status"}
    for day, group in groups.items():
        if not day or len(group) < 2:
            continue
        group.sort(key=lambda row: (sum(row.get(k) is not None for k in fields), str(row.get("updated_at") or "")), reverse=True)
        for loser in group[1:]:
            if loser.get("id") is None:
                continue
            supabase.table("biometrics_daily").delete().eq("user_id", uid).eq("id", loser["id"]).execute()
            removed += 1
    return removed


def _missing_unique(exc: BaseException) -> bool:
    blob = str(exc).lower()
    return "42p10" in blob or "no unique or exclusion constraint" in blob


def _write_one(row: dict) -> None:
    try:
        supabase.table("biometrics_daily").upsert(row, on_conflict="user_id, date").execute()
        return
    except Exception as exc:
        if not _missing_unique(exc):
            raise
    found = supabase.table("biometrics_daily").select("id").eq("user_id", row["user_id"]).eq("date", row["date"]).execute().data
    if found:
        supabase.table("biometrics_daily").update(row).eq("user_id", row["user_id"]).eq("date", row["date"]).execute()
    else:
        supabase.table("biometrics_daily").insert(row).execute()


def upsert_biometrics_daily(rows, *, drop_nulls: bool = False) -> int:
    """Upsert coerced rows. Returns how many days still failed."""
    if not supabase:
        return 0
    coerced = [c for row in rows if (c := coerce_biometrics_row(row, drop_nulls=drop_nulls)).get("date")]
    if not coerced:
        return 0
    try:
        supabase.table("biometrics_daily").upsert(coerced, on_conflict="user_id, date").execute()
        return 0
    except Exception:
        logger.warning("biometrics_daily batch upsert failed; retrying per day")
    failed = 0
    for row in coerced:
        try:
            _write_one(row)
        except Exception:
            failed += 1
            logger.warning("biometrics_daily upsert failed for date=%s", row.get("date"))
    return failed


def remirror_biometrics_daily(user_id, page_size: int = 200) -> dict:
    """Idempotent. Reads Supabase only."""
    label = str(user_id)
    empty = {"user_id": label, "source_days": 0, "upserted": 0, "duplicates_removed": 0, "failed": 0}
    if not supabase:
        return {**empty, "error": "supabase not configured"}
    try:
        removed = dedupe_biometrics_daily(user_id, page_size)
        daily = {_day(r.get("date")): r for r in _paged("garmin_daily", user_id, "date,steps,heartrate,stress,respiration,spo2,resting_hr", page_size)}
        sleep = {_day(r.get("date")): r for r in _paged("garmin_sleep", user_id, "date,sleep_data", page_size)}
        daily.pop("", None)
        sleep.pop("", None)
        days = sorted(set(daily) | set(sleep))
        payloads = [doc for doc in (build_biometrics_from_raw(user_id, day, daily.get(day), sleep.get(day)) for day in days) if doc]
        failed = upsert_biometrics_daily(payloads, drop_nulls=True) if payloads else 0
        result = {**empty, "source_days": len(days), "upserted": len(payloads), "duplicates_removed": removed, "failed": failed}
        if failed:
            result["error"] = f"biometrics_daily upsert failed for {failed} day(s)"
        return result
    except Exception as exc:
        logger.warning("remirror_biometrics_daily failed for user_id=%s (%s)", label, type(exc).__name__)
        return {**empty, "error": type(exc).__name__}
