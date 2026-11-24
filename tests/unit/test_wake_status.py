"""Wake status and the today-only poll. No live Garmin login."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.garmin.cli import main as garmin_cli_main
from app.garmin.sync import pull_today_for_wake
from app.garmin.wake import get_wake_status
from app.mcp.policies import requires_confirm
from app.supabase_client import supabase
from app.tools.registry import get_tool_implementation
from app.tools.wake_tools import get_wake_status as tool_get_wake_status

UID = 9101
DAY = "2026-11-23"
LA = "America/Los_Angeles"
ZONE = ZoneInfo(LA)

def _wipe():
    for table, column in (
        ("garmin_sleep", "user_id"),
        ("garmin_daily", "user_id"),
        ("users", "id"),
    ):
        supabase.table(table).delete().eq(column, UID).execute()

def setup_function():
    _wipe()

def teardown_function():
    _wipe()

def _ms(instant):
    return int(instant.timestamp() * 1000)

def _local(stamp):
    return datetime.fromisoformat(stamp).replace(tzinfo=ZONE)

def _gmt(stamp):
    return _local(stamp).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0")

def _hr(start, end, bpm, step=2):
    cursor, stop = _local(start), _local(end)
    values = []
    while cursor <= stop:
        values.append([_ms(cursor), bpm])
        cursor += timedelta(minutes=step)
    return values

def _buckets(ranges):
    return [
        {"startGMT": _gmt(a), "endGMT": _gmt(b), "steps": steps}
        for a, b, steps in ranges
    ]

def _sleep(payload, day=DAY, synced_at="2026-11-23T16:00:00+00:00"):
    supabase.table("garmin_sleep").insert({
        "user_id": UID, "date": day, "sleep_data": payload, "synced_at": synced_at,
    }).execute()

def _daily(hr, steps, resting=48):
    supabase.table("garmin_daily").insert({
        "user_id": UID, "date": DAY, "steps": steps, "resting_hr": resting,
        "heartrate": {"restingHeartRate": resting, "heartRateValues": hr},
        "synced_at": "2026-11-23T16:30:00+00:00",
    }).execute()

def _session(start, end, confirmation="enhanced_confirmed_final", confirmed=True, levels=True, with_id=True):
    return {
        "dailySleepDTO": {
            "id": 987654321 if with_id else None,
            "calendarDate": DAY,
            "sleepWindowConfirmed": confirmed,
            "sleepWindowConfirmationType": confirmation,
            "sleepStartTimestampGMT": _ms(start),
            "sleepEndTimestampGMT": _ms(end),
        },
        "sleepLevels": [{"startGMT": "x", "endGMT": "y"}] if levels else [],
    }

def _status():
    return get_wake_status(str(UID), as_of=DAY, timezone=LA)

def _night():
    return (
        datetime(2026, 11, 23, 6, 30, tzinfo=timezone.utc),
        datetime(2026, 11, 23, 14, 30, tzinfo=timezone.utc),
    )

def test_sleep_finalized_is_up_immediately():
    start, end = _night()
    _sleep(_session(start, end))
    hr = _hr("2026-11-23T00:00:00", "2026-11-23T06:30:00", 46)
    hr += _hr("2026-11-23T06:32:00", "2026-11-23T08:00:00", None)
    _daily(hr, _buckets([
        ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 150),
        ("2026-11-23T06:15:00", "2026-11-23T06:45:00", 150),
    ]))
    result = _status()
    assert result["signal"] == "sleep_finalized"
    assert result["state"] == "up"
    assert result["finalized"] is True
    assert result["wake_time"] == "2026-11-23T06:30:00-08:00"
    assert result["sleep_start"] == "2026-11-22T22:30:00-08:00"

def test_off_wrist_after_5am_is_up_without_waiting():
    end = _local("2026-11-23T06:40:00")
    _sleep(_session(end - timedelta(hours=8), end, confirmation="off_wrist"))
    _daily(_hr("2026-11-23T06:42:00", "2026-11-23T07:10:00", 46), [])
    result = _status()
    assert result["finalized"] is False
    assert result["signal"] == "off_wrist"
    assert result["state"] == "up"
    assert result["wake_time"] == "2026-11-23T06:40:00-08:00"

def test_off_wrist_null_run_and_a_series_that_ends_is_lag():
    _sleep({
        "dailySleepDTO": {"id": None, "sleepWindowConfirmed": False, "sleepWindowConfirmationType": "unconfirmed"},
        "sleepLevels": [],
    })
    worn = _hr("2026-11-23T04:00:00", "2026-11-23T06:08:00", 45)
    _daily(worn + _hr("2026-11-23T06:10:00", "2026-11-23T06:40:00", None), [])
    assert _status()["signal"] == "off_wrist"

    _wipe()
    _sleep({
        "dailySleepDTO": {"id": None, "sleepWindowConfirmed": False},
        "sleepLevels": [],
    }, synced_at="2026-11-23T12:00:00+00:00")
    _daily(_hr("2026-11-23T00:00:00", "2026-11-23T04:00:00", 45), [])
    ended = _status()
    assert ended["signal"] is None
    assert ended["state"] == "unknown"
    assert "unknown / not synced yet" in ended["reason"]

def test_pre_5am_spike_is_ignored_and_activity_is_the_fallback():
    shell = {
        "dailySleepDTO": {"id": None, "sleepStartTimestampGMT": None, "sleepEndTimestampGMT": None},
        "sleepLevels": [],
    }
    _sleep(shell)
    early = _hr("2026-11-23T03:20:00", "2026-11-23T03:40:00", 90)
    early += _hr("2026-11-23T03:42:00", "2026-11-23T07:00:00", 46)
    _daily(early, _buckets([
        ("2026-11-23T03:15:00", "2026-11-23T03:45:00", 400),
        ("2026-11-23T05:00:00", "2026-11-23T07:00:00", 0),
    ]))
    ignored = _status()
    assert ignored["signal"] is None
    assert ignored["state"] != "up"

    _wipe()
    _sleep(shell)
    _daily(
        _hr("2026-11-23T06:00:00", "2026-11-23T06:50:00", 75),
        _buckets([
            ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 100),
            ("2026-11-23T06:15:00", "2026-11-23T06:30:00", 100),
            ("2026-11-23T06:30:00", "2026-11-23T06:45:00", 100),
            ("2026-11-23T06:45:00", "2026-11-23T07:00:00", 100),
        ]),
    )
    moved = _status()
    assert moved["signal"] == "activity"
    assert moved["wake_time"] == "2026-11-23T06:00:00-08:00"
    assert moved["finalized"] is False

def test_missing_row_and_empty_shell_do_not_use_yesterday():
    start, end = _night()
    _sleep(_session(start - timedelta(days=1), end - timedelta(days=1)), day="2026-11-22",
           synced_at="2026-11-22T16:00:00+00:00")
    missing = _status()
    assert missing["state"] == "unknown"
    assert missing["wake_time"] is None
    assert missing["reason"] == "unknown / not synced yet: no row"
    assert missing["latest_data_at"] == "2026-11-22T16:00:00+00:00"

    _sleep({
        "dailySleepDTO": {"id": None, "sleepStartTimestampGMT": None, "sleepEndTimestampGMT": None},
        "sleepLevels": [],
    }, synced_at="2026-11-23T14:05:00+00:00")
    shell = _status()
    assert shell["state"] == "unknown"
    assert shell["wake_time"] is None
    assert "empty shell" in shell["reason"]
    assert shell["latest_data_at"] == "2026-11-23T14:05:00+00:00"

def test_off_wrist_before_5am_is_not_up():
    end = _local("2026-11-23T03:30:00")
    _sleep(_session(end - timedelta(hours=6), end, confirmation="off_wrist"))
    result = _status()
    assert result["signal"] is None
    assert result["state"] == "unknown"
    assert result["wake_time"] is None

def test_registry_wires_the_read_tool():
    from app.mcp.auth import MCPAuthContext
    from app.mcp.executor import execute_tool
    from app.mcp.server import build_mcp_tools

    assert get_tool_implementation("get_wake_status") is tool_get_wake_status
    assert requires_confirm("get_wake_status") is False
    names = {tool.name for tool in build_mcp_tools()}
    assert "get_wake_status" in names
    start, end = _night()
    _sleep(_session(start, end))
    result = execute_tool(
        "get_wake_status",
        {"as_of": DAY, "timezone": LA, "user_id": "999999"},
        auth=MCPAuthContext(user_id=str(UID), auth_method="api_key"),
    )
    assert result.success is True and result.data["signal"] == "sleep_finalized"
    assert result.data["user_id"] == str(UID)

def test_wake_poll_skips_garmin_once_up(monkeypatch, capsys):
    start, end = _night()
    _sleep(_session(start, end))
    monkeypatch.setattr("app.garmin.sync.pull_today_for_wake", MagicMock(side_effect=AssertionError("garmin")))
    code = garmin_cli_main(["wake-poll", "--user-id", str(UID), "--as-of", DAY, "--timezone", LA, "--json"])
    assert code == 0
    import json
    payload = json.loads(capsys.readouterr().out)
    assert payload["garmin_called"] is False
    assert payload["signal"] == "sleep_finalized"

def test_wake_poll_uses_marker_without_calling_garmin(monkeypatch, capsys):
    supabase.table("users").insert({
        "id": UID, "username": "wake", "password": "x",
        "goals": {"wake_detected_on": DAY},
    }).execute()
    called = MagicMock(side_effect=AssertionError("garmin"))
    monkeypatch.setattr("app.garmin.sync.pull_today_for_wake", called)
    code = garmin_cli_main(["wake-poll", "--user-id", str(UID), "--as-of", DAY, "--timezone", LA, "--json"])
    assert code == 0
    import json
    payload = json.loads(capsys.readouterr().out)
    assert payload["garmin_called"] is False
    assert payload["state"] == "up"
    assert payload["reason"] == "wake already detected today"
    called.assert_not_called()

def test_pull_today_writes_only_sleep_steps_and_hr(monkeypatch):
    api = MagicMock()
    start, end = _night()
    api.get_sleep_data.return_value = _session(start, end)
    api.get_steps_data.return_value = _buckets([("2026-11-23T06:00:00", "2026-11-23T06:15:00", 10)])
    api.get_heart_rates.return_value = {"restingHeartRate": 48, "heartRateValues": []}
    monkeypatch.setattr("app.garmin.sync.init_garmin_api_for_user", lambda *args, **kwargs: api)
    result = pull_today_for_wake(str(UID), DAY, "test-key-not-a-secret")
    assert result["ok"] is True
    api.get_sleep_data.assert_called_once_with(DAY)
    api.get_steps_data.assert_called_once_with(DAY)
    api.get_heart_rates.assert_called_once_with(DAY)
    api.get_activities.assert_not_called()
    sleep = supabase.table("garmin_sleep").select("*").eq("user_id", UID).eq("date", DAY).execute().data
    daily = supabase.table("garmin_daily").select("*").eq("user_id", UID).eq("date", DAY).execute().data
    assert sleep and sleep[0]["sleep_data"]["dailySleepDTO"]["id"] == 987654321
    assert daily and daily[0]["resting_hr"] == 48
    assert get_wake_status(str(UID), as_of=DAY, timezone=LA)["signal"] == "sleep_finalized"

def test_failed_wake_pull_does_not_replace_stored_rows(monkeypatch):
    start, end = _night()
    _sleep(_session(start, end))
    _daily(_hr("2026-11-23T06:00:00", "2026-11-23T06:20:00", 70), _buckets([
        ("2026-11-23T06:00:00", "2026-11-23T06:15:00", 40),
    ]))
    api = MagicMock()
    api.get_sleep_data.return_value = None
    api.get_steps_data.return_value = None
    api.get_heart_rates.return_value = None
    monkeypatch.setattr("app.garmin.sync.init_garmin_api_for_user", lambda *args, **kwargs: api)
    result = pull_today_for_wake(str(UID), DAY, "test-key-not-a-secret")
    assert result["ok"] is False
    sleep = supabase.table("garmin_sleep").select("sleep_data").eq("user_id", UID).eq("date", DAY).execute().data
    daily = supabase.table("garmin_daily").select("steps,resting_hr").eq("user_id", UID).eq("date", DAY).execute().data
    assert sleep[0]["sleep_data"]["dailySleepDTO"]["id"] == 987654321
    assert daily[0]["resting_hr"] == 48
    assert get_wake_status(str(UID), as_of=DAY, timezone=LA)["signal"] == "sleep_finalized"
