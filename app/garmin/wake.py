"""Wake check from garmin_sleep and garmin_daily. Does not call Garmin."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.garmin.scope import normalize_garmin_user_id
from app.supabase_client import supabase

DEFAULT_TZ = "America/Los_Angeles"
_EARLY = 5
_WINDOW = 25
_HR_DELTA = 12
_MIN_STEPS = 80

def get_wake_status(user_id: str, as_of: Optional[str] = None, timezone: Optional[str] = None) -> dict:
    if not supabase:
        return _out(user_id=user_id, status="error", reason="supabase client is not configured", message="supabase client is not configured")
    uid = normalize_garmin_user_id(user_id)
    user = _user(uid)
    tz_name = _tz_name(timezone, user)
    zone = _zone(tz_name)
    day = _day(as_of) if as_of else datetime.now(zone).date()
    if as_of and day is None:
        return _out(user_id=user_id, timezone=tz_name, status="error", reason=f"invalid as_of date: {as_of}", message=f"invalid as_of date: {as_of}")

    day_iso = day.isoformat()
    sleep_row = _one("garmin_sleep", uid, day_iso)
    daily_row = _one("garmin_daily", uid, day_iso)
    facts = _sleep((sleep_row or {}).get("sleep_data") if sleep_row else None)
    samples, hr_rest = _hr((daily_row or {}).get("heartrate") if daily_row else None)
    buckets = _steps((daily_row or {}).get("steps") if daily_row else None)
    resting = _rest(daily_row, hr_rest)
    latest = _latest(uid, sleep_row, daily_row, [s[0] for s in samples] + [b[1] for b in buckets])
    base = dict(
        user_id=str(user_id), sleep_date=day_iso, timezone=tz_name,
        sleep_start=_fmt(facts["start"], zone),
        confirmation_type=facts["confirmation"], latest_data_at=latest,
    )

    if facts["finalized"]:
        return _out(**base, finalized=True, awake=True, state="up", signal="sleep_finalized",
                    confidence="high", wake_time=_fmt(facts["end"], zone),
                    reason="sleep session finalized")

    off = _off_wrist(facts, samples, day, zone)
    if off is not None:
        when, reason = off
        return _out(**base, awake=True, state="up", signal="off_wrist", confidence="medium",
                    wake_time=_fmt(when, zone), reason=reason)

    moved = _activity(samples, buckets, resting, day, zone)
    if moved is not None:
        return _out(**base, awake=True, state="up", signal="activity", confidence="medium",
                    wake_time=_fmt(moved, zone),
                    reason="sustained morning steps and heart rate above resting")

    covered = _last(samples, buckets)
    covered = covered is not None and covered.astimezone(zone) >= _at(day, _EARLY, zone)
    if not covered:
        if sleep_row is None:
            reason = "unknown / not synced yet: no row"
        elif facts["empty"]:
            reason = "unknown / not synced yet: empty shell (not uploaded yet)"
        else:
            reason = "unknown / not synced yet: present but not yet confirmed/final"
        return _out(**base, awake=None, state="unknown", reason=reason)
    if sleep_row is None:
        reason = "no row"
    elif facts["empty"]:
        reason = "empty shell (not uploaded yet)"
    else:
        reason = "present but not yet confirmed/final"
    return _out(**base, awake=False, state="not_yet", reason=reason)

def format_wake_status_line(result: dict) -> str:
    keys = (
        "user_id", "sleep_date", "timezone", "finalized", "awake", "state", "signal",
        "confidence", "wake_time", "sleep_start", "confirmation_type", "latest_data_at", "garmin_called",
    )
    def token(value):
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)
    parts = [f"{key}={token(result.get(key))}" for key in keys if key in result or key != "garmin_called"]
    parts.append(f"reason={token(result.get('reason'))}")
    return " ".join(parts)

def _sleep(raw: Any) -> dict:
    data = _json(raw)
    data = data if isinstance(data, dict) else {}
    dto = data.get("dailySleepDTO") if isinstance(data.get("dailySleepDTO"), dict) else {}
    levels = data.get("sleepLevels") if isinstance(data.get("sleepLevels"), list) else []
    if not levels and isinstance(dto.get("sleepLevels"), list):
        levels = dto["sleepLevels"]
    confirmation = dto.get("sleepWindowConfirmationType")
    confirmation = confirmation.strip() if isinstance(confirmation, str) and confirmation.strip() else None
    kind = (confirmation or "").lower()
    start, end = _epoch(dto.get("sleepStartTimestampGMT")), _epoch(dto.get("sleepEndTimestampGMT"))
    has_id = dto.get("id") not in (None, "") and str(dto.get("id")).strip().lower() not in {"", "null", "none"}
    confirmed = dto.get("sleepWindowConfirmed") is True or str(dto.get("sleepWindowConfirmed")).strip().lower() == "true"
    return {
        "empty": not has_id and not levels and start is None and end is None,
        "finalized": bool(has_id and levels and confirmed and kind == "enhanced_confirmed_final"),
        "off_wrist": kind == "off_wrist",
        "confirmation": confirmation,
        "start": start,
        "end": end,
    }

def _off_wrist(facts, samples, day, zone):
    """Immediate up at/after 05:00. No settle wait. A series that ends is not off-wrist."""
    end = facts["end"]
    if facts["off_wrist"] and end is not None:
        local = end.astimezone(zone)
        if local.date() == day and local >= _at(day, _EARLY, zone):
            return end, "sleep window closed off-wrist"
    if len(samples) < 2 or samples[-1][1] is not None:
        return None
    index = len(samples) - 1
    while index >= 0 and samples[index][1] is None:
        index -= 1
    if index < 0:
        return None
    start = samples[index + 1][0]
    if samples[-1][0] - start < timedelta(minutes=_WINDOW):
        return None
    if start.astimezone(zone) < _at(day, _EARLY, zone):
        return None
    worn = [s for s in samples[: index + 1] if s[1] is not None and s[0] >= start - timedelta(hours=3)]
    if len(worn) < 5 or worn[-1][0] - worn[0][0] < timedelta(minutes=20):
        return None
    return start, "sustained morning off-wrist after overnight wear"

def _activity(samples, buckets, resting, day, zone):
    if resting is None:
        return None
    earliest = _at(day, _EARLY, zone)
    window = timedelta(minutes=_WINDOW)
    last = _last(samples, buckets)
    if last is None or last < earliest + window:
        return None
    cursor = earliest
    while cursor <= last - window:
        end = cursor + window
        if _active(samples, buckets, cursor, end, resting):
            return cursor
        cursor += timedelta(minutes=5)
    return None

def _active(samples, buckets, start, end, resting) -> bool:
    if _step_sum(buckets, start, end) < _MIN_STEPS:
        return False
    points = [s for s in samples if s[1] is not None and start <= s[0] < end]
    if len(points) < 4:
        return False
    edge = timedelta(minutes=3)
    if points[0][0] > start + edge or points[-1][0] < end - edge:
        return False
    if points[-1][0] - points[0][0] < timedelta(minutes=_WINDOW) * 0.7:
        return False
    return _median([p[1] for p in points]) >= resting + _HR_DELTA

def _hr(raw):
    payload = _json(raw)
    resting = None
    values = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        values = payload.get("heartRateValues") or []
        resting = _num(payload.get("restingHeartRate")) or _num(payload.get("lastSevenDaysAvgRestingHeartRate"))
    samples = []
    for item in values if isinstance(values, list) else []:
        if isinstance(item, (list, tuple)) and len(item) > 1:
            at = _epoch(item[0])
            if at is not None:
                samples.append((at, _bpm(item[1])))
    samples.sort(key=lambda sample: sample[0])
    return samples, resting

def _steps(raw):
    payload = _json(raw)
    items = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        items = payload.get("steps") if isinstance(payload.get("steps"), list) else [payload]
    buckets = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start, end = _epoch(item.get("startGMT")), _epoch(item.get("endGMT"))
        count = _num(item.get("steps"))
        if start is None or count is None or count < 0:
            continue
        if end is None or end <= start:
            end = start + timedelta(minutes=15)
        buckets.append((start, end, count))
    return buckets

def _step_sum(buckets, start, end) -> float:
    total = 0.0
    for b0, b1, count in buckets:
        span = b1 - b0
        if span <= timedelta(0):
            continue
        overlap = min(end, b1) - max(start, b0)
        if overlap > timedelta(0):
            total += count * (overlap / span)
    return total

def _rest(daily_row, hr_rest):
    for value in (_num((daily_row or {}).get("resting_hr")), hr_rest):
        if value is not None and 25 <= value <= 120:
            return value
    return None

def _latest(uid, sleep_row, daily_row, instants):
    found = [t for t in instants if t is not None]
    for row in (sleep_row, daily_row):
        parsed = _epoch((row or {}).get("synced_at")) if row else None
        if parsed:
            found.append(parsed)
    if not found:
        for table in ("garmin_sleep", "garmin_daily"):
            try:
                res = supabase.table(table).select("synced_at").eq("user_id", uid).order("synced_at", desc=True).limit(1).execute()
            except Exception:
                continue
            rows = res.data or []
            parsed = _epoch(rows[0].get("synced_at")) if rows else None
            if parsed:
                found.append(parsed)
    return _iso(max(found)) if found else None

def _user(uid):
    try:
        res = supabase.table("users").select("id,goals").eq("id", uid).limit(1).execute()
    except Exception:
        return None
    rows = res.data or []
    return rows[0] if rows else None

def _one(table, uid, day):
    res = supabase.table(table).select("*").eq("user_id", uid).eq("date", day).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None

def _tz_name(explicit, user) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    goals = (user or {}).get("goals") if isinstance(user, dict) else None
    if isinstance(goals, dict):
        for key in ("timezone", "time_zone", "tz"):
            if isinstance(goals.get(key), str) and goals[key].strip():
                return goals[key].strip()
    return os.environ.get("GYMBRO_ATHLETE_TIMEZONE", "").strip() or DEFAULT_TZ

def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ)

def _out(**fields) -> dict:
    payload = {key: fields.get(key) for key in (
        "user_id", "sleep_date", "timezone", "awake", "signal", "confidence",
        "wake_time", "sleep_start", "confirmation_type", "reason", "latest_data_at",
    )}
    payload["finalized"] = bool(fields.get("finalized"))
    payload["state"] = fields.get("state") or "unknown"
    payload["status"] = fields.get("status") or "success"
    state, reason = payload["state"], payload["reason"]
    payload["message"] = fields.get("message") or (
        f"Athlete is up ({payload['signal']}) at {payload['wake_time']}." if state == "up"
        else f"Wake unknown / not synced yet ({reason}). latest_data_at={payload['latest_data_at']}." if state == "unknown"
        else f"Not up yet for {payload['sleep_date']}: {reason}."
    )
    if "garmin_called" in fields:
        payload["garmin_called"] = fields["garmin_called"]
    return payload

def _last(samples, buckets):
    times = [s[0] for s in samples] + [b[1] for b in buckets]
    return max(times) if times else None

def _at(day: date, hour: int, zone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=zone)

def _fmt(instant, zone):
    return None if instant is None else instant.astimezone(zone).isoformat(timespec="seconds")

def _iso(instant: datetime) -> str:
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc).isoformat(timespec="seconds")

def _epoch(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"null", "none"}:
            return None
        try:
            value = float(text)
        except ValueError:
            text = text[:-1] + "+00:00" if text.endswith("Z") else text
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        num = float(value)
        if abs(num) < 1e11:
            num *= 1000.0
        return datetime.fromtimestamp(num / 1000.0, tz=timezone.utc)
    return None

def _day(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None

def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _bpm(value):
    num = _num(value)
    if num is None or num <= 0 or num > 250:
        return None
    return num

def _median(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0

def _json(value):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value
