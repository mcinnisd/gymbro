"""Decide whether an athlete is up, from rows already in Supabase.

Reads ``garmin_sleep`` and ``garmin_daily`` only. Does not call Garmin and does
not use stored credentials or ``ENCRYPTION_KEY``.

Sleep payload shape follows ``garminconnect`` 0.2.25 ``get_sleep_data``
(``GET wellness-service/wellness/dailySleepData``): summary fields live on
``dailySleepDTO`` and stage intervals live on the sibling ``sleepLevels`` list.
``sleepStartTimestampGMT`` / ``sleepEndTimestampGMT`` are epoch milliseconds.
``sleepWindowConfirmationType`` values seen in the Garmin model include
``unconfirmed``, ``device_confirmed``, ``manually_confirmed``, ``auto_confirmed``,
``auto_confirmed_final``, ``off_wrist``, ``enhanced_confirmed``, and
``enhanced_confirmed_final``. A session is finalized only for
``enhanced_confirmed_final`` together with an id, a non-empty ``sleepLevels``
list, and ``sleepWindowConfirmed``.

There is no timezone column on ``users``. The display zone is, in order, the
explicit argument, ``users.goals.timezone`` (also ``time_zone`` / ``tz``),
``GYMBRO_ATHLETE_TIMEZONE``, then ``America/Los_Angeles`` (the athlete zone
documented for the morning coach routine). When the payload includes both GMT
and local sleep timestamps, the wake clock uses that offset so a traveling
watch still formats correctly.

Intraday series are whatever sync already stored:
``garmin_daily.steps`` from ``get_steps_data`` (daily summary chart buckets
with ``startGMT`` / ``endGMT`` / ``steps``) and ``garmin_daily.heartrate``
from ``get_heart_rates`` (``heartRateValues`` pairs; a null heart rate is
Garmin's off-wrist sample). A series that simply stops is treated as sync lag,
not as the watch coming off.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone as dt_timezone
from typing import Any, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.garmin.scope import normalize_garmin_user_id
from app.supabase_client import supabase

FINAL_CONFIRMATION = "enhanced_confirmed_final"
OFF_WRIST_CONFIRMATION = "off_wrist"
DEFAULT_TIMEZONE = "America/Los_Angeles"
_TZ_GOAL_KEYS = ("timezone", "time_zone", "tz")

_RESULT_KEYS = (
    "user_id",
    "sleep_date",
    "timezone",
    "finalized",
    "awake",
    "state",
    "signal",
    "confidence",
    "wake_time",
    "sleep_start",
    "confirmation_type",
    "reason",
    "latest_data_at",
    "status",
    "message",
)


@dataclass(frozen=True)
class WakeConfig:
    """Heuristic knobs. Env overrides are read per call so tests can tune them."""

    sustained_minutes: int = 25
    early_hour: int = 5
    hr_delta_bpm: float = 12.0
    min_steps: float = 80.0
    settle_minutes: int = 20
    settle_max_steps: float = 80.0
    settle_hr_delta: float = 5.0
    off_wrist_minutes: int = 25
    min_hr_samples: int = 4
    hr_span_ratio: float = 0.7
    wear_lookback_hours: int = 3
    wear_min_span_minutes: int = 20
    wear_min_samples: int = 5


@dataclass(frozen=True)
class SleepAssessment:
    empty_shell: bool
    finalized: bool
    confirmation_type: Optional[str]
    start_utc: Optional[datetime]
    wake_utc: Optional[datetime]
    start_offset: Optional[dt_timezone]
    wake_offset: Optional[dt_timezone]
    off_wrist_confirmation: bool


@dataclass(frozen=True)
class StepBucket:
    start: datetime
    end: datetime
    steps: float


@dataclass(frozen=True)
class HrSample:
    at: datetime
    bpm: Optional[float]


def wake_config_from_env() -> WakeConfig:
    def _int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None or not str(raw).strip():
            return default
        try:
            return int(str(raw).strip())
        except ValueError:
            return default

    def _float(name: str, default: float) -> float:
        raw = os.environ.get(name)
        if raw is None or not str(raw).strip():
            return default
        try:
            return float(str(raw).strip())
        except ValueError:
            return default

    return WakeConfig(
        sustained_minutes=_int("GYMBRO_WAKE_SUSTAINED_MINUTES", 25),
        early_hour=_int("GYMBRO_WAKE_EARLY_HOUR", 5),
        hr_delta_bpm=_float("GYMBRO_WAKE_HR_DELTA_BPM", 12.0),
        min_steps=_float("GYMBRO_WAKE_MIN_STEPS", 80.0),
        settle_minutes=_int("GYMBRO_WAKE_SETTLE_MINUTES", 20),
        settle_max_steps=_float("GYMBRO_WAKE_SETTLE_MAX_STEPS", 80.0),
        settle_hr_delta=_float("GYMBRO_WAKE_SETTLE_HR_DELTA", 5.0),
        off_wrist_minutes=_int("GYMBRO_WAKE_OFF_WRIST_MINUTES", 25),
    )


def assess_sleep_payload(sleep_data: Any) -> SleepAssessment:
    """Apply the finalized-session predicate to one ``garmin_sleep.sleep_data``."""
    data = _as_dict(_coerce_json(sleep_data)) or {}
    dto = data.get("dailySleepDTO")
    dto = dto if isinstance(dto, dict) else {}
    levels = data.get("sleepLevels")
    if not isinstance(levels, list) or not levels:
        nested = dto.get("sleepLevels")
        levels = nested if isinstance(nested, list) else []
    confirmation = dto.get("sleepWindowConfirmationType")
    confirmation = confirmation.strip() if isinstance(confirmation, str) and confirmation.strip() else None
    start = _epoch_utc(dto.get("sleepStartTimestampGMT"))
    end = _epoch_utc(dto.get("sleepEndTimestampGMT"))
    has_id = _has_id(dto.get("id"))
    confirmed = _is_true(dto.get("sleepWindowConfirmed"))
    final_type = (confirmation or "").lower() == FINAL_CONFIRMATION
    empty = (not has_id) and not levels and start is None and end is None
    return SleepAssessment(
        empty_shell=empty,
        finalized=bool(has_id and levels and confirmed and final_type),
        confirmation_type=confirmation,
        start_utc=start,
        wake_utc=end,
        start_offset=_offset_from_pair(start, dto.get("sleepStartTimestampLocal")),
        wake_offset=_offset_from_pair(end, dto.get("sleepEndTimestampLocal")),
        off_wrist_confirmation=(confirmation or "").lower() == OFF_WRIST_CONFIRMATION,
    )


def get_wake_status(
    user_id: str,
    as_of: Optional[str] = None,
    timezone: Optional[str] = None,
) -> dict:
    """
    Wake check for one athlete.

    ``as_of`` is the local calendar date Garmin uses as the wake date
    (YYYY-MM-DD). Omitted, it is today in the athlete's zone. Yesterday's
    finalized session is never substituted when today's row is missing or an
    empty shell.

    ``state`` is ``up``, ``not_yet``, or ``unknown``. ``unknown`` means the
    morning has not synced; do not treat that as asleep. ``signal`` is
    ``sleep_finalized``, ``activity``, ``off_wrist``, or null.
    """
    if not supabase:
        return _error(user_id, "supabase client is not configured")

    uid = normalize_garmin_user_id(user_id)
    cfg = wake_config_from_env()
    user = _load_user(uid)
    tz_name = _resolve_tz_name(timezone, user)
    zone = _zone(tz_name)
    if as_of:
        day = _parse_day(as_of)
        if day is None:
            return _error(user_id, f"invalid as_of date: {as_of}", tz_name)
    else:
        day = datetime.now(zone).date()

    day_iso = day.isoformat()
    sleep_row = _row_for_date("garmin_sleep", uid, day_iso)
    daily_row = _row_for_date("garmin_daily", uid, day_iso)
    assessment = assess_sleep_payload((sleep_row or {}).get("sleep_data") if sleep_row else None)
    samples, hr_rest = parse_heart_rate((daily_row or {}).get("heartrate") if daily_row else None)
    buckets = parse_step_buckets((daily_row or {}).get("steps") if daily_row else None)
    resting = _resolve_resting_hr(daily_row, hr_rest, uid, day_iso)
    latest = _latest_data_at(sleep_row, daily_row, samples, buckets, uid)
    display_offset = assessment.wake_offset or assessment.start_offset

    def _local(instant: Optional[datetime]) -> Optional[str]:
        if instant is None:
            return None
        return _format_local(instant, zone, display_offset)

    common = dict(
        user_id=user_id,
        sleep_date=day_iso,
        timezone_name=tz_name,
        sleep_start=_local(assessment.start_utc),
        confirmation_type=assessment.confirmation_type,
        latest_data_at=latest,
    )

    if assessment.finalized:
        return _result(
            **common,
            finalized=True,
            awake=True,
            state="up",
            signal="sleep_finalized",
            confidence="high",
            wake_time=_local(assessment.wake_utc),
            reason="sleep session finalized",
        )

    activity_at = detect_activity_wake(samples, buckets, resting, day, zone, cfg)
    if activity_at is not None:
        return _result(
            **common,
            finalized=False,
            awake=True,
            state="up",
            signal="activity",
            confidence="medium",
            wake_time=_format_local(activity_at, zone, display_offset),
            reason="sustained morning steps and heart rate above resting",
        )

    off_at = confirmation_off_wrist_wake(assessment, samples, resting, day, zone, cfg)
    off_reason = "sleep window closed off-wrist"
    if off_at is None:
        off_at = detect_off_wrist_run(samples, day, zone, cfg)
        off_reason = "sustained morning off-wrist after overnight wear"
    if off_at is not None:
        return _result(
            **common,
            finalized=False,
            awake=True,
            state="up",
            signal="off_wrist",
            confidence="medium",
            wake_time=_format_local(off_at, zone, display_offset),
            reason=off_reason,
        )

    if not _morning_covered(samples, buckets, day, zone, cfg):
        if sleep_row is None:
            reason = "unknown / not synced yet: no row"
        elif assessment.empty_shell:
            reason = "unknown / not synced yet: empty shell (not uploaded yet)"
        else:
            reason = "unknown / not synced yet: present but not yet confirmed/final"
        return _result(
            **common,
            finalized=False,
            awake=None,
            state="unknown",
            signal=None,
            confidence=None,
            wake_time=None,
            reason=reason,
        )

    if sleep_row is None:
        reason = "no row"
    elif assessment.empty_shell:
        reason = "empty shell (not uploaded yet)"
    else:
        reason = "present but not yet confirmed/final"
    return _result(
        **common,
        finalized=False,
        awake=False,
        state="not_yet",
        signal=None,
        confidence=None,
        wake_time=None,
        reason=reason,
    )


def format_wake_status_line(result: dict) -> str:
    """Single key=value line. ``reason`` is last because it contains spaces."""

    def token(value: Any) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)

    keys = [key for key in _RESULT_KEYS if key not in {"reason", "status", "message"}]
    parts = [f"{key}={token(result.get(key))}" for key in keys]
    parts.append(f"reason={token(result.get('reason'))}")
    return " ".join(parts)


def detect_activity_wake(
    samples: Sequence[HrSample],
    buckets: Sequence[StepBucket],
    resting_hr: Optional[float],
    day: date,
    zone: ZoneInfo,
    cfg: WakeConfig,
) -> Optional[datetime]:
    """First sustained morning window that does not fall back to sleep levels."""
    if resting_hr is None:
        return None
    ordered = sorted(samples, key=lambda sample: sample.at)
    earliest = _at(day, cfg.early_hour, 0, zone)
    sustained = timedelta(minutes=cfg.sustained_minutes)
    last = _last_instant(ordered, buckets)
    if last is None:
        return None
    cursor = earliest
    latest_start = last - sustained
    step = timedelta(minutes=5)
    while cursor <= latest_start:
        end = cursor + sustained
        if _window_active(ordered, buckets, cursor, end, resting_hr, cfg) and not _settled_back(
            ordered, buckets, end, resting_hr, last, cfg
        ):
            return cursor
        cursor += step
    return None


def detect_off_wrist_run(
    samples: Sequence[HrSample],
    day: date,
    zone: ZoneInfo,
    cfg: WakeConfig,
) -> Optional[datetime]:
    """
    Terminal run of explicit null heart-rate samples.

    Garmin writes nulls into ``heartRateValues`` for minutes the strap was off.
    A series that ends on a real sample is sync lag, not off-wrist, so only a
    null run that reaches the last sample counts.
    """
    ordered = sorted(samples, key=lambda sample: sample.at)
    if len(ordered) < 2 or ordered[-1].bpm is not None:
        return None
    index = len(ordered) - 1
    while index >= 0 and ordered[index].bpm is None:
        index -= 1
    run = ordered[index + 1 :]
    if len(run) < 2:
        return None
    start = run[0].at
    if run[-1].at - start < timedelta(minutes=cfg.off_wrist_minutes):
        return None
    if start.astimezone(zone) < _at(day, cfg.early_hour, 0, zone):
        return None
    if not _worn_before(ordered[: index + 1], start, cfg):
        return None
    return start


def confirmation_off_wrist_wake(
    assessment: SleepAssessment,
    samples: Sequence[HrSample],
    resting_hr: Optional[float],
    day: date,
    zone: ZoneInfo,
    cfg: WakeConfig,
) -> Optional[datetime]:
    """Sleep window Garmin itself closed as ``off_wrist``, when it was not put back on."""
    if not assessment.off_wrist_confirmation or assessment.wake_utc is None:
        return None
    local = assessment.wake_utc.astimezone(zone)
    earliest = _at(day, cfg.early_hour, 0, zone)
    if local.date() != day or local < earliest:
        return None
    if _returned_to_sleep(samples, assessment.wake_utc, resting_hr, cfg):
        return None
    return assessment.wake_utc


def parse_step_buckets(raw: Any) -> list[StepBucket]:
    payload = _coerce_json(raw)
    items: list = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("steps", "allDayStepList", "stepValues", "entries", "values"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        else:
            if any(key in payload for key in ("startGMT", "endGMT", "steps")):
                items = [payload]
    buckets: list[StepBucket] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = _parse_gmt(item.get("startGMT") or item.get("startTimeGMT") or item.get("start"))
        end = _parse_gmt(item.get("endGMT") or item.get("endTimeGMT") or item.get("end"))
        steps = _num(item.get("steps") if "steps" in item else item.get("stepCount"))
        if start is None or steps is None or steps < 0:
            continue
        if end is None or end <= start:
            end = start + timedelta(minutes=15)
        buckets.append(StepBucket(start=start, end=end, steps=steps))
    return buckets


def parse_heart_rate(raw: Any) -> tuple[list[HrSample], Optional[float]]:
    payload = _coerce_json(raw)
    ts_index, hr_index = 0, 1
    resting = None
    values: list = []
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        nested = payload.get("heartRateValues")
        if nested is None:
            nested = payload.get("heartRateValuesArray")
        values = nested if isinstance(nested, list) else []
        resting = _scalar_hr(payload.get("restingHeartRate")) or _scalar_hr(
            payload.get("lastSevenDaysAvgRestingHeartRate")
        )
        for desc in payload.get("heartRateValueDescriptors") or []:
            if not isinstance(desc, dict) or not isinstance(desc.get("index"), int):
                continue
            key = str(desc.get("key") or "").lower()
            if key in {"timestamp", "time"}:
                ts_index = desc["index"]
            elif key in {"heartrate", "heart_rate", "bpm"}:
                hr_index = desc["index"]
    else:
        return [], None

    samples: list[HrSample] = []
    for item in values:
        if isinstance(item, dict):
            at = _epoch_utc(item.get("timestamp") or item.get("startGMT") or item.get("time"))
            bpm = item.get("heartRate", item.get("heartrate", item.get("value")))
        elif isinstance(item, (list, tuple)) and len(item) > max(ts_index, hr_index):
            at = _epoch_utc(item[ts_index])
            bpm = item[hr_index]
        else:
            continue
        if at is None:
            continue
        samples.append(HrSample(at=at, bpm=_optional_bpm(bpm)))
    samples.sort(key=lambda sample: sample.at)
    return samples, resting


def _window_active(samples, buckets, start, end, resting_hr, cfg: WakeConfig) -> bool:
    if _steps_between(buckets, start, end) < cfg.min_steps:
        return False
    stats = _hr_stats(samples, start, end)
    if stats is None:
        return False
    span, median, count = stats
    if count < cfg.min_hr_samples:
        return False
    if span < timedelta(minutes=cfg.sustained_minutes) * cfg.hr_span_ratio:
        return False
    # Samples have to cover the window, not just a burst at one end.
    edge = timedelta(minutes=3)
    points = [sample for sample in samples if sample.bpm is not None and start <= sample.at < end]
    if not points or points[0].at > start + edge or points[-1].at < end - edge:
        return False
    return median >= resting_hr + cfg.hr_delta_bpm


def _settled_back(samples, buckets, end, resting_hr, last, cfg: WakeConfig) -> bool:
    """True when a quiet block shows up after the candidate, before the series ends."""
    quiet = timedelta(minutes=cfg.settle_minutes)
    if last < end + quiet - timedelta(minutes=2):
        return False
    cursor = end
    horizon = end + timedelta(minutes=30)
    while cursor + quiet <= last and cursor <= horizon:
        if _is_quiet(samples, buckets, cursor, cursor + quiet, resting_hr, cfg):
            return True
        cursor += timedelta(minutes=5)
    return False


def _is_quiet(samples, buckets, start, end, resting_hr, cfg: WakeConfig) -> bool:
    if resting_hr is None:
        return False
    if _steps_between(buckets, start, end) > cfg.settle_max_steps:
        return False
    stats = _hr_stats(samples, start, end)
    if stats is None:
        return False
    span, median, count = stats
    if count < 3 or span < timedelta(minutes=cfg.settle_minutes) * 0.6:
        return False
    return median <= resting_hr + cfg.settle_hr_delta


def _returned_to_sleep(samples, end, resting_hr, cfg: WakeConfig) -> bool:
    """True only when post-removal heart rate is actually near the resting baseline.

    Missing baseline is not evidence of sleep. Garmin's off_wrist close stays
    an up signal until samples can be compared with rest.
    """
    if resting_hr is None:
        return False
    quiet_end = end + timedelta(minutes=cfg.settle_minutes)
    # Strictly after the removal instant.
    stats = _hr_stats(samples, end + timedelta(seconds=1), quiet_end + timedelta(seconds=1))
    if stats is None:
        return False
    span, median, count = stats
    if count < 3 or span < timedelta(minutes=cfg.settle_minutes) * 0.5:
        return False
    return median <= resting_hr + cfg.settle_hr_delta


def _worn_before(prior: Sequence[HrSample], at: datetime, cfg: WakeConfig) -> bool:
    window_start = at - timedelta(hours=cfg.wear_lookback_hours)
    worn = [sample for sample in prior if sample.bpm is not None and window_start <= sample.at <= at]
    if len(worn) < cfg.wear_min_samples:
        return False
    return worn[-1].at - worn[0].at >= timedelta(minutes=cfg.wear_min_span_minutes)


def _morning_covered(samples, buckets, day, zone, cfg: WakeConfig) -> bool:
    last = _last_instant(samples, buckets)
    if last is None:
        return False
    return last.astimezone(zone) >= _at(day, cfg.early_hour, 0, zone)


def _hr_stats(samples, start, end):
    points = [sample for sample in samples if sample.bpm is not None and start <= sample.at < end]
    if not points:
        return None
    span = points[-1].at - points[0].at
    return span, _median([sample.bpm for sample in points]), len(points)


def _steps_between(buckets, start, end) -> float:
    total = 0.0
    for bucket in buckets:
        duration = bucket.end - bucket.start
        if duration <= timedelta(0):
            continue
        overlap = min(end, bucket.end) - max(start, bucket.start)
        if overlap <= timedelta(0):
            continue
        total += bucket.steps * (overlap / duration)
    return total


def _last_instant(samples, buckets) -> Optional[datetime]:
    times = [sample.at for sample in samples] + [bucket.end for bucket in buckets]
    return max(times) if times else None


def _resolve_resting_hr(daily_row, hr_rest, user_id, day_iso) -> Optional[float]:
    for candidate in (
        _scalar_hr((daily_row or {}).get("resting_hr")),
        hr_rest,
    ):
        if candidate is not None and 25 <= candidate <= 120:
            return candidate
    if not supabase:
        return None
    try:
        res = (
            supabase.table("biometrics_daily")
            .select("date,resting_hr")
            .eq("user_id", user_id)
            .lte("date", day_iso)
            .order("date", desc=True)
            .limit(14)
            .execute()
        )
    except Exception:
        return None
    for row in res.data or []:
        value = _scalar_hr(row.get("resting_hr"))
        if value is not None and 25 <= value <= 120:
            return value
    return None


def _load_user(user_id):
    try:
        res = supabase.table("users").select("id,goals").eq("id", user_id).limit(1).execute()
    except Exception:
        return None
    rows = res.data or []
    return rows[0] if rows else None


def _row_for_date(table: str, user_id, day_iso: str):
    res = (
        supabase.table(table)
        .select("*")
        .eq("user_id", user_id)
        .eq("date", day_iso)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def _latest_any(table: str, user_id):
    res = (
        supabase.table(table)
        .select("date,synced_at")
        .eq("user_id", user_id)
        .order("synced_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def _latest_data_at(sleep_row, daily_row, samples, buckets, user_id) -> Optional[str]:
    instants = []
    for row in (sleep_row, daily_row):
        parsed = _parse_dt((row or {}).get("synced_at")) if row else None
        if parsed is not None:
            instants.append(parsed)
    instants.extend(sample.at for sample in samples)
    instants.extend(bucket.end for bucket in buckets)
    if not instants:
        for table in ("garmin_sleep", "garmin_daily"):
            try:
                row = _latest_any(table, user_id)
            except Exception:
                row = None
            parsed = _parse_dt((row or {}).get("synced_at")) if row else None
            if parsed is not None:
                instants.append(parsed)
    if not instants:
        return None
    return _iso_utc(max(instants))


def _resolve_tz_name(explicit: Optional[str], user: Optional[dict]) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    goals = (user or {}).get("goals") if isinstance(user, dict) else None
    if isinstance(goals, dict):
        for key in _TZ_GOAL_KEYS:
            value = goals.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    env = os.environ.get("GYMBRO_ATHLETE_TIMEZONE", "").strip()
    return env or DEFAULT_TIMEZONE


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _result(
    *,
    user_id,
    sleep_date,
    timezone_name,
    finalized,
    awake,
    state,
    signal,
    confidence,
    wake_time,
    sleep_start,
    confirmation_type,
    reason,
    latest_data_at,
    status="success",
    message=None,
) -> dict:
    payload = {
        "user_id": str(user_id),
        "sleep_date": sleep_date,
        "timezone": timezone_name,
        "finalized": bool(finalized),
        "awake": awake,
        "state": state,
        "signal": signal,
        "confidence": confidence,
        "wake_time": wake_time,
        "sleep_start": sleep_start,
        "confirmation_type": confirmation_type,
        "reason": reason,
        "latest_data_at": latest_data_at,
        "status": status,
    }
    if message is None:
        if state == "up":
            message = f"Athlete is up ({signal}) at {wake_time}."
        elif state == "unknown":
            message = (
                f"Wake unknown / not synced yet ({reason}). "
                f"latest_data_at={latest_data_at}."
            )
        else:
            message = f"Not up yet for {sleep_date}: {reason}."
    payload["message"] = message
    return payload


def _error(user_id, message: str, tz_name: Optional[str] = None) -> dict:
    return _result(
        user_id=user_id,
        sleep_date=None,
        timezone_name=tz_name,
        finalized=False,
        awake=None,
        state="unknown",
        signal=None,
        confidence=None,
        wake_time=None,
        sleep_start=None,
        confirmation_type=None,
        reason=message,
        latest_data_at=None,
        status="error",
        message=message,
    )


def _at(day: date, hour: int, minute: int, zone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)


def _format_local(instant: datetime, zone: ZoneInfo, payload_offset: Optional[dt_timezone]) -> str:
    return instant.astimezone(payload_offset or zone).isoformat(timespec="seconds")


def _iso_utc(instant: datetime) -> str:
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=dt_timezone.utc)
    return instant.astimezone(dt_timezone.utc).isoformat(timespec="seconds")


def _offset_from_pair(gmt: Optional[datetime], local_value: Any) -> Optional[dt_timezone]:
    """Difference between Garmin's local timestamp and the GMT instant, as a fixed offset."""
    if gmt is None or local_value is None:
        return None
    if isinstance(local_value, (int, float)) or _looks_numeric(local_value):
        local_as_utc = _epoch_utc(local_value)
        if local_as_utc is None:
            return None
        delta = local_as_utc - gmt
    elif isinstance(local_value, str):
        text = local_value.strip()
        if not text or text.lower() == "null":
            return None
        if _has_explicit_offset(text):
            parsed = _parse_dt(text)
            if parsed is None or parsed.utcoffset() is None:
                return None
            return dt_timezone(parsed.utcoffset())
        naive = _parse_naive(text)
        if naive is None:
            return None
        delta = naive - gmt.astimezone(dt_timezone.utc).replace(tzinfo=None)
    else:
        return None
    if abs(delta) > timedelta(hours=14):
        return None
    return dt_timezone(delta)


