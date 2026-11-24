"""Typed Garmin payloads and one declarative refresh entry per feed."""
from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Any, NamedTuple, Optional

from pydantic import AliasPath, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from app.supabase_client import supabase

logger = logging.getLogger(__name__)
SHELL_DAYS = 14


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
    if isinstance(value, dict):
        return _num(value.get("value"))
    return None


def _first(*values):
    for value in values:
        if isinstance(value, str):
            value = value.strip() or None
        if value is not None:
            return value
    return None


Num = Annotated[Optional[float], BeforeValidator(_num)]


class Loose(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def parse(cls, raw: Any):
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if raw is None or isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            raw = {"value": raw}
        if not isinstance(raw, dict):
            logger.warning("%s skipped non-object payload", cls.__name__)
            return None
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            logger.warning("%s invalid: %s", cls.__name__, exc)
            return None


class ActivityPayload(Loose):
    activityId: Optional[Any] = None
    activityName: Optional[str] = None
    startTimeLocal: Optional[str] = None
    distance: Num = None
    duration: Num = None
    calories: Num = None
    type_key: Optional[str] = Field(None, validation_alias=AliasPath("activityType", "typeKey"))
    averageHR: Num = None
    maxHR: Num = None
    elevationGain: Num = None
    averageSpeed: Num = None
    maxSpeed: Num = None

    def row(self, user_id, details, synced_at, raw):
        if self.activityId in (None, ""):
            return None
        return {
            "user_id": user_id, "activity_id": str(self.activityId), "activity_name": self.activityName,
            "start_time_local": self.startTimeLocal, "distance": self.distance, "duration": self.duration,
            "calories": self.calories, "activity_type": self.type_key, "average_hr": self.averageHR,
            "max_hr": self.maxHR, "elevation_gain": self.elevationGain, "average_speed": self.averageSpeed,
            "max_speed": self.maxSpeed, "raw_data": raw, "details": details, "synced_at": synced_at,
        }


class StepsPayload(Loose):
    steps: Optional[list] = None
    totalSteps: Num = None
    value: Num = None

    @classmethod
    def parse(cls, raw):
        return super().parse({"steps": raw} if isinstance(raw, list) else raw)

    def total(self):
        if isinstance(self.steps, list) and self.steps:
            found = [int(n) for n in (_num(i.get("steps") if isinstance(i, dict) else i) for i in self.steps) if n is not None]
            if found:
                return sum(found)
        return int(self.totalSteps) if self.totalSteps is not None else (int(self.value) if self.value is not None else None)


class SleepPayload(Loose):
    nested_score: Num = Field(None, validation_alias=AliasPath("dailySleepDTO", "sleepScores", "overall", "value"))
    sleepQualityScore: Num = None
    overallSleepScore: Num = None
    nested_seconds: Num = Field(None, validation_alias=AliasPath("dailySleepDTO", "sleepTimeSeconds"))
    totalSleepSeconds: Num = None
    deep: Num = Field(None, validation_alias=AliasPath("dailySleepDTO", "deepSleepSeconds"))
    rem: Num = Field(None, validation_alias=AliasPath("dailySleepDTO", "remSleepSeconds"))
    light: Num = Field(None, validation_alias=AliasPath("dailySleepDTO", "lightSleepSeconds"))
    awake: Num = Field(None, validation_alias=AliasPath("dailySleepDTO", "awakeSleepSeconds"))

    def score(self):
        return _first(self.nested_score, self.sleepQualityScore, self.overallSleepScore)

    def seconds(self):
        return _first(self.nested_seconds, self.totalSleepSeconds)


class HeartRatePayload(Loose):
    restingHeartRate: Num = None


class RhrPayload(Loose):
    value: Num = None
    nested: Num = Field(None, validation_alias=AliasPath("allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE", 0, "value"))

    def resting(self):
        return _first(self.value, self.nested)


class StressPayload(Loose):
    avgStressLevel: Num = None
    value: Num = None

    def level(self):
        return _first(self.avgStressLevel, self.value)


class HrvPayload(Loose):
    last_night: Num = Field(None, validation_alias=AliasPath("hrvSummary", "lastNightAvg"))
    weekly: Num = Field(None, validation_alias=AliasPath("hrvSummary", "weeklyAvg"))
    status_text: Optional[str] = Field(None, validation_alias=AliasPath("hrvSummary", "status"))
    lastNight5MinHigh: Num = None
    value: Num = None

    def reading(self):
        return _first(self.last_night, self.weekly, self.lastNight5MinHigh, self.value)

    def status(self):
        return _first(self.status_text)


class TrainingStatusPayload(Loose):
    trainingStatusKey: Optional[str] = None
    trainingStatus: Optional[Any] = None
    nested_status: Optional[str] = Field(None, validation_alias=AliasPath("userTrainingStatus", "trainingStatusKey"))
    acuteTrainingLoad: Num = None
    acuteLoad: Num = None
    generic_vo2: Num = Field(None, validation_alias=AliasPath("mostRecentVO2Max", "generic", "vo2MaxValue"))
    recent_vo2: Num = Field(None, validation_alias=AliasPath("mostRecentVO2Max", "vo2Max"))

    def status_key(self):
        return _first(self.trainingStatusKey, self.trainingStatus if isinstance(self.trainingStatus, str) else None, self.nested_status)

    def load(self):
        return _first(self.acuteTrainingLoad, self.acuteLoad)

    def vo2(self):
        return _first(self.generic_vo2, self.recent_vo2)


class MaxMetricsPayload(Loose):
    generic_vo2: Num = Field(None, validation_alias=AliasPath("generic", "vo2MaxValue"))
    generic_precise: Num = Field(None, validation_alias=AliasPath("generic", "vo2MaxPrecision"))
    vo2Max: Num = None
    vo2MaxRunning: Num = None
    vo2MaxValue: Num = None
    fitnessAge: Num = None
    value: Num = None

    def vo2(self):
        return _first(self.generic_vo2, self.generic_precise, self.vo2Max, self.vo2MaxRunning, self.vo2MaxValue, self.value)

    def fitness_age(self):
        return self.fitnessAge


class BodyBatteryPayload(Loose):
    highestBodyBattery: Num = None
    currentBodyBattery: Num = None
    bodyBattery: Num = None
    value: Num = None
    bodyBatteryValuesArray: Optional[list] = None

    def level(self):
        chosen = _first(self.highestBodyBattery, self.currentBodyBattery, self.bodyBattery, self.value)
        if chosen is not None:
            return int(chosen)
        latest = None
        for point in self.bodyBatteryValuesArray or []:
            if isinstance(point, (list, tuple)) and len(point) > 1 and _num(point[1]) is not None:
                latest = int(_num(point[1]))
        return latest


class Spo2Payload(Loose):
    averageSpO2: Num = None
    latestSpO2: Num = None
    avgSpO2: Num = None
    value: Num = None

    def reading(self):
        return _first(self.averageSpO2, self.latestSpO2, self.avgSpO2, self.value)


class RespirationPayload(Loose):
    avgWakingRespirationValue: Num = None
    avgSleepRespirationValue: Num = None
    averageRespirationValue: Num = None
    value: Num = None

    def reading(self):
        return _first(self.avgWakingRespirationValue, self.avgSleepRespirationValue, self.averageRespirationValue, self.value)


class DailySummary(Loose):
    resting_hr: Num = None
    hrv: Num = None
    hrv_ms: Num = None
    hrv_status: Optional[str] = None
    sleep_score: Num = None
    sleep_hours: Num = None
    deep_sleep_hours: Num = None
    rem_sleep_hours: Num = None
    light_sleep_hours: Num = None
    sleep_stages: Optional[dict] = None
    stress_level: Num = None
    steps: Optional[int] = None
    body_battery: Optional[int] = None
    vo2_max: Num = None
    fitness_age: Num = None
    training_status: Optional[str] = None
    acute_load: Num = None
    spo2: Num = None
    respiration: Num = None
    source: str = "garmin"


class Feed(NamedTuple):
    name: str
    method: str
    model: type
    kind: str
    shell_days: int = SHELL_DAYS


FEEDS = (
    Feed("activities", "get_activities", ActivityPayload, "incremental"),
    Feed("steps", "get_steps_data", StepsPayload, "recent"),
    Feed("heart_rate", "get_heart_rates", HeartRatePayload, "recent"),
    Feed("rhr", "get_rhr_day", RhrPayload, "recent"),
    Feed("stress", "get_stress_data", StressPayload, "recent"),
    Feed("sleep", "get_sleep_data", SleepPayload, "shell"),
    Feed("hrv", "get_hrv_data", HrvPayload, "shell"),
    Feed("max_metrics", "get_max_metrics", MaxMetricsPayload, "recent"),
    Feed("training_status", "get_training_status", TrainingStatusPayload, "recent"),
    Feed("body_battery", "get_body_battery", BodyBatteryPayload, "recent"),
    Feed("spo2", "get_spo2_data", Spo2Payload, "recent"),
    Feed("respiration", "get_respiration_data", RespirationPayload, "recent"),
)
DAILY_FEEDS = tuple(feed for feed in FEEDS if feed.kind != "incremental")
_COMPLETE = {
    "rhr": "resting_hr", "hrv": "hrv", "sleep": "sleep_score", "steps": "steps",
    "body_battery": "body_battery", "stress": "stress_level", "max_metrics": "vo2_max",
    "spo2": "spo2", "respiration": "respiration", "training_status": "training_status",
}


def is_empty_shell(sleep_data: Any) -> bool:
    data = sleep_data if isinstance(sleep_data, dict) else {}
    dto = data.get("dailySleepDTO") if isinstance(data.get("dailySleepDTO"), dict) else {}
    levels = data.get("sleepLevels") if isinstance(data.get("sleepLevels"), list) else []
    if not levels and isinstance(dto.get("sleepLevels"), list):
        levels = dto["sleepLevels"]
    raw_id = dto.get("id")
    has_id = raw_id not in (None, "") and str(raw_id).strip().lower() not in {"", "null", "none"}
    return not has_id and not levels and dto.get("sleepStartTimestampGMT") is None and dto.get("sleepEndTimestampGMT") is None


class DaySnapshot:
    def __init__(self):
        self.ok = {}
        self.shells = set()

    def complete(self, name, day):
        return day in self.ok.get(name, ())

    def mark(self, name, day):
        if day:
            self.ok.setdefault(name, set()).add(day)


def feed_due(feed, day, today, force, snap) -> bool:
    if feed.kind == "incremental":
        return False
    if force:
        return True
    key, age = day.isoformat(), (today - day).days
    if feed.kind == "recent" and 0 <= age <= 1:
        return True
    if feed.kind == "shell" and key in snap.shells:
        return 0 <= age <= feed.shell_days
    return not snap.complete(feed.name, key)


def _day_key(value) -> str:
    if value is None:
        return ""
    return (value.isoformat() if hasattr(value, "isoformat") else str(value))[:10]


def load_snapshot(user_id, uid, start, end):
    snap = DaySnapshot()
    if not supabase or start is None:
        return snap
    start_s, end_s = start.isoformat(), end.isoformat()

    def rows(table, columns, uid_value):
        return supabase.table(table).select(columns).eq("user_id", uid_value).gte("date", start_s).lte("date", end_s).execute().data or []

    try:
        for row in rows("biometrics_daily", "date," + ",".join(_COMPLETE.values()), uid):
            day = _day_key(row.get("date"))
            for name, column in _COMPLETE.items():
                if row.get(column) is not None:
                    snap.mark(name, day)
    except Exception as exc:
        logger.warning("biometrics snapshot failed: %s", exc)
    try:
        for sleep_uid in dict.fromkeys((user_id, uid)):
            for row in rows("garmin_sleep", "date,sleep_data", sleep_uid):
                day = _day_key(row.get("date"))
                if is_empty_shell(row.get("sleep_data")):
                    snap.shells.add(day)
                    snap.ok.get("sleep", set()).discard(day)
                    snap.ok.get("hrv", set()).discard(day)
                elif day:
                    snap.mark("sleep", day)
    except Exception as exc:
        logger.warning("sleep snapshot failed: %s", exc)
    try:
        for row in rows("garmin_daily", "date,steps,heartrate,stress,resting_hr", user_id):
            day = _day_key(row.get("date"))
            for name, column in (("steps", "steps"), ("heart_rate", "heartrate"), ("stress", "stress"), ("rhr", "resting_hr")):
                if row.get(column) is not None:
                    snap.mark(name, day)
    except Exception as exc:
        logger.warning("garmin_daily snapshot failed: %s", exc)
    return snap


def _hours(seconds, places):
    return round(seconds / 3600.0, places) if seconds and seconds > 0 else None


def summary_from(parsed) -> DailySummary:
    sleep, hrv, rhr = parsed.get("sleep"), parsed.get("hrv"), parsed.get("rhr")
    heart, stress, steps = parsed.get("heart_rate"), parsed.get("stress"), parsed.get("steps")
    battery, training, metrics = parsed.get("body_battery"), parsed.get("training_status"), parsed.get("max_metrics")
    spo2, resp = parsed.get("spo2"), parsed.get("respiration")
    stages = {name: int(getattr(sleep, name)) for name in ("deep", "rem", "light", "awake") if sleep and getattr(sleep, name) is not None}
    return DailySummary(
        resting_hr=_first(rhr.resting() if rhr else None, heart.restingHeartRate if heart else None),
        hrv=hrv.reading() if hrv else None, hrv_ms=hrv.reading() if hrv else None, hrv_status=hrv.status() if hrv else None,
        sleep_score=sleep.score() if sleep else None, sleep_hours=_hours(sleep.seconds() if sleep else None, 1),
        deep_sleep_hours=_hours(stages.get("deep"), 2), rem_sleep_hours=_hours(stages.get("rem"), 2),
        light_sleep_hours=_hours(stages.get("light"), 2), sleep_stages=stages or None,
        stress_level=stress.level() if stress else None, steps=steps.total() if steps else None,
        body_battery=battery.level() if battery else None,
        vo2_max=_first(metrics.vo2() if metrics else None, training.vo2() if training else None),
        fitness_age=metrics.fitness_age() if metrics else None,
        training_status=training.status_key() if training else None, acute_load=training.load() if training else None,
        spo2=spo2.reading() if spo2 else None, respiration=resp.reading() if resp else None,
    )


def fetch_feed(api, feed, day, call):
    try:
        raw = call(api, feed.method, day)
        return raw, feed.model.parse(raw)
    except Exception as exc:
        logger.warning("%s %s failed: %s", feed.name, day, exc)
        return None, None


def _raw_ok(raw) -> bool:
    return isinstance(raw, (dict, list)) or (isinstance(raw, (int, float)) and not isinstance(raw, bool))


def day_records(user_id, uid, day, fetched, synced_at):
    summary = summary_from({name: model for name, (_raw, model) in fetched.items()})
    bio = summary.model_dump(exclude_none=True)
    bio.update({"user_id": uid, "date": day, "source": "garmin", "updated_at": synced_at})
    daily = {"user_id": user_id, "date": day, "synced_at": synced_at}
    wrote = False
    if "steps" in fetched and _raw_ok(fetched["steps"][0]):
        daily["steps"] = fetched["steps"][0]
        wrote = True
    if "heart_rate" in fetched and _raw_ok(fetched["heart_rate"][0]):
        daily["heartrate"] = fetched["heart_rate"][0]
        wrote = True
    if summary.resting_hr is not None:
        daily["resting_hr"] = summary.resting_hr
        wrote = True
    if summary.stress_level is not None:
        daily["stress"] = summary.stress_level
        wrote = True
    sleep_doc = None
    if "sleep" in fetched and isinstance(fetched["sleep"][0], dict):
        sleep_doc = {"user_id": user_id, "date": day, "sleep_data": fetched["sleep"][0], "synced_at": synced_at}
    keep = any(key not in {"user_id", "date", "source", "updated_at"} for key in bio)
    return (daily if wrote else None), sleep_doc, (bio if keep else None)
