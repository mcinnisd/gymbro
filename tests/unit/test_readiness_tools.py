from datetime import datetime, timedelta, timezone, date

from app.supabase_client import supabase
from app.tools.readiness_tools import (
    biomarker_penalty,
    compose_readiness,
    get_readiness,
    score_hrv,
    score_sleep,
    score_training_load,
)
from app.tools.registry import get_tool_implementation


def _recent_iso(days_ago: int, hour: int = 7) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def _recent_date(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()


def _clear_readiness_tables():
    for table in (
        "biometrics_daily",
        "garmin_activities",
        "strava_activities",
        "activities",
        "daily_journals",
        "lab_panels",
        "biomarkers",
    ):
        supabase.table(table).data[table] = []


def test_registry_binds_get_readiness():
    assert get_tool_implementation("get_readiness") is get_readiness


def test_score_sleep_prefers_score_and_maps_hours():
    assert score_sleep(82, 5.0) == 82
    assert score_sleep(None, 8.0) == 100.0
    assert score_sleep(None, 6.0) == 75.0
    assert score_sleep(None, None) is None


def test_score_hrv_does_not_invent_population_norm():
    assert score_hrv(64, None, None) is None
    assert score_hrv(64, None, "BALANCED") == 72.0
    vs = score_hrv(70, 64, None)
    assert vs is not None and vs > 70


def test_score_training_load_skips_missing_chronic():
    assert score_training_load(5.0, None) is None
    assert score_training_load(5.0, 0) is None
    balanced = score_training_load(5.0, 5.0)
    overloaded = score_training_load(9.0, 5.0)
    recovered = score_training_load(3.0, 5.0)
    assert recovered > balanced > overloaded


def test_biomarker_penalty_caps_and_weights_recovery_markers():
    flagged = [
        {"marker_name": "Ferritin", "status": "flagged_low"},
        {"marker_name": "hs-CRP", "status": "flagged_high"},
        {"marker_name": "ApoB", "status": "flagged_high"},
    ]
    # 4 + 4 + 2 = 10
    assert biomarker_penalty(flagged) == 10.0
    assert biomarker_penalty([]) == 0.0
    many = [{"marker_name": "Ferritin", "status": "flagged_low"}] * 10
    assert biomarker_penalty(many) == 15.0


def test_compose_renormalizes_weights_over_available_only():
    as_of = date(2026, 9, 16)
    payload = compose_readiness(
        [
            {
                "id": "sleep",
                "label": "Sleep",
                "nominal_weight": 0.22,
                "optional": False,
                "raw": {"sleep_score": 80},
                "score": 80.0,
                "freshness": 1.0,
                "date": "2026-09-15",
            },
            {
                "id": "stress",
                "label": "Stress",
                "nominal_weight": 0.08,
                "optional": False,
                "raw": {"stress_level": 80},
                "score": 20.0,
                "freshness": 1.0,
                "date": "2026-09-15",
            },
        ],
        [{"id": "hrv", "label": "HRV", "optional": False, "reason": "absent"}],
        as_of=as_of,
    )
    assert payload["score"] is not None
    # 80*(0.22/0.30) + 20*(0.08/0.30) = 58.667 + 5.333 = 64.0
    assert payload["score"] == 64.0
    by_id = {c["id"]: c for c in payload["components"]}
    assert by_id["sleep"]["missing"] is False
    assert abs(by_id["sleep"]["weight"] - (0.22 / 0.30)) < 1e-3
    assert abs(by_id["stress"]["weight"] - (0.08 / 0.30)) < 1e-3
    assert payload["band"] == "yellow"
    assert "hrv" in [m["id"] for m in payload["missing"]]


def test_get_readiness_insufficient_data_does_not_invent():
    _clear_readiness_tables()
    res = get_readiness(user_id="99")
    assert res["status"] == "success"
    assert res["score"] is None
    assert res["band"] is None
    assert res["confidence"] == 0.0
    assert res["components"] == []
    missing_ids = {m["id"] for m in res["missing"]}
    assert {"sleep", "hrv", "rhr", "body_battery", "stress", "training_load", "residual_fatigue", "journal", "biomarkers"} <= missing_ids
    assert all(m.get("reason") for m in res["missing"])
    journal = next(m for m in res["missing"] if m["id"] == "journal")
    biomarkers = next(m for m in res["missing"] if m["id"] == "biomarkers")
    assert journal["optional"] is True
    assert biomarkers["optional"] is True


def test_get_readiness_sleep_only_renormalizes_and_low_confidence():
    _clear_readiness_tables()
    day = _recent_date(1)
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": day,
        "sleep_score": 82,
        "sleep_hours": 7.6,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()

    res = get_readiness(user_id="1")
    assert res["status"] == "success"
    assert res["score"] == 82.0
    assert res["band"] == "green"
    assert res["confidence"] < 0.4
    ids = [c["id"] for c in res["components"]]
    assert ids == ["sleep"]
    sleep = res["components"][0]
    assert sleep["missing"] is False
    assert sleep["weight"] == 1.0
    assert sleep["raw"]["sleep_score"] == 82
    assert sleep["raw"].get("hrv_ms") is None
    missing_ids = {m["id"] for m in res["missing"]}
    assert "hrv" in missing_ids
    assert "training_load" in missing_ids
    assert "journal" in missing_ids
    # Isolated HRV/RHR would have been invented if we used population norms — they must be missing.
    assert "hrv" in missing_ids
    assert "rhr" in missing_ids


def test_get_readiness_activities_only():
    _clear_readiness_tables()
    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_ready_easy",
        "activity_name": "Easy Aerobic Run",
        "start_time_local": _recent_iso(2),
        "distance": 8000.0,
        "duration": 2400.0,
        "activity_type": "running",
        "average_hr": 138,
    }).execute()
    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_ready_prior",
        "activity_name": "Easy Prior Week",
        "start_time_local": _recent_iso(10),
        "distance": 8000.0,
        "duration": 2400.0,
        "activity_type": "running",
        "average_hr": 140,
    }).execute()

    res = get_readiness(user_id="1")
    assert res["status"] == "success"
    assert res["score"] is not None
    assert 0 <= res["score"] <= 100
    ids = [c["id"] for c in res["components"]]
    assert "residual_fatigue" in ids
    assert "training_load" in ids
    assert "sleep" not in ids
    assert res["confidence"] < 0.5
    missing_ids = {m["id"] for m in res["missing"]}
    assert "sleep" in missing_ids
    assert "journal" in missing_ids
    load = next(c for c in res["components"] if c["id"] == "training_load")
    assert load["raw"]["acute_activity_count"] >= 1
    assert load["raw"]["prior_activity_count"] >= 1
    assert load["missing"] is False


