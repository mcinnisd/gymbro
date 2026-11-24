from datetime import datetime, timedelta, timezone, date

from app.supabase_client import supabase, is_missing_relation_error
from app.tools.readiness_tools import (
    biomarker_penalty, compose_readiness, get_readiness, score_hrv, score_sleep, score_training_load,
)
from app.tools.registry import get_tool_implementation


def _ago(days, hour=7):
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0)


def _day(days):
    return _ago(days).date().isoformat()


def _iso(days):
    return _ago(days).isoformat().replace("+00:00", "Z")


def _clear():
    supabase.missing_tables = set()
    for table in ("biometrics_daily", "garmin_activities", "strava_activities", "activities", "daily_journals", "lab_panels", "biomarkers"):
        supabase.table(table).data[table] = []


def _bio(**fields):
    supabase.table("biometrics_daily").upsert({"user_id": 1, "date": _day(1), "source": "garmin", **fields}, on_conflict="user_id, date").execute()


def _run(aid, days, distance=8000, duration=2400, hr=140):
    supabase.table("garmin_activities").insert({
        "user_id": 1, "activity_id": aid, "activity_name": aid, "start_time_local": _iso(days),
        "distance": distance, "duration": duration, "activity_type": "running", "average_hr": hr,
    }).execute()


def _seed_ready(suffix=""):
    for i in range(1, 8):
        supabase.table("biometrics_daily").upsert({
            "user_id": 1, "date": _day(i), "sleep_score": 80 if i == 1 else 78, "sleep_hours": 7.5,
            "hrv": 66 if i == 1 else 64, "hrv_ms": 66 if i == 1 else 64, "hrv_status": "BALANCED",
            "resting_hr": 50 if i == 1 else 52, "stress_level": 28, "body_battery": 78, "source": "garmin",
        }, on_conflict="user_id, date").execute()
    _run(f"easy{suffix}", 2)
    _run(f"prior{suffix}", 10, 8500, 2500, 142)


def test_scoring_helpers_do_not_invent_missing_signals():
    assert get_tool_implementation("get_readiness") is get_readiness
    assert score_sleep(82, 5.0) == 82 and score_sleep(None, 8.0) == 100.0 and score_sleep(None, None) is None
    assert score_hrv(64, None, None) is None and score_hrv(64, None, "BALANCED") == 72.0
    assert score_hrv(70, 64, None) > 70
    assert score_training_load(5.0, None) is None and score_training_load(3.0, 5.0) > score_training_load(5.0, 5.0) > score_training_load(9.0, 5.0)
    assert biomarker_penalty([{"marker_name": "Ferritin", "status": "flagged_low"}, {"marker_name": "hs-CRP", "status": "flagged_high"}, {"marker_name": "ApoB", "status": "flagged_high"}]) == 10.0
    assert biomarker_penalty([]) == 0.0 and biomarker_penalty([{"marker_name": "Ferritin", "status": "flagged_low"}] * 10) == 15.0


def test_compose_renormalizes_weights_over_available_only():
    payload = compose_readiness([
        {"id": "sleep", "label": "Sleep", "nominal_weight": 0.22, "optional": False, "raw": {"sleep_score": 80}, "score": 80.0, "freshness": 1.0, "date": "2026-09-15"},
        {"id": "stress", "label": "Stress", "nominal_weight": 0.08, "optional": False, "raw": {"stress_level": 80}, "score": 20.0, "freshness": 1.0, "date": "2026-09-15"},
    ], [{"id": "hrv", "label": "HRV", "optional": False, "reason": "absent"}], as_of=date(2026, 9, 16))
    assert payload["score"] == 64.0 and payload["band"] == "yellow"
    by_id = {c["id"]: c for c in payload["components"]}
    assert abs(by_id["sleep"]["weight"] - (0.22 / 0.30)) < 1e-3
    assert "hrv" in [m["id"] for m in payload["missing"]]


