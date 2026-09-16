"""
Sparse-aware athlete readiness score.

Combines Garmin-first wellness (biometrics_daily), unified activities,
optional daily journals, and flagged biomarkers. Missing signals are
omitted — never imputed — and remaining weights are renormalized.

See docs/readiness.md for the formula.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from app.supabase_client import supabase
from app.health_hub.ingestion_service import get_unified_activities

logger = logging.getLogger(__name__)

# Nominal weights sum to 1.0. Biomarkers are a post-hoc penalty, not a weight.
COMPONENT_SPECS: Tuple[Dict[str, Any], ...] = (
    {"id": "sleep", "label": "Sleep", "nominal_weight": 0.22, "optional": False},
    {"id": "hrv", "label": "HRV", "nominal_weight": 0.18, "optional": False},
    {"id": "rhr", "label": "Resting heart rate", "nominal_weight": 0.12, "optional": False},
    {"id": "body_battery", "label": "Body Battery", "nominal_weight": 0.10, "optional": False},
    {"id": "stress", "label": "Stress", "nominal_weight": 0.08, "optional": False},
    {"id": "training_load", "label": "Training load (7d vs baseline)", "nominal_weight": 0.15, "optional": False},
    {"id": "residual_fatigue", "label": "Residual fatigue", "nominal_weight": 0.08, "optional": False},
    {"id": "journal", "label": "Subjective journal", "nominal_weight": 0.07, "optional": True},
)

BIOMARKER_SPEC = {
    "id": "biomarkers",
    "label": "Flagged biomarkers",
    "optional": True,
}

HRV_STATUS_SCORES = {
    "poor": 25.0,
    "low": 35.0,
    "unbalanced": 40.0,
    "below_baseline": 40.0,
    "low_unbalanced": 35.0,
    "balanced": 72.0,
    "normal": 70.0,
    "good": 80.0,
    "prime": 92.0,
    "high": 88.0,
    "excellent": 90.0,
    "above_baseline": 85.0,
}

HARD_SESSION_KEYWORDS = (
    "tempo", "interval", "race", "threshold", "vo2", "repeat",
    "hard", "workout", "track", "anaerobic",
)

RECOVERY_MARKER_NEEDLES = (
    "hs-crp", "crp", "ferritin", "creatine kinase", "ck",
    "vitamin d", "testosterone", "cortisol", "hemoglobin",
)

WELLNESS_MAX_AGE_DAYS = 7
JOURNAL_MAX_AGE_DAYS = 2
BIOMARKER_MAX_AGE_DAYS = 90
ACTIVITY_LOOKBACK_DAYS = 28
HRV_RHR_BASELINE_MIN_POINTS = 3

BAND_GREEN = 70.0
BAND_YELLOW = 45.0
MAX_BIOMARKER_PENALTY = 15.0


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _as_float(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_date(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        if "T" in text:
            return datetime.fromisoformat(text).date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_datetime(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        d = _parse_date(raw)
        if d is None:
            return None
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _band_for_score(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= BAND_GREEN:
        return "green"
    if score >= BAND_YELLOW:
        return "yellow"
    return "red"


def _wellness_freshness(record_date: date, as_of: date) -> Optional[float]:
    age = (as_of - record_date).days
    if age < 0:
        return None
    if age <= 1:
        return 1.0
    if age > WELLNESS_MAX_AGE_DAYS:
        return None
    return round(max(0.2, 1.0 - (age - 1) / float(WELLNESS_MAX_AGE_DAYS - 1)), 3)


def _journal_freshness(record_date: date, as_of: date) -> Optional[float]:
    age = (as_of - record_date).days
    if age < 0 or age > JOURNAL_MAX_AGE_DAYS:
        return None
    if age <= 1:
        return 1.0
    return 0.5


def _biomarker_freshness(test_date: date, as_of: date) -> Optional[float]:
    age = (as_of - test_date).days
    if age < 0 or age > BIOMARKER_MAX_AGE_DAYS:
        return None
    if age <= 30:
        return 1.0
    return round(max(0.4, 1.0 - (age - 30) / 100.0), 3)


def score_sleep(sleep_score: Optional[float], sleep_hours: Optional[float]) -> Optional[float]:
    """Prefer Garmin sleep_score (0–100). Hours use a 7–9h physiological map — not an imputed score."""
    if sleep_score is not None:
        return round(_clamp(sleep_score), 1)
    if sleep_hours is None:
        return None
    hours = sleep_hours
    if 7.0 <= hours <= 9.0:
        return 100.0
    if hours < 7.0:
        return round(_clamp(100.0 - (7.0 - hours) * 25.0), 1)
    return round(_clamp(100.0 - (hours - 9.0) * 15.0, 40.0, 100.0), 1)


def score_hrv(
    value: Optional[float],
    baseline: Optional[float],
    status: Optional[str],
) -> Optional[float]:
    """Score HRV only from personal baseline and/or Garmin status. Raw ms alone is not scored."""
    status_score = None
    if status:
        key = str(status).strip().lower().replace(" ", "_").replace("-", "_")
        status_score = HRV_STATUS_SCORES.get(key)

    vs_baseline = None
    if value is not None and baseline is not None and baseline > 0:
        delta_pct = (value - baseline) / baseline
        vs_baseline = _clamp(70.0 + delta_pct * 150.0)

    if vs_baseline is not None and status_score is not None:
        return round(0.7 * vs_baseline + 0.3 * status_score, 1)
    if vs_baseline is not None:
        return round(vs_baseline, 1)
    if status_score is not None:
        return round(status_score, 1)
    return None


def score_rhr(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if value is None or baseline is None or baseline <= 0:
        return None
    delta_pct = (baseline - value) / baseline
    return round(_clamp(70.0 + delta_pct * 200.0), 1)


def score_body_battery(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(_clamp(value), 1)


def score_stress(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(_clamp(100.0 - value), 1)


def score_training_load(acute: Optional[float], chronic: Optional[float]) -> Optional[float]:
    """Readiness ACWR: lower acute vs chronic → more recovered. No chronic → skip (do not invent 0)."""
    if acute is None or chronic is None or chronic <= 0:
        return None
    ratio = acute / chronic
    if ratio <= 0.8:
        return round(_clamp(90.0 + (0.8 - ratio) * 12.5, 90.0, 100.0), 1)
    if ratio <= 1.2:
        return round(_clamp(90.0 - (ratio - 0.8) * 37.5, 75.0, 90.0), 1)
    if ratio <= 1.5:
        return round(_clamp(75.0 - (ratio - 1.2) * (25.0 / 0.3), 50.0, 75.0), 1)
    return round(_clamp(50.0 - (ratio - 1.5) * 40.0, 15.0, 50.0), 1)


def _activity_duration_hours(act: Dict[str, Any]) -> float:
    raw = act.get("duration_s")
    if raw is None:
        raw = act.get("duration")
    value = _as_float(raw) or 0.0
    if value > 300:
        return value / 3600.0
    if value > 12:
        return value / 60.0
    return value


def _activity_distance_km(act: Dict[str, Any]) -> float:
    raw = act.get("distance_m")
    if raw is None:
        raw = act.get("distance")
    value = _as_float(raw) or 0.0
    return value / 1000.0 if value > 100 else value


def _activity_training_load(act: Dict[str, Any]) -> Optional[float]:
    details = act.get("details") or act.get("raw_data") or {}
    if not isinstance(details, dict):
        details = {}
    for key in ("activityTrainingLoad", "activity_training_load", "trainingLoad"):
        load = _as_float(details.get(key))
        if load is not None:
            return load
    return _as_float(act.get("training_load"))


def is_hard_session(act: Dict[str, Any]) -> bool:
    name = str(act.get("name") or act.get("activity_name") or "").lower()
    if any(keyword in name for keyword in HARD_SESSION_KEYWORDS):
        return True
    hours = _activity_duration_hours(act)
    if hours >= 1.5:
        return True
    if _activity_distance_km(act) >= 16.0:
        return True
    avg_hr = _as_float(act.get("average_hr") or act.get("average_heartrate"))
    if avg_hr is not None and avg_hr >= 155:
        return True
    load = _activity_training_load(act)
    if load is not None and load >= 150:
        return True
    return False


def score_residual_fatigue(activities: List[Dict[str, Any]], as_of: date) -> Optional[float]:
    if not activities:
        return None
    as_of_end = datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59, tzinfo=timezone.utc)
    cutoff = as_of_end - timedelta(days=7)
    recent = []
    for act in activities:
        start = _parse_datetime(act.get("start_time_local") or act.get("start_time"))
        if start is None or start > as_of_end or start < cutoff:
            continue
        recent.append((start, act))
    if not recent:
        return None

    hardest_hours_ago = None
    for start, act in recent:
        if not is_hard_session(act):
            continue
        hours_ago = (as_of_end - start).total_seconds() / 3600.0
        if hardest_hours_ago is None or hours_ago < hardest_hours_ago:
            hardest_hours_ago = hours_ago

    if hardest_hours_ago is None:
        return 92.0
    if hardest_hours_ago <= 18:
        return 38.0
    if hardest_hours_ago <= 36:
        return 55.0
    if hardest_hours_ago <= 60:
        return 70.0
    if hardest_hours_ago <= 84:
        return 82.0
    return 90.0


def score_journal(answers: Optional[Dict[str, Any]]) -> Optional[float]:
    if not answers or not isinstance(answers, dict):
        return None
    energy = _as_float(answers.get("energy_level"))
    felt_sore = answers.get("felt_sore")
    soreness = answers.get("soreness")
    has_soreness = False
    if isinstance(soreness, str) and soreness.strip() and soreness.strip().lower() not in {"none", "no", "false"}:
        has_soreness = True
    elif isinstance(soreness, (int, float)) and float(soreness) >= 5:
        has_soreness = True

    if energy is None and felt_sore is None and not has_soreness:
        return None

    score = energy * 10.0 if energy is not None else 70.0
    if felt_sore is True:
        score -= 20.0
    if has_soreness:
        score -= 10.0
    return round(_clamp(score), 1)


def biomarker_penalty(flagged: List[Dict[str, Any]]) -> float:
    if not flagged:
        return 0.0
    penalty = 0.0
    for row in flagged:
        name = str(row.get("marker_name") or "").lower()
        if any(needle in name for needle in RECOVERY_MARKER_NEEDLES):
            penalty += 4.0
        else:
            penalty += 2.0
    return min(MAX_BIOMARKER_PENALTY, penalty)


def compose_readiness(
    present: List[Dict[str, Any]],
    missing: List[Dict[str, Any]],
    *,
    as_of: date,
    penalty: float = 0.0,
    penalty_raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Renormalize nominal weights over scored components and assemble the payload.

    `present` items: id, label, nominal_weight, optional, raw, score, freshness, date.
    Biomarker penalty is applied after the weighted average (not a fake biomarker value).
    """
    scored = [c for c in present if c.get("score") is not None]
    weight_sum = sum(float(c["nominal_weight"]) for c in scored)
    notes: List[str] = []

    components: List[Dict[str, Any]] = []
    composite = None
    if scored and weight_sum > 0:
        composite = 0.0
        for item in scored:
            used = float(item["nominal_weight"]) / weight_sum
            contribution = round(float(item["score"]) * used, 2)
            composite += contribution
            components.append({
                "id": item["id"],
                "label": item["label"],
                "raw": item.get("raw"),
                "score": item["score"],
                "contribution": contribution,
                "weight": round(used, 4),
                "nominal_weight": item["nominal_weight"],
                "missing": False,
                "freshness": item.get("freshness"),
                "date": item.get("date"),
            })
        composite = round(_clamp(composite - max(0.0, penalty)), 1)

    if penalty > 0 and penalty_raw is not None:
        components.append({
            "id": BIOMARKER_SPEC["id"],
            "label": BIOMARKER_SPEC["label"],
            "raw": penalty_raw,
            "score": None,
            "contribution": round(-penalty, 2),
            "weight": 0.0,
            "nominal_weight": 0.0,
            "missing": False,
            "freshness": penalty_raw.get("freshness"),
            "date": penalty_raw.get("test_date"),
        })
        notes.append(
            f"{penalty_raw.get('flagged_count', 0)} flagged biomarker(s) applied as a -{penalty:.0f}pt soft penalty."
        )
    elif penalty_raw is not None and penalty == 0:
        components.append({
            "id": BIOMARKER_SPEC["id"],
            "label": BIOMARKER_SPEC["label"],
            "raw": penalty_raw,
            "score": 100.0,
            "contribution": 0.0,
            "weight": 0.0,
            "nominal_weight": 0.0,
            "missing": False,
            "freshness": penalty_raw.get("freshness"),
            "date": penalty_raw.get("test_date"),
        })
        notes.append("Latest biomarker panel has no flags; no penalty applied.")

    total_nominal = sum(spec["nominal_weight"] for spec in COMPONENT_SPECS)
    coverage = (weight_sum / total_nominal) if total_nominal else 0.0
    if scored and weight_sum > 0:
        freshness_w = sum(float(c["nominal_weight"]) * float(c.get("freshness") or 0.0) for c in scored) / weight_sum
        confidence = round(min(0.98, coverage * (0.40 + 0.60 * freshness_w)), 3)
    else:
        confidence = 0.0

    band = _band_for_score(composite)
    ids_used = [c["id"] for c in scored]
    if composite is None:
        notes.insert(0, "Insufficient data: no recent sleep, wellness, training, or journal signals.")
        message = "Insufficient data for a readiness score (no recent sleep, wellness, or training signals)."
    else:
        notes.insert(
            0,
            f"Sparse-aware composite uses {len(scored)} of {len(COMPONENT_SPECS)} weighted components; "
            f"weights renormalized over available signals only.",
        )
        used_txt = ", ".join(ids_used) if ids_used else "none"
        missing_ids = [m["id"] for m in missing]
        miss_txt = ", ".join(missing_ids) if missing_ids else "none"
        message = (
            f"Readiness {composite:.0f}/100 ({band}), confidence {confidence:.2f}. "
            f"Used: {used_txt}. Missing: {miss_txt}."
        )

    stale = [c for c in scored if (c.get("freshness") or 1) < 0.7]
    for item in stale:
        notes.append(f"{item['label']} is {item.get('date')} (freshness {item.get('freshness')}); confidence reduced.")

    return {
        "status": "success",
        "score": composite,
        "band": band,
        "confidence": confidence,
        "as_of": as_of.isoformat(),
        "components": components,
        "missing": missing,
        "notes": notes,
        "message": message,
        "observation": message,
    }