def test_get_readiness_full_signals_applies_biomarker_penalty():
    _clear_readiness_tables()
    # Several days so HRV/RHR baselines exist (do not score a single isolated point).
    for i in range(1, 8):
        supabase.table("biometrics_daily").upsert({
            "user_id": 1,
            "date": _recent_date(i),
            "sleep_score": 80 if i == 1 else 78,
            "sleep_hours": 7.5,
            "hrv": 66 if i == 1 else 64,
            "hrv_ms": 66 if i == 1 else 64,
            "hrv_status": "BALANCED",
            "resting_hr": 50 if i == 1 else 52,
            "stress_level": 28,
            "body_battery": 78,
            "source": "garmin",
        }, on_conflict="user_id, date").execute()

    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_full_easy",
        "activity_name": "Easy Aerobic Run",
        "start_time_local": _recent_iso(2),
        "distance": 8000.0,
        "duration": 2400.0,
        "activity_type": "running",
        "average_hr": 140,
    }).execute()
    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_full_prior",
        "activity_name": "Easy Prior Week",
        "start_time_local": _recent_iso(10),
        "distance": 8500.0,
        "duration": 2500.0,
        "activity_type": "running",
        "average_hr": 142,
    }).execute()

    supabase.table("daily_journals").insert({
        "user_id": 1,
        "date": _recent_date(0),
        "answers": {"energy_level": 8, "felt_sore": False, "journal_text": "Legs ok"},
    }).execute()

    panel = supabase.table("lab_panels").insert({
        "user_id": 1,
        "provider_name": "Quest",
        "test_date": _recent_date(20),
    }).execute().data[0]
    supabase.table("biomarkers").insert({
        "user_id": 1,
        "panel_id": panel["id"],
        "marker_name": "Ferritin",
        "value": 12.0,
        "status": "flagged_low",
    }).execute()
    supabase.table("biomarkers").insert({
        "user_id": 1,
        "panel_id": panel["id"],
        "marker_name": "hs-CRP",
        "value": 3.2,
        "status": "flagged_high",
    }).execute()

    res = get_readiness(user_id="1")
    assert res["status"] == "success"
    assert res["score"] is not None
    assert 0 <= res["score"] <= 100
    assert res["band"] in {"green", "yellow", "red"}
    assert res["confidence"] >= 0.7
    ids = [c["id"] for c in res["components"]]
    for required in (
        "sleep", "hrv", "rhr", "body_battery", "stress",
        "training_load", "residual_fatigue", "journal", "biomarkers",
    ):
        assert required in ids
    assert all(c["missing"] is False for c in res["components"])
    weights = [c["weight"] for c in res["components"] if c["id"] != "biomarkers"]
    assert abs(sum(weights) - 1.0) < 1e-3
    bio = next(c for c in res["components"] if c["id"] == "biomarkers")
    assert bio["contribution"] == -8.0  # two recovery flags × 4
    assert bio["raw"]["flagged_count"] == 2
    assert res["missing"] == []

    # Penalty actually lowers the composite versus the same inputs without flags.
    _clear_readiness_tables()
    for i in range(1, 8):
        supabase.table("biometrics_daily").upsert({
            "user_id": 1,
            "date": _recent_date(i),
            "sleep_score": 80 if i == 1 else 78,
            "sleep_hours": 7.5,
            "hrv": 66 if i == 1 else 64,
            "hrv_ms": 66 if i == 1 else 64,
            "hrv_status": "BALANCED",
            "resting_hr": 50 if i == 1 else 52,
            "stress_level": 28,
            "body_battery": 78,
            "source": "garmin",
        }, on_conflict="user_id, date").execute()
    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_full_easy_b",
        "activity_name": "Easy Aerobic Run",
        "start_time_local": _recent_iso(2),
        "distance": 8000.0,
        "duration": 2400.0,
        "activity_type": "running",
        "average_hr": 140,
    }).execute()
    supabase.table("garmin_activities").insert({
        "user_id": 1,
        "activity_id": "garmin_full_prior_b",
        "activity_name": "Easy Prior Week",
        "start_time_local": _recent_iso(10),
        "distance": 8500.0,
        "duration": 2500.0,
        "activity_type": "running",
        "average_hr": 142,
    }).execute()
    supabase.table("daily_journals").insert({
        "user_id": 1,
        "date": _recent_date(0),
        "answers": {"energy_level": 8, "felt_sore": False},
    }).execute()
    clean_panel = supabase.table("lab_panels").insert({
        "user_id": 1,
        "provider_name": "Quest",
        "test_date": _recent_date(20),
    }).execute().data[0]
    supabase.table("biomarkers").insert({
        "user_id": 1,
        "panel_id": clean_panel["id"],
        "marker_name": "Vitamin D 25-OH",
        "value": 45.0,
        "status": "optimal",
    }).execute()
    clean = get_readiness(user_id="1")
    assert clean["score"] is not None
    assert clean["score"] > res["score"]