def _epoch_utc(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() == "null":
            return None
        if _looks_numeric(text):
            value = float(text)
        else:
            parsed = _parse_dt(text)
            return parsed
    if isinstance(value, (int, float)):
        num = float(value)
        if abs(num) < 1e11:
            num *= 1000.0
        return datetime.fromtimestamp(num / 1000.0, tz=dt_timezone.utc)
    return None


def _parse_gmt(value: Any) -> Optional[datetime]:
    return _epoch_utc(value)


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _parse_naive(text: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return None
    return parsed


def _parse_day(value: str) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _has_explicit_offset(text: str) -> bool:
    if text.endswith("Z"):
        return True
    # Date uses the first two dashes; a third dash or a plus sign is an offset.
    return "+" in text[10:] or text.rfind("-") > 7


def _looks_numeric(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def _has_id(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and text.lower() != "null"
    return True


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
        return True
    return False


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _optional_bpm(value: Any) -> Optional[float]:
    num = _num(value)
    if num is None or num <= 0 or num > 250:
        return None
    return num


def _scalar_hr(value: Any) -> Optional[float]:
    value = _coerce_json(value)
    if isinstance(value, dict):
        for key in ("restingHeartRate", "resting_hr", "value"):
            if key in value:
                return _scalar_hr(value.get(key))
        return None
    if isinstance(value, list):
        return None
    return _num(value)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _as_dict(value: Any) -> Optional[dict]:
    return value if isinstance(value, dict) else None