def _latest_field(
    records: List[Dict[str, Any]],
    keys: Tuple[str, ...],
    as_of: date,
) -> Tuple[Optional[float], Optional[date], Optional[Dict[str, Any]]]:
    for row in records:
        row_date = _parse_date(row.get("date"))
        if row_date is None or row_date > as_of:
            continue
        freshness = _wellness_freshness(row_date, as_of)
        if freshness is None:
            continue
        for key in keys:
            value = _as_float(row.get(key))
            if value is not None:
                return value, row_date, row
    return None, None, None


def _baseline_mean(records: List[Dict[str, Any]], keys: Tuple[str, ...], as_of: date, exclude_date: Optional[date]) -> Optional[float]:
    values: List[float] = []
    cutoff = as_of - timedelta(days=28)
    for row in records:
        row_date = _parse_date(row.get("date"))
        if row_date is None or row_date > as_of or row_date < cutoff:
            continue
        if exclude_date is not None and row_date == exclude_date:
            continue
        for key in keys:
            value = _as_float(row.get(key))
            if value is not None:
                values.append(value)
                break
    if len(values) < HRV_RHR_BASELINE_MIN_POINTS:
        return None
    return sum(values) / len(values)


def _load_biometrics(user_id: Any, as_of: date) -> List[Dict[str, Any]]:
    if not supabase:
        return []
    cutoff = (as_of - timedelta(days=28)).isoformat()
    uid = int(user_id) if str(user_id).isdigit() else user_id
    res = (
        supabase.table("biometrics_daily")
        .select("*")
        .eq("user_id", uid)
        .gte("date", cutoff)
        .lte("date", as_of.isoformat())
        .order("date", desc=True)
        .execute()
    )
    return res.data or []