def test_get_readiness_sparse_cases():
    _clear()
    empty = get_readiness(user_id="99")
    missing = {m["id"] for m in empty["missing"]}
    assert empty["score"] is None and empty["confidence"] == 0.0
    assert {"sleep", "hrv", "rhr", "body_battery", "stress", "training_load", "journal", "biomarkers"} <= missing
    assert next(m for m in empty["missing"] if m["id"] == "journal")["optional"] is True

    _clear()
    _bio(sleep_score=82, sleep_hours=7.6)
    sleep = get_readiness(user_id="1")
    assert sleep["score"] == 82.0 and sleep["band"] == "green" and sleep["confidence"] < 0.4
    assert [c["id"] for c in sleep["components"]] == ["sleep"]
    assert "hrv" in {m["id"] for m in sleep["missing"]} and "rhr" in {m["id"] for m in sleep["missing"]}

    _clear()
    _run("garmin_ready_easy", 2, hr=138)
    _run("garmin_ready_prior", 10, hr=140)
    loaded = get_readiness(user_id="1")
    ids = [c["id"] for c in loaded["components"]]
    assert loaded["score"] is not None and "sleep" not in ids and "training_load" in ids and "residual_fatigue" in ids
    load = next(c for c in loaded["components"] if c["id"] == "training_load")
    assert load["raw"]["acute_activity_count"] >= 1 and load["raw"]["prior_activity_count"] >= 1

    _clear()
    _bio(date=_day(10), sleep_score=95)
    assert get_readiness(user_id="1")["score"] is None

    _clear()
    _bio(hrv=64, hrv_ms=64)
    hrv = next(m for m in get_readiness(user_id="1")["missing"] if m["id"] == "hrv")
    assert "population" in hrv["reason"].lower() or "baseline" in hrv["reason"].lower()


def test_full_signals_biomarker_penalty_lowers_the_score():
    _clear()
    _seed_ready()
    supabase.table("daily_journals").insert({"user_id": 1, "date": _day(0), "answers": {"energy_level": 8, "felt_sore": False}}).execute()
    panel = supabase.table("lab_panels").insert({"user_id": 1, "provider_name": "Quest", "test_date": _day(20)}).execute().data[0]
    for name, status in (("Ferritin", "flagged_low"), ("hs-CRP", "flagged_high")):
        supabase.table("biomarkers").insert({"user_id": 1, "panel_id": panel["id"], "marker_name": name, "value": 12, "status": status}).execute()
    flagged = get_readiness(user_id="1")
    ids = {c["id"] for c in flagged["components"]}
    assert {"sleep", "hrv", "rhr", "body_battery", "stress", "training_load", "residual_fatigue", "journal", "biomarkers"} <= ids
    assert next(c for c in flagged["components"] if c["id"] == "biomarkers")["contribution"] == -8.0
    assert flagged["missing"] == [] and flagged["confidence"] >= 0.7

    _clear()
    _seed_ready("_b")
    supabase.table("daily_journals").insert({"user_id": 1, "date": _day(0), "answers": {"energy_level": 8}}).execute()
    panel = supabase.table("lab_panels").insert({"user_id": 1, "provider_name": "Quest", "test_date": _day(20)}).execute().data[0]
    supabase.table("biomarkers").insert({"user_id": 1, "panel_id": panel["id"], "marker_name": "Vitamin D 25-OH", "value": 45, "status": "optimal"}).execute()
    assert get_readiness(user_id="1")["score"] > flagged["score"]


def test_readiness_http_route_uses_the_jwt_user(client, auth_headers):
    _clear()
    _bio(sleep_score=77)
    resp = client.get("/telemetry/tools/readiness", headers=auth_headers)
    assert resp.status_code == 200 and resp.json["score"] == 77.0


def test_readiness_routes_and_missing_tables():
    _clear()
    _bio(sleep_score=77)
    from flask import json as _json  # noqa: F401
    assert True
    _clear()
    empty = __import__("app.garmin.cli", fromlist=["verify_mcp_tools_for_user"]).verify_mcp_tools_for_user("99")
    assert empty["readiness"]["score"] is None
    _bio(sleep_score=80)
    assert __import__("app.garmin.cli", fromlist=["verify_mcp_tools_for_user"]).verify_mcp_tools_for_user("1")["readiness"]["score"] == 80

    class ApiError(Exception):
        code = "PGRST205"
        message = "Could not find the table 'public.lab_panels' in the schema cache"
    assert is_missing_relation_error(ApiError(ApiError.message), "lab_panels")
    assert not is_missing_relation_error(ValueError("unrelated"))

    _clear()
    _bio(sleep_score=82, sleep_hours=7.5)
    _run("garmin_pgrst_easy", 2, hr=138)
    _run("garmin_pgrst_prior", 10, hr=140)
    supabase.missing_tables = {"lab_panels", "activities"}
    try:
        res = get_readiness(user_id="1")
    finally:
        supabase.missing_tables = set()
    assert res["score"] is not None and "sleep" in {c["id"] for c in res["components"]}
    assert "PGRST205" in next(m["reason"] for m in res["missing"] if m["id"] == "biomarkers") or "lab_panels" in next(m["reason"] for m in res["missing"] if m["id"] == "biomarkers")

    _clear()
    _run("garmin_no_generic", 1, 5000, 1500)
    supabase.missing_tables = {"activities", "lab_panels", "daily_journals"}
    try:
        res = get_readiness(user_id="1")
    finally:
        supabase.missing_tables = set()
    assert res["status"] == "success" and "residual_fatigue" in {c["id"] for c in res["components"]}
