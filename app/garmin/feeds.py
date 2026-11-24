"""Typed Garmin payloads and the per-type refresh registry.

Each feed parses on its own. A missing or invalid payload becomes None and
does not drop the other feeds for that day. Fields Garmin omits stay None.
"""
from __future__ import annotations

import logging
from datetime import date
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationError, field_validator

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


def _map(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


Num = Annotated[Optional[float], BeforeValidator(_num)]


class Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @classmethod
    def parse(cls, raw: Any) -> Optional["Loose"]:
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if isinstance(raw, bool) or raw is None:
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
    activityType: Optional[dict] = None
    averageHR: Num = None
    maxHR: Num = None
    elevationGain: Num = None
    averageSpeed: Num = None
    maxSpeed: Num = None

    @field_validator("activityType", mode="before")
    @classmethod
    def _type_obj(cls, value):
        return value if isinstance(value, dict) else None

    def type_key(self) -> Optional[str]:
        return _map(self.activityType).get("typeKey")

    def row(self, user_id, details, synced_at, raw) -> Optional[dict]:
        if self.activityId in (None, ""):
            return None
        return {
            "user_id": user_id,
            "activity_id": str(self.activityId),
            "activity_name": self.activityName,
            "start_time_local": self.startTimeLocal,
            "distance": self.distance,
            "duration": self.duration,
            "calories": self.calories,
            "activity_type": self.type_key(),
            "average_hr": self.averageHR,
            "max_hr": self.maxHR,
            "elevation_gain": self.elevationGain,
            "average_speed": self.averageSpeed,
            "max_speed": self.maxSpeed,
            "raw_data": raw,
            "details": details,
            "synced_at": synced_at,
        }


class StepsPayload(Loose):
    steps: Optional[list] = None
    totalSteps: Num = None
    value: Num = None

    @classmethod
    def parse(cls, raw: Any) -> Optional["StepsPayload"]:
        if isinstance(raw, list):
            raw = {"steps": raw}
        return super().parse(raw)

    def total(self) -> Optional[int]:
        if isinstance(self.steps, list) and self.steps:
            nums = []
            for item in self.steps:
                nums.append(_num(item.get("steps") if isinstance(item, dict) else item))
            found = [int(n) for n in nums if n is not None]
            if found:
                return sum(found)
        for candidate in (self.totalSteps, self.value):
            if candidate is not None:
                return int(candidate)
        return None


class SleepPayload(Loose):
    dailySleepDTO: Optional[dict] = None
    sleepLevels: Optional[list] = None
    sleepQualityScore: Num = None
    overallSleepScore: Num = None
    totalSleepSeconds: Num = None

    @field_validator("dailySleepDTO", mode="before")
    @classmethod
    def _dto(cls, value):
        return value if isinstance(value, dict) else None

    def _dto_map(self) -> dict:
        return _map(self.dailySleepDTO)

    def score(self) -> Optional[float]:
        overall = _map(_map(self._dto_map().get("sleepScores")).get("overall"))
        return _num(overall.get("value")) or self.sleepQualityScore or self.overallSleepScore

    def seconds(self) -> Optional[float]:
        return _num(self._dto_map().get("sleepTimeSeconds")) or self.totalSleepSeconds

    def stage_seconds(self) -> dict:
        dto = self._dto_map()
        return {name: _num(dto.get(f"{name}SleepSeconds")) for name in ("deep", "rem", "light", "awake")}


class HeartRatePayload(Loose):
    restingHeartRate: Num = None
    value: Num = None


class RhrPayload(Loose):
    allMetrics: Optional[dict] = None
    value: Num = None

    def resting(self) -> Optional[float]:
        if self.value is not None:
            return self.value
        metrics = _map(_map(self.allMetrics).get("metricsMap"))
        vals = metrics.get("WELLNESS_RESTING_HEART_RATE") or []
        if isinstance(vals, list) and vals:
            return _num(vals[0].get("value") if isinstance(vals[0], dict) else vals[0])
        return None


class StressPayload(Loose):
    avgStressLevel: Num = None
    value: Num = None

    def level(self) -> Optional[float]:
        return self.avgStressLevel if self.avgStressLevel is not None else self.value


class HrvPayload(Loose):
    hrvSummary: Optional[dict] = None
    lastNight5MinHigh: Num = None
    value: Num = None

    @field_validator("hrvSummary", mode="before")
    @classmethod
    def _summary(cls, value):
        return value if isinstance(value, dict) else None

    def reading(self) -> Optional[float]:
        summary = _map(self.hrvSummary)
        return _num(summary.get("lastNightAvg")) or _num(summary.get("weeklyAvg")) or self.lastNight5MinHigh or self.value

    def status(self) -> Optional[str]:
        summary = _map(self.hrvSummary)
        text = summary.get("status")
        return text.strip() if isinstance(text, str) and text.strip() else None


class GenericVo2(Loose):
    vo2MaxValue: Num = None
    vo2MaxPrecision: Num = None


class RecentVo2(Loose):
    generic: Optional[GenericVo2] = None
    vo2Max: Num = None

    @field_validator("generic", mode="before")
    @classmethod
    def _generic(cls, value):
        return value if isinstance(value, dict) else None


class UserTrainingStatus(Loose):
    trainingStatusKey: Optional[str] = None


class TrainingStatusPayload(Loose):
    trainingStatusKey: Optional[str] = None
    trainingStatus: Optional[Any] = None
    userTrainingStatus: Optional[UserTrainingStatus] = None
    acuteTrainingLoad: Num = None
    acuteLoad: Num = None
    mostRecentVO2Max: Optional[RecentVo2] = None

    @field_validator("userTrainingStatus", "mostRecentVO2Max", mode="before")
    @classmethod
    def _nested(cls, value):
        return value if isinstance(value, dict) else None

    def status_key(self) -> Optional[str]:
        if isinstance(self.trainingStatusKey, str) and self.trainingStatusKey.strip():
            return self.trainingStatusKey
        if isinstance(self.trainingStatus, str) and self.trainingStatus.strip():
            return self.trainingStatus
        nested = self.userTrainingStatus.trainingStatusKey if self.userTrainingStatus else None
        return nested if isinstance(nested, str) and nested.strip() else None

    def load(self) -> Optional[float]:
        return self.acuteTrainingLoad if self.acuteTrainingLoad is not None else self.acuteLoad

    def vo2(self) -> Optional[float]:
        recent = self.mostRecentVO2Max
        if recent is None:
            return None
        generic = recent.generic.vo2MaxValue if recent.generic else None
        return generic if generic is not None else recent.vo2Max


class MaxMetricsPayload(Loose):
    generic: Optional[GenericVo2] = None
    vo2Max: Num = None
    vo2MaxRunning: Num = None
    vo2MaxValue: Num = None
    fitnessAge: Num = None
    value: Num = None

    @field_validator("generic", mode="before")
    @classmethod
    def _generic(cls, value):
        return value if isinstance(value, dict) else None

    def vo2(self) -> Optional[float]:
        generic = self.generic
        if generic and generic.vo2MaxValue is not None:
            return generic.vo2MaxValue
        if generic and generic.vo2MaxPrecision is not None:
            return generic.vo2MaxPrecision
        return self.vo2Max if self.vo2Max is not None else self.vo2MaxRunning or self.vo2MaxValue or self.value

    def fitness_age(self) -> Optional[float]:
        return self.fitnessAge


class BodyBatteryPayload(Loose):
    highestBodyBattery: Num = None
    currentBodyBattery: Num = None
    bodyBattery: Num = None
    value: Num = None
    charged: Num = None
    drained: Num = None
    bodyBatteryValuesArray: Optional[list] = None

    def level(self) -> Optional[int]:
        for candidate in (self.highestBodyBattery, self.currentBodyBattery, self.bodyBattery, self.value):
            if candidate is not None:
                return int(candidate)
        latest = None
        for point in self.bodyBatteryValuesArray or []:
            if isinstance(point, (list, tuple)) and len(point) > 1:
                reading = _num(point[1])
                if reading is not None:
                    latest = int(reading)
        return latest


class Spo2Payload(Loose):
    averageSpO2: Num = None
    latestSpO2: Num = None
    avgSpO2: Num = None
    value: Num = None

    def reading(self) -> Optional[float]:
        for candidate in (self.averageSpO2, self.latestSpO2, self.avgSpO2, self.value):
            if candidate is not None:
                return candidate
        return None


class RespirationPayload(Loose):
    avgWakingRespirationValue: Num = None
    avgSleepRespirationValue: Num = None
    averageRespirationValue: Num = None
    value: Num = None

    def reading(self) -> Optional[float]:
        for candidate in (
            self.avgWakingRespirationValue,
            self.avgSleepRespirationValue,
            self.averageRespirationValue,
            self.value,
        ):
            if candidate is not None:
                return candidate
        return None


class DailySummary(Loose):
    """Athlete-facing day. Missing metrics stay None, never zero."""
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


class Kind(str, Enum):
    recent = "recent"          # today and yesterday, otherwise only if incomplete
    shell = "shell"            # refetch empty shells for SHELL_DAYS
    incremental = "incremental"


class Feed(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    method: str
    model: type
    kind: Kind
    shell_days: int = SHELL_DAYS


FEEDS: tuple[Feed, ...] = (
    Feed(name="activities", method="get_activities", model=ActivityPayload, kind=Kind.incremental),
    Feed(name="steps", method="get_steps_data", model=StepsPayload, kind=Kind.recent),
    Feed(name="heart_rate", method="get_heart_rates", model=HeartRatePayload, kind=Kind.recent),
    Feed(name="rhr", method="get_rhr_day", model=RhrPayload, kind=Kind.recent),
    Feed(name="stress", method="get_stress_data", model=StressPayload, kind=Kind.recent),
    Feed(name="sleep", method="get_sleep_data", model=SleepPayload, kind=Kind.shell),
    Feed(name="hrv", method="get_hrv_data", model=HrvPayload, kind=Kind.shell),
    Feed(name="max_metrics", method="get_max_metrics", model=MaxMetricsPayload, kind=Kind.recent),
    Feed(name="training_status", method="get_training_status", model=TrainingStatusPayload, kind=Kind.recent),
    Feed(name="body_battery", method="get_body_battery", model=BodyBatteryPayload, kind=Kind.recent),
    Feed(name="spo2", method="get_spo2_data", model=Spo2Payload, kind=Kind.recent),
    Feed(name="respiration", method="get_respiration_data", model=RespirationPayload, kind=Kind.recent),
)

DAILY_FEEDS: tuple[Feed, ...] = tuple(feed for feed in FEEDS if feed.kind != Kind.incremental)
_FEED_BY_NAME = {feed.name: feed for feed in FEEDS}


def is_empty_shell(sleep_data: Any) -> bool:
    """No session id, levels, or start/end. Those days are not finished."""
    data = sleep_data if isinstance(sleep_data, dict) else {}
    dto = _map(data.get("dailySleepDTO"))
    levels = data.get("sleepLevels") if isinstance(data.get("sleepLevels"), list) else []
    if not levels and isinstance(dto.get("sleepLevels"), list):
        levels = dto["sleepLevels"]
    raw_id = dto.get("id")
    has_id = raw_id not in (None, "") and str(raw_id).strip().lower() not in {"", "null", "none"}
    return not has_id and not levels and dto.get("sleepStartTimestampGMT") is None and dto.get("sleepEndTimestampGMT") is None


class DaySnapshot:
    def __init__(self):
        self.ok: dict[str, set] = {}
        self.shells: set = set()

    def complete(self, name: str, day: str) -> bool:
        return day in self.ok.get(name, ())

    def mark(self, name: str, day: str) -> None:
        if day:
            self.ok.setdefault(name, set()).add(day)


def feed_due(feed: Feed, day: date, today: date, force: bool, snap: DaySnapshot) -> bool:
    """Whether this type should be fetched for a day already inside the sync window."""
    if feed.kind == Kind.incremental:
        return False
    if force:
        return True
    key = day.isoformat()
    age = (today - day).days
    if feed.kind == Kind.recent and 0 <= age <= 1:
        return True
    # Empty shells are retried only for shell_days. Older shells stay put.
    if feed.kind == Kind.shell and key in snap.shells:
        return 0 <= age <= feed.shell_days
    return not snap.complete(feed.name, key)


def _day_key(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def load_snapshot(user_id, uid, start: date, end: date) -> DaySnapshot:
    snap = DaySnapshot()
    if not supabase or start is None:
        return snap
    start_s, end_s = start.isoformat(), end.isoformat()

    def _rows(table, columns, uid_value):
        return supabase.table(table).select(columns).eq("user_id", uid_value).gte("date", start_s).lte("date", end_s).execute().data or []

    try:
        for row in _rows(
            "biometrics_daily",
            "date,resting_hr,hrv,sleep_score,steps,body_battery,stress_level,vo2_max,spo2,respiration,training_status",
            uid,
        ):
            day = _day_key(row.get("date"))
            pairs = (
                ("rhr", "resting_hr"),
                ("hrv", "hrv"),
                ("sleep", "sleep_score"),
                ("steps", "steps"),
                ("body_battery", "body_battery"),
                ("stress", "stress_level"),
                ("max_metrics", "vo2_max"),
                ("spo2", "spo2"),
                ("respiration", "respiration"),
                ("training_status", "training_status"),
            )
            for name, column in pairs:
                if row.get(column) is not None:
                    snap.mark(name, day)
    except Exception as exc:
        logger.warning("biometrics snapshot failed: %s", exc)
    try:
        seen = set()
        for sleep_uid in (user_id, uid):
            if sleep_uid in seen:
                continue
            seen.add(sleep_uid)
            for row in _rows("garmin_sleep", "date,sleep_data", sleep_uid):
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
        for row in _rows("garmin_daily", "date,steps,heartrate,stress,resting_hr", user_id):
            day = _day_key(row.get("date"))
            if row.get("steps") is not None:
                snap.mark("steps", day)
            if row.get("heartrate") is not None:
                snap.mark("heart_rate", day)
            if row.get("stress") is not None:
                snap.mark("stress", day)
            if row.get("resting_hr") is not None:
                snap.mark("rhr", day)
    except Exception as exc:
        logger.warning("garmin_daily snapshot failed: %s", exc)
    return snap


def _hours(seconds: Optional[float], places: int) -> Optional[float]:
    if not seconds or seconds <= 0:
        return None
    return round(seconds / 3600.0, places)


def summary_from(parsed: dict) -> DailySummary:
    """Build the mirrored day from whichever feeds parsed. Others stay None."""
    sleep: Optional[SleepPayload] = parsed.get("sleep")
    hrv: Optional[HrvPayload] = parsed.get("hrv")
    rhr: Optional[RhrPayload] = parsed.get("rhr")
    heart: Optional[HeartRatePayload] = parsed.get("heart_rate")
    stress: Optional[StressPayload] = parsed.get("stress")
    steps: Optional[StepsPayload] = parsed.get("steps")
    battery: Optional[BodyBatteryPayload] = parsed.get("body_battery")
    training: Optional[TrainingStatusPayload] = parsed.get("training_status")
    metrics: Optional[MaxMetricsPayload] = parsed.get("max_metrics")
    spo2: Optional[Spo2Payload] = parsed.get("spo2")
    resp: Optional[RespirationPayload] = parsed.get("respiration")
    stages = {}
    if sleep:
        for name, seconds in sleep.stage_seconds().items():
            if seconds is not None:
                stages[name] = int(seconds)
    vo2 = metrics.vo2() if metrics else None
    if vo2 is None and training:
        vo2 = training.vo2()
    resting = rhr.resting() if rhr else None
    if resting is None and heart:
        resting = heart.restingHeartRate
    return DailySummary(
        resting_hr=resting,
        hrv=hrv.reading() if hrv else None,
        hrv_ms=hrv.reading() if hrv else None,
        hrv_status=hrv.status() if hrv else None,
        sleep_score=sleep.score() if sleep else None,
        sleep_hours=_hours(sleep.seconds() if sleep else None, 1),
        deep_sleep_hours=_hours(stages.get("deep"), 2),
        rem_sleep_hours=_hours(stages.get("rem"), 2),
        light_sleep_hours=_hours(stages.get("light"), 2),
        sleep_stages=stages or None,
        stress_level=stress.level() if stress else None,
        steps=steps.total() if steps else None,
        body_battery=battery.level() if battery else None,
        vo2_max=vo2,
        fitness_age=metrics.fitness_age() if metrics else None,
        training_status=training.status_key() if training else None,
        acute_load=training.load() if training else None,
        spo2=spo2.reading() if spo2 else None,
        respiration=resp.reading() if resp else None,
    )


def fetch_feed(api, feed: Feed, day: str, call):
    """Fetch and parse one type. Failures stay local to that type."""
    try:
        raw = call(api, feed.method, day)
        return raw, feed.model.parse(raw)
    except Exception as exc:
        logger.warning("%s %s failed: %s", feed.name, day, exc)
        return None, None


def raw_ok(raw: Any) -> bool:
    return isinstance(raw, (dict, list)) or (isinstance(raw, (int, float)) and not isinstance(raw, bool))


def day_records(user_id, uid, day: str, fetched: dict, synced_at: str):
    """Persist only feeds that returned a payload. Unfetched fields are omitted."""
    summary = summary_from({name: model for name, (_raw, model) in fetched.items()})
    bio = summary.model_dump(exclude_none=True)
    bio.update({"user_id": uid, "date": day, "source": "garmin", "updated_at": synced_at})
    daily = {"user_id": user_id, "date": day, "synced_at": synced_at}
    wrote_daily = False
    if "steps" in fetched and raw_ok(fetched["steps"][0]):
        daily["steps"] = fetched["steps"][0]
        wrote_daily = True
    if "heart_rate" in fetched and raw_ok(fetched["heart_rate"][0]):
        daily["heartrate"] = fetched["heart_rate"][0]
        wrote_daily = True
    if summary.resting_hr is not None:
        daily["resting_hr"] = summary.resting_hr
        wrote_daily = True
    if summary.stress_level is not None:
        daily["stress"] = summary.stress_level
        wrote_daily = True
    sleep_doc = None
    if "sleep" in fetched and isinstance(fetched["sleep"][0], dict):
        sleep_doc = {
            "user_id": user_id,
            "date": day,
            "sleep_data": fetched["sleep"][0],
            "synced_at": synced_at,
        }
    has_metric = any(key not in {"user_id", "date", "source", "updated_at"} for key in bio)
    return (daily if wrote_daily else None), sleep_doc, (bio if has_metric else None)