def _load_journal(user_id: Any, as_of: date) -> Optional[Dict[str, Any]]:
    if not supabase:
        return None
    cutoff = (as_of - timedelta(days=JOURNAL_MAX_AGE_DAYS)).isoformat()
    uid = int(user_id) if str(user_id).isdigit() else user_id
    res = (
        supabase.table("daily_journals")
        .select("*")
        .eq("user_id", uid)
        .gte("date", cutoff)
        .lte("date", as_of.isoformat())
        .order("date", desc=True)
        .limit(5)
        .execute()
    )
    rows = res.data or []
    for row in rows:
        row_date = _parse_date(row.get("date"))
        if row_date is None:
            continue
        if _journal_freshness(row_date, as_of) is None:
            continue
        return row
    return None


def _load_biomarkers(user_id: Any, as_of: date) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    if not supabase:
        return None, []
    uid = int(user_id) if str(user_id).isdigit() else user_id
    panels_res = (
        supabase.table("lab_panels")
        .select("*")
        .eq("user_id", uid)
        .order("test_date", desc=True)
        .limit(5)
        .execute()
    )
    panels = panels_res.data or []
    latest = None
    for panel in panels:
        test_date = _parse_date(panel.get("test_date"))
        if test_date is None:
            continue
        if _biomarker_freshness(test_date, as_of) is None:
            continue
        latest = panel
        break
    if latest is None:
        return None, []
    flagged_res = (
        supabase.table("biomarkers")
        .select("*")
        .eq("user_id", uid)
        .eq("panel_id", latest.get("id"))
        .execute()
    )
    rows = flagged_res.data or []
    flagged = [r for r in rows if r.get("status") in {"flagged_low", "flagged_high"}]
    return latest, flagged