def test_get_readiness_stale_sleep_is_not_used():
    _clear_readiness_tables()
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": _recent_date(10),
        "sleep_score": 95,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()
    res = get_readiness(user_id="1")
    assert res["score"] is None
    assert "sleep" in {m["id"] for m in res["missing"]}


def test_hrv_value_without_baseline_or_status_is_omitted():
    _clear_readiness_tables()
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": _recent_date(1),
        "hrv": 64,
        "hrv_ms": 64,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()
    res = get_readiness(user_id="1")
    assert res["score"] is None
    hrv_missing = next(m for m in res["missing"] if m["id"] == "hrv")
    assert "population" in hrv_missing["reason"].lower() or "baseline" in hrv_missing["reason"].lower()


def test_localhost_readiness_route_binds_jwt(client, auth_headers):
    _clear_readiness_tables()
    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": _recent_date(1),
        "sleep_score": 77,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()
    resp = client.get("/telemetry/tools/readiness", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json
    assert body["status"] == "success"
    assert body["score"] == 77.0
    assert body["as_of"]


def test_verify_mcp_tools_includes_readiness():
    from app.garmin.cli import verify_mcp_tools_for_user

    _clear_readiness_tables()
    empty = verify_mcp_tools_for_user("99")
    assert empty["readiness"]["score"] is None
    assert empty["readiness"]["confidence"] == 0.0

    supabase.table("biometrics_daily").upsert({
        "user_id": 1,
        "date": _recent_date(1),
        "sleep_score": 80,
        "source": "garmin",
    }, on_conflict="user_id, date").execute()
    snapshot = verify_mcp_tools_for_user("1")
    assert snapshot["readiness"]["score"] == 80
    assert snapshot["readiness"]["band"] == "green"
