"""Wake status from stored garmin_sleep / garmin_daily. No Garmin API."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.garmin.cli import main as garmin_cli_main
from app.garmin.wake import assess_sleep_payload
from app.mcp.executor import execute_tool
from app.mcp.policies import requires_confirm
from app.mcp.server import build_mcp_tools
from app.supabase_client import supabase
from app.tools.registry import get_tool_implementation
from app.tools.wake_tools import get_wake_status

UID = 9101
DAY = "2026-11-23"
LA = "America/Los_Angeles"
ZONE = ZoneInfo(LA)


def _wipe():
    for table, column in (
        ("garmin_sleep", "user_id"),
        ("garmin_daily", "user_id"),
        ("biometrics_daily", "user_id"),
        ("users", "id"),
    ):
        supabase.table(table).delete().eq(column, UID).execute()


@pytest.fixture(autouse=True)
def _clean_rows():
    _wipe()
    yield
    _wipe()


def _ms(instant: datetime) -> int:
    return int(instant.timestamp() * 1000)


def _local(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp).replace(tzinfo=ZONE)


def _gmt_stamp(stamp: str) -> str:
    return _local(stamp).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0")


def _hr(start: str, end: str, bpm, step_min: int = 2):
    cursor = _local(start)
    stop = _local(end)
    values = []
    while cursor <= stop:
        values.append([_ms(cursor), bpm])
        cursor += timedelta(minutes=step_min)
    return values


def _steps(ranges):
    buckets = []
    for start, end, steps in ranges:
        buckets.append({
            "startGMT": _gmt_stamp(start),
            "endGMT": _gmt_stamp(end),
            "steps": steps,
            "primaryActivityLevel": "active" if steps else "sedentary",
        })
    return buckets


def _sleep(payload, day=DAY, synced_at="2026-11-23T16:00:00+00:00"):
    supabase.table("garmin_sleep").insert({
        "user_id": UID,
        "date": day,
        "sleep_data": payload,
        "synced_at": synced_at,
    }).execute()


def _daily(hr_values, steps, resting=48, synced_at="2026-11-23T16:30:00+00:00"):
    supabase.table("garmin_daily").insert({
        "user_id": UID,
        "date": DAY,
        "steps": steps,
        "heartrate": {"restingHeartRate": resting, "heartRateValues": hr_values},
        "resting_hr": resting,
        "synced_at": synced_at,
    }).execute()


def _payload(start, end, *, confirmation="enhanced_confirmed_final", confirmed=True,
             with_id=True, levels=True, offset_hours=None):
    dto = {
        "id": 987654321 if with_id else None,
        "calendarDate": DAY,
        "sleepWindowConfirmed": confirmed,
        "sleepWindowConfirmationType": confirmation,
        "sleepStartTimestampGMT": _ms(start),
        "sleepEndTimestampGMT": _ms(end),
    }
    if offset_hours is not None:
        shift = int(offset_hours * 3600 * 1000)
        dto["sleepStartTimestampLocal"] = _ms(start) + shift
        dto["sleepEndTimestampLocal"] = _ms(end) + shift
    return {
        "dailySleepDTO": dto,
        "sleepLevels": [
            {"startGMT": "2026-11-23T06:30:00.0", "endGMT": "2026-11-23T07:00:00.0", "activityLevel": 1.0}
        ] if levels else [],
    }


def _shell():
    return {
        "dailySleepDTO": {
            "id": None,
            "calendarDate": DAY,
            "sleepTimeSeconds": None,
            "sleepWindowConfirmed": False,
            "sleepWindowConfirmationType": "unconfirmed",
            "sleepStartTimestampGMT": None,
            "sleepEndTimestampGMT": None,
        },
        "sleepLevels": [],
    }


def _status(**kwargs):
    kwargs.setdefault("timezone", LA)
    return get_wake_status(str(UID), as_of=kwargs.pop("as_of", DAY), **kwargs)


def _final_instants():
    start = datetime(2026, 11, 23, 6, 30, tzinfo=timezone.utc)  # 22:30 PST
    end = datetime(2026, 11, 23, 14, 30, tzinfo=timezone.utc)  # 06:30 PST
    return start, end


def test_assess_finalized_requires_id_levels_confirmed_and_final_type():
    start, end = _final_instants()
    assert assess_sleep_payload(_payload(start, end)).finalized is True
    assert assess_sleep_payload(_shell()).empty_shell is True
    assert assess_sleep_payload(_shell()).finalized is False
    almost = _payload(start, end, confirmation="enhanced_confirmed")
    assessed = assess_sleep_payload(almost)
    assert assessed.finalized is False
    assert assessed.empty_shell is False
    assert assess_sleep_payload(_payload(start, end, levels=False)).finalized is False
    assert assess_sleep_payload(_payload(start, end, confirmed=False)).finalized is False
    assert assess_sleep_payload(_payload(start, end, with_id=False, levels=False)).empty_shell is False


def test_finalized_session_wake_time_uses_athlete_zone():
    start, end = _final_instants()
    _sleep(_payload(start, end), synced_at="2026-11-23T15:10:00+00:00")
    result = _status()
    assert result["status"] == "success"
    assert result["finalized"] is True
    assert result["awake"] is True
    assert result["state"] == "up"
    assert result["signal"] == "sleep_finalized"
    assert result["confidence"] == "high"
    assert result["wake_time"] == "2026-11-23T06:30:00-08:00"
    assert result["sleep_start"] == "2026-11-22T22:30:00-08:00"
    assert result["confirmation_type"] == "enhanced_confirmed_final"
    assert result["reason"] == "sleep session finalized"
    assert result["latest_data_at"] == "2026-11-23T15:10:00+00:00"


def test_payload_local_offset_beats_the_athlete_zone():
    start, end = _final_instants()
    _sleep(_payload(start, end, offset_hours=-7))
    result = _status()
    assert result["signal"] == "sleep_finalized"
    assert result["wake_time"] == "2026-11-23T07:30:00-07:00"
    assert result["sleep_start"] == "2026-11-22T23:30:00-07:00"


def test_finalized_sleep_wins_over_later_activity_and_off_wrist():
    start, end = _final_instants()
    _sleep(_payload(start, end))
    hr = _hr("2026-11-23T00:00:00", "2026-11-23T06:30:00", 46)
    hr += _hr("2026-11-23T06:32:00", "2026-11-23T08:00:00", None)
    _daily(
        hr,
        _steps([
            ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 150),
            ("2026-11-23T06:15:00", "2026-11-23T06:30:00", 150),
            ("2026-11-23T06:30:00", "2026-11-23T06:45:00", 150),
        ]),
    )
    result = _status()
    assert result["signal"] == "sleep_finalized"
    assert result["wake_time"] == "2026-11-23T06:30:00-08:00"
    assert result["finalized"] is True


def test_empty_shell_does_not_reuse_yesterdays_finalized_session():
    start, end = _final_instants()
    yesterday_end = end - timedelta(days=1)
    _sleep(
        _payload(start - timedelta(days=1), yesterday_end),
        day="2026-11-22",
        synced_at="2026-11-22T16:00:00+00:00",
    )
    _sleep(_shell(), synced_at="2026-11-23T14:05:00+00:00")
    result = _status()
    assert result["finalized"] is False
    assert result["awake"] is None
    assert result["state"] == "unknown"
    assert result["signal"] is None
    assert result["wake_time"] is None
    assert "unknown / not synced yet" in result["reason"]
    assert "empty shell (not uploaded yet)" in result["reason"]
    assert result["latest_data_at"] == "2026-11-23T14:05:00+00:00"
    assert "06:30" not in (result["wake_time"] or "")


def test_missing_row_is_unknown_and_reports_latest_stored_timestamp():
    start, end = _final_instants()
    _sleep(
        _payload(start - timedelta(days=1), end - timedelta(days=1)),
        day="2026-11-22",
        synced_at="2026-11-22T16:00:00+00:00",
    )
    result = _status()
    assert result["finalized"] is False
    assert result["state"] == "unknown"
    assert result["awake"] is None
    assert result["wake_time"] is None
    assert result["reason"] == "unknown / not synced yet: no row"
    assert result["latest_data_at"] == "2026-11-22T16:00:00+00:00"


def test_unconfirmed_session_with_morning_rest_is_not_yet():
    start, end = _final_instants()
    _sleep(_payload(start, end, confirmation="unconfirmed", confirmed=False))
    _daily(_hr("2026-11-23T05:00:00", "2026-11-23T07:00:00", 47), _steps([]))
    result = _status()
    assert result["finalized"] is False
    assert result["awake"] is False
    assert result["state"] == "not_yet"
    assert result["signal"] is None
    assert result["wake_time"] is None
    assert result["reason"] == "present but not yet confirmed/final"
    assert result["confirmation_type"] == "unconfirmed"


def test_activity_signal_after_sustained_morning_movement():
    _sleep(_shell())
    _daily(
        _hr("2026-11-23T06:00:00", "2026-11-23T06:50:00", 75),
        _steps([
            ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 100),
            ("2026-11-23T06:15:00", "2026-11-23T06:30:00", 100),
            ("2026-11-23T06:30:00", "2026-11-23T06:45:00", 100),
            ("2026-11-23T06:45:00", "2026-11-23T07:00:00", 100),
        ]),
    )
    result = _status()
    assert result["finalized"] is False
    assert result["awake"] is True
    assert result["state"] == "up"
    assert result["signal"] == "activity"
    assert result["confidence"] == "medium"
    assert result["wake_time"] == "2026-11-23T06:00:00-08:00"
    assert result["reason"] == "sustained morning steps and heart rate above resting"


def test_early_dog_walk_does_not_count_as_awake():
    _sleep(_shell())
    hr = _hr("2026-11-23T03:20:00", "2026-11-23T03:40:00", 90)
    hr += _hr("2026-11-23T03:42:00", "2026-11-23T07:00:00", 46)
    _daily(
        hr,
        _steps([
            ("2026-11-23T03:15:00", "2026-11-23T03:30:00", 220),
            ("2026-11-23T03:30:00", "2026-11-23T03:45:00", 180),
            ("2026-11-23T05:00:00", "2026-11-23T07:00:00", 0),
        ]),
    )
    result = _status()
    assert result["signal"] is None
    assert result["awake"] is False
    assert result["state"] == "not_yet"
    assert result["wake_time"] is None


def test_activity_that_settles_back_to_sleep_is_not_up():
    start, end = _final_instants()
    _sleep(_payload(start, end, confirmation="unconfirmed", confirmed=False))
    hr = _hr("2026-11-23T06:00:00", "2026-11-23T06:28:00", 80)
    hr += _hr("2026-11-23T06:30:00", "2026-11-23T07:00:00", 47)
    _daily(
        hr,
        _steps([
            ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 120),
            ("2026-11-23T06:15:00", "2026-11-23T06:30:00", 120),
            ("2026-11-23T06:30:00", "2026-11-23T07:00:00", 0),
        ]),
    )
    result = _status()
    assert result["signal"] is None
    assert result["state"] == "not_yet"
    assert result["reason"] == "present but not yet confirmed/final"


def test_off_wrist_null_run_after_overnight_wear():
    _sleep(_shell())
    hr = _hr("2026-11-23T04:00:00", "2026-11-23T06:08:00", 45)
    hr += _hr("2026-11-23T06:10:00", "2026-11-23T06:40:00", None)
    _daily(hr, _steps([]))
    result = _status()
    assert result["finalized"] is False
    assert result["awake"] is True
    assert result["signal"] == "off_wrist"
    assert result["confidence"] == "medium"
    assert result["wake_time"] == "2026-11-23T06:10:00-08:00"
    assert result["reason"] == "sustained morning off-wrist after overnight wear"


def test_heart_rate_series_that_ends_is_not_off_wrist():
    _sleep(_shell(), synced_at="2026-11-23T12:00:00+00:00")
    _daily(_hr("2026-11-23T00:00:00", "2026-11-23T04:00:00", 45), _steps([]))
    result = _status()
    assert result["signal"] is None
    assert result["state"] == "unknown"
    assert result["awake"] is None
    assert "unknown / not synced yet" in result["reason"]
    assert "empty shell" in result["reason"]
    assert result["wake_time"] is None


def test_off_wrist_confirmation_after_early_hour():
    start = datetime(2026, 11, 23, 6, 30, tzinfo=timezone.utc)
    end = _local("2026-11-23T06:40:00")
    _sleep(_payload(start, end, confirmation="off_wrist", confirmed=True))
    result = _status()
    assert result["finalized"] is False
    assert result["signal"] == "off_wrist"
    assert result["wake_time"] == "2026-11-23T06:40:00-08:00"
    assert result["reason"] == "sleep window closed off-wrist"
    assert result["confirmation_type"] == "off_wrist"


def test_off_wrist_confirmation_before_5am_is_not_up():
    start = datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc)
    end = _local("2026-11-23T03:30:00")
    _sleep(_payload(start, end, confirmation="off_wrist", confirmed=True))
    result = _status()
    assert result["signal"] is None
    assert result["state"] == "unknown"
    assert result["wake_time"] is None
    assert "unknown / not synced yet" in result["reason"]


def test_off_wrist_confirmation_cancelled_when_watch_goes_back_on():
    end = _local("2026-11-23T06:10:00")
    start = end - timedelta(hours=8)
    _sleep(_payload(start, end, confirmation="off_wrist", confirmed=True))
    _daily(_hr("2026-11-23T06:12:00", "2026-11-23T07:00:00", 46), _steps([]), resting=48)
    result = _status()
    assert result["signal"] is None
    assert result["state"] == "not_yet"
    assert result["reason"] == "present but not yet confirmed/final"


def test_goals_timezone_used_when_argument_omitted():
    supabase.table("users").insert({
        "id": UID,
        "username": "wake-athlete",
        "password": "stored",
        "goals": {"timezone": "America/New_York"},
    }).execute()
    start = datetime(2026, 11, 23, 3, 30, tzinfo=timezone.utc)  # 22:30 EST
    end = datetime(2026, 11, 23, 11, 30, tzinfo=timezone.utc)  # 06:30 EST
    _sleep(_payload(start, end))
    result = get_wake_status(str(UID), as_of=DAY)
    assert result["timezone"] == "America/New_York"
    assert result["wake_time"] == "2026-11-23T06:30:00-05:00"
    assert result["sleep_start"] == "2026-11-22T22:30:00-05:00"


def test_early_hour_env_ignores_a_6am_activity(monkeypatch):
    monkeypatch.setenv("GYMBRO_WAKE_EARLY_HOUR", "7")
    _sleep(_shell())
    _daily(
        _hr("2026-11-23T06:00:00", "2026-11-23T06:50:00", 80),
        _steps([
            ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 140),
            ("2026-11-23T06:15:00", "2026-11-23T06:30:00", 140),
            ("2026-11-23T06:30:00", "2026-11-23T06:45:00", 140),
        ]),
    )
    result = _status()
    assert result["signal"] is None
    assert result["state"] != "up"


def test_invalid_as_of_is_an_error():
    result = get_wake_status(str(UID), as_of="tomorrow", timezone=LA)
    assert result["status"] == "error"
    assert result["state"] == "unknown"
    assert result["finalized"] is False


def test_registry_and_mcp_expose_read_only_wake_tool():
    assert get_tool_implementation("get_wake_status") is get_wake_status
    assert requires_confirm("get_wake_status") is False
    tool = next(item for item in build_mcp_tools() if item.name == "get_wake_status")
    assert "user_id" not in (tool.inputSchema.get("properties") or {})
    assert "as_of" in tool.inputSchema["properties"]
    assert tool.annotations.readOnlyHint is True


def test_mcp_execute_binds_athlete_and_matches_cli_json(monkeypatch, capsys):
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "k")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", str(UID))
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)
    start, end = _final_instants()
    _sleep(_payload(start, end))

    bound = execute_tool(
        "get_wake_status",
        {"user_id": "attacker", "as_of": DAY, "timezone": LA},
    )
    assert bound.success is True
    assert bound.data["user_id"] == str(UID)
    assert bound.data["signal"] == "sleep_finalized"
    assert bound.data["wake_time"] == "2026-11-23T06:30:00-08:00"

    code = garmin_cli_main([
        "wake-status", "--user-id", str(UID), "--as-of", DAY,
        "--timezone", LA, "--json",
    ])
    printed = capsys.readouterr().out
    assert code == 0
    import json
    payload = json.loads(printed)
    assert payload["wake_time"] == bound.data["wake_time"]
    assert payload["signal"] == "sleep_finalized"
    assert payload["finalized"] is True

    text_code = garmin_cli_main([
        "wake-status", "--user-id", str(UID), "--as-of", DAY, "--timezone", LA,
    ])
    text = capsys.readouterr().out
    assert text_code == 0
    assert "finalized=true" in text
    assert "signal=sleep_finalized" in text
    assert "wake_time=2026-11-23T06:30:00-08:00" in text