def _missing_entry(spec: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "id": spec["id"],
        "label": spec["label"],
        "optional": bool(spec.get("optional")),
        "reason": reason,
    }


def get_readiness(user_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    """
    Composite readiness for one athlete. Never invents missing telemetry.

    Args:
        user_id: Server-bound athlete id (MCP strips client-supplied user_id).
        as_of: Optional YYYY-MM-DD (defaults to today UTC).
    """
    try:
        as_of_date = _parse_date(as_of) if as_of else _today()
        if as_of_date is None:
            as_of_date = _today()

        records = _load_biometrics(user_id, as_of_date)
        present: List[Dict[str, Any]] = []
        missing: List[Dict[str, Any]] = []
        spec_by_id = {s["id"]: s for s in COMPONENT_SPECS}

        # Sleep
        sleep_score, sleep_date, sleep_row = _latest_field(records, ("sleep_score",), as_of_date)
        sleep_hours = None
        hours_date = None
        hours_row = None
        if sleep_row is not None:
            sleep_hours = _as_float(sleep_row.get("sleep_hours"))
            hours_date, hours_row = sleep_date, sleep_row
        if sleep_hours is None:
            sleep_hours, hours_date, hours_row = _latest_field(records, ("sleep_hours",), as_of_date)
        sleep_used_date = sleep_date or hours_date
        sleep_used_row = sleep_row or hours_row
        sleep_val = score_sleep(sleep_score, sleep_hours)
        if sleep_val is not None and sleep_used_date is not None:
            present.append({
                **spec_by_id["sleep"],
                "raw": {
                    "sleep_score": sleep_score,
                    "sleep_hours": sleep_hours,
                    "source": (sleep_used_row or {}).get("source") or (sleep_used_row or {}).get("raw_source"),
                },
                "score": sleep_val,
                "freshness": _wellness_freshness(sleep_used_date, as_of_date),
                "date": sleep_used_date.isoformat(),
            })
        else:
            missing.append(_missing_entry(spec_by_id["sleep"], "No sleep_score or sleep_hours in the last 7 days"))

        # HRV
        hrv, hrv_date, hrv_row = _latest_field(records, ("hrv", "hrv_ms"), as_of_date)
        hrv_status = (hrv_row or {}).get("hrv_status") if hrv_row else None
        if hrv_status is None:
            for row in records:
                row_date = _parse_date(row.get("date"))
                if row_date is None or _wellness_freshness(row_date, as_of_date) is None:
                    continue
                if row.get("hrv_status"):
                    hrv_status = row.get("hrv_status")
                    if hrv_date is None:
                        hrv_date = row_date
                        hrv_row = row
                    break
        hrv_baseline = _baseline_mean(records, ("hrv", "hrv_ms"), as_of_date, hrv_date)
        hrv_val = score_hrv(hrv, hrv_baseline, hrv_status)
        if hrv_val is not None and hrv_date is not None:
            present.append({
                **spec_by_id["hrv"],
                "raw": {
                    "hrv_ms": hrv,
                    "hrv_status": hrv_status,
                    "baseline_ms": round(hrv_baseline, 1) if hrv_baseline is not None else None,
                    "source": (hrv_row or {}).get("source"),
                },
                "score": hrv_val,
                "freshness": _wellness_freshness(hrv_date, as_of_date),
                "date": hrv_date.isoformat(),
            })
        else:
            if hrv is not None and hrv_val is None:
                missing.append(_missing_entry(
                    spec_by_id["hrv"],
                    "HRV value present but no personal baseline (≥3 days) or Garmin status — omitted rather than inventing a population norm",
                ))
            else:
                missing.append(_missing_entry(spec_by_id["hrv"], "No HRV or hrv_status in the last 7 days"))

        # RHR
        rhr, rhr_date, rhr_row = _latest_field(records, ("resting_hr",), as_of_date)
        rhr_baseline = _baseline_mean(records, ("resting_hr",), as_of_date, rhr_date)
        rhr_val = score_rhr(rhr, rhr_baseline)
        if rhr_val is not None and rhr_date is not None:
            present.append({
                **spec_by_id["rhr"],
                "raw": {
                    "resting_hr_bpm": rhr,
                    "baseline_bpm": round(rhr_baseline, 1) if rhr_baseline is not None else None,
                    "source": (rhr_row or {}).get("source"),
                },
                "score": rhr_val,
                "freshness": _wellness_freshness(rhr_date, as_of_date),
                "date": rhr_date.isoformat(),
            })
        else:
            if rhr is not None and rhr_val is None:
                missing.append(_missing_entry(
                    spec_by_id["rhr"],
                    "Resting HR present but no personal baseline (≥3 days) — omitted rather than inventing a population norm",
                ))
            else:
                missing.append(_missing_entry(spec_by_id["rhr"], "No resting_hr in the last 7 days"))

        # Body battery
        bb, bb_date, bb_row = _latest_field(records, ("body_battery",), as_of_date)
        bb_val = score_body_battery(bb)
        if bb_val is not None and bb_date is not None:
            present.append({
                **spec_by_id["body_battery"],
                "raw": {"body_battery": bb, "source": (bb_row or {}).get("source")},
                "score": bb_val,
                "freshness": _wellness_freshness(bb_date, as_of_date),
                "date": bb_date.isoformat(),
            })
        else:
            missing.append(_missing_entry(spec_by_id["body_battery"], "No body_battery in the last 7 days"))

        # Stress
        stress, stress_date, stress_row = _latest_field(records, ("stress_level", "stress"), as_of_date)
        stress_val = score_stress(stress)
        if stress_val is not None and stress_date is not None:
            present.append({
                **spec_by_id["stress"],
                "raw": {"stress_level": stress, "source": (stress_row or {}).get("source")},
                "score": stress_val,
                "freshness": _wellness_freshness(stress_date, as_of_date),
                "date": stress_date.isoformat(),
            })
        else:
            missing.append(_missing_entry(spec_by_id["stress"], "No stress_level in the last 7 days"))

        # Activities (Garmin-first unified stream)
        start_date = (as_of_date - timedelta(days=ACTIVITY_LOOKBACK_DAYS)).isoformat()
        activities = get_unified_activities(
            user_id,
            start_date=start_date,
            end_date=(as_of_date + timedelta(days=1)).isoformat(),
            limit=200,
        )
        as_of_end = datetime(as_of_date.year, as_of_date.month, as_of_date.day, 23, 59, 59, tzinfo=timezone.utc)

        def _in_window(act: Dict[str, Any], start_days: int, end_days: int) -> bool:
            start = _parse_datetime(act.get("start_time_local") or act.get("start_time"))
            if start is None or start > as_of_end:
                return False
            age_days = (as_of_end - start).total_seconds() / 86400.0
            return start_days <= age_days < end_days

        acute_acts = [a for a in activities if _in_window(a, 0, 7)]
        prior_acts = [a for a in activities if _in_window(a, 7, 14)]

        def _volume(acts: List[Dict[str, Any]]) -> Tuple[float, float, Optional[float]]:
            hours = sum(_activity_duration_hours(a) for a in acts)
            km = sum(_activity_distance_km(a) for a in acts)
            loads = [_activity_training_load(a) for a in acts]
            load_vals = [v for v in loads if v is not None]
            load_sum = sum(load_vals) if load_vals else None
            return hours, km, load_sum

        acute_h, acute_km, acute_load = _volume(acute_acts)
        prior_h, prior_km, prior_load = _volume(prior_acts)

        load_score = None
        load_raw: Dict[str, Any] = {
            "acute_7d_hours": round(acute_h, 2),
            "prior_7d_hours": round(prior_h, 2),
            "acute_7d_km": round(acute_km, 2),
            "prior_7d_km": round(prior_km, 2),
            "acute_activity_count": len(acute_acts),
            "prior_activity_count": len(prior_acts),
        }
        if prior_load is not None and prior_load > 0 and acute_load is not None:
            load_score = score_training_load(acute_load, prior_load)
            load_raw["acute_training_load"] = acute_load
            load_raw["prior_training_load"] = prior_load
            load_raw["ratio"] = round(acute_load / prior_load, 3)
        elif prior_h > 0:
            load_score = score_training_load(acute_h, prior_h)
            load_raw["ratio"] = round(acute_h / prior_h, 3) if prior_h else None
        elif prior_km > 0:
            load_score = score_training_load(acute_km, prior_km)
            load_raw["ratio"] = round(acute_km / prior_km, 3) if prior_km else None

        if load_score is not None:
            present.append({
                **spec_by_id["training_load"],
                "raw": load_raw,
                "score": load_score,
                "freshness": 1.0 if acute_acts else 0.6,
                "date": as_of_date.isoformat(),
            })
        else:
            if acute_acts and not prior_acts:
                missing.append(_missing_entry(
                    spec_by_id["training_load"],
                    "7d volume present but no prior-week baseline — omitted rather than inventing chronic load",
                ))
            else:
                missing.append(_missing_entry(spec_by_id["training_load"], "No comparable 7d vs prior-7d training volume"))

        fatigue = score_residual_fatigue(activities, as_of_date)
        if fatigue is not None:
            hard = [a for a in acute_acts if is_hard_session(a)]
            present.append({
                **spec_by_id["residual_fatigue"],
                "raw": {
                    "recent_activity_count": len(acute_acts),
                    "hard_session_count_7d": len(hard),
                    "latest_hard": (hard[0].get("name") if hard else None),
                },
                "score": fatigue,
                "freshness": 1.0,
                "date": as_of_date.isoformat(),
            })
        else:
            missing.append(_missing_entry(
                spec_by_id["residual_fatigue"],
                "No unified activities in the last 7 days",
            ))

        # Journal (optional)
        journal = _load_journal(user_id, as_of_date)
        journal_score = score_journal((journal or {}).get("answers") if journal else None)
        if journal_score is not None and journal is not None:
            jdate = _parse_date(journal.get("date"))
            present.append({
                **spec_by_id["journal"],
                "raw": {
                    "energy_level": (journal.get("answers") or {}).get("energy_level"),
                    "felt_sore": (journal.get("answers") or {}).get("felt_sore"),
                    "soreness": (journal.get("answers") or {}).get("soreness"),
                },
                "score": journal_score,
                "freshness": _journal_freshness(jdate, as_of_date) if jdate else 0.5,
                "date": jdate.isoformat() if jdate else None,
            })
        else:
            missing.append(_missing_entry(
                spec_by_id["journal"],
                "No daily_journals row with energy/soreness in the last 2 days",
            ))

        # Biomarkers (optional soft penalty)
        panel, flagged = _load_biomarkers(user_id, as_of_date)
        penalty = 0.0
        penalty_raw = None
        if panel is None:
            missing.append(_missing_entry(
                BIOMARKER_SPEC,
                "No lab panel in the last 90 days",
            ))
        else:
            test_date = _parse_date(panel.get("test_date"))
            penalty = biomarker_penalty(flagged)
            penalty_raw = {
                "panel_id": panel.get("id"),
                "test_date": test_date.isoformat() if test_date else None,
                "flagged_count": len(flagged),
                "flagged": [
                    {"marker_name": f.get("marker_name"), "status": f.get("status"), "value": f.get("value")}
                    for f in flagged
                ],
                "freshness": _biomarker_freshness(test_date, as_of_date) if test_date else None,
            }

        return compose_readiness(
            present,
            missing,
            as_of=as_of_date,
            penalty=penalty,
            penalty_raw=penalty_raw,
        )
    except Exception as exc:
        logger.error("Error computing readiness for user %s: %s", user_id, exc)
        return {
            "status": "error",
            "score": None,
            "band": None,
            "confidence": 0.0,
            "as_of": as_of or _today().isoformat(),
            "components": [],
            "missing": [],
            "notes": [str(exc)],
            "message": str(exc),
        }
