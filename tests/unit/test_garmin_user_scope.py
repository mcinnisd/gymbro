from app.garmin.scope import (
    collapse_duplicate_garmin_emails,
    select_users_for_garmin_sync,
)
from app.garmin.sync import upsert_garmin_activities
from app.supabase_client import supabase


def test_select_users_for_garmin_sync_requires_user_id_when_multiple():
    rows = [{"id": 2, "garmin_email": "a@example.com"}, {"id": 100, "garmin_email": "b@example.com"}]
    selected, err = select_users_for_garmin_sync(rows)
    assert selected == []
    assert err and "--user-id" in err
    assert "@" not in err

    selected, err = select_users_for_garmin_sync(rows, user_id="2")
    assert err is None
    assert [u["id"] for u in selected] == [2]

    selected, err = select_users_for_garmin_sync(rows, all_users=True)
    assert err is None
    assert len(selected) == 2


def test_collapse_duplicate_garmin_emails_keeps_lowest_id():
    rows = [
        {"id": 100, "garmin_email": "Shared@example.com"},
        {"id": 2, "garmin_email": " shared@example.com "},
        {"id": 50, "garmin_email": "other@example.com"},
    ]
    kept, skipped = collapse_duplicate_garmin_emails(rows)
    kept_ids = {u["id"] for u in kept}
    assert 2 in kept_ids
    assert 50 in kept_ids
    assert 100 not in kept_ids
    assert skipped == ["100"]


def test_select_users_refuses_duplicate_email_user_id():
    rows = [
        {"id": 2, "garmin_email": "shared@example.com"},
        {"id": 100, "garmin_email": "shared@example.com"},
    ]
    selected, err = select_users_for_garmin_sync(rows, user_id="100")
    assert selected == []
    assert err and "user_id=100" in err and "user_id=2" in err
    assert "@" not in err
    assert "shared" not in err.lower()

    selected, err = select_users_for_garmin_sync(rows, user_id="2")
    assert err is None
    assert [u["id"] for u in selected] == [2]


def test_select_users_collapses_duplicate_email_without_user_id():
    rows = [
        {"id": 2, "garmin_email": "shared@example.com"},
        {"id": 100, "garmin_email": "shared@example.com"},
    ]
    selected, err = select_users_for_garmin_sync(rows)
    assert err is None
    assert [u["id"] for u in selected] == [2]

    selected, err = select_users_for_garmin_sync(rows, all_users=True)
    assert err is None
    assert [u["id"] for u in selected] == [2]


def test_select_users_allowlist_wins_duplicate_email(monkeypatch):
    monkeypatch.setenv("GYMBRO_GARMIN_SYNC_USER_IDS", "100")
    rows = [
        {"id": 2, "garmin_email": "shared@example.com"},
        {"id": 100, "garmin_email": "shared@example.com"},
    ]
    selected, err = select_users_for_garmin_sync(rows, user_id="100")
    assert err is None
    assert [u["id"] for u in selected] == [100]


def test_select_users_for_garmin_sync_honors_allowlist(monkeypatch):
    monkeypatch.setenv("GYMBRO_GARMIN_SYNC_USER_IDS", "2")
    rows = [{"id": 2}, {"id": 100}]
    selected, err = select_users_for_garmin_sync(rows)
    assert err is None
    assert [u["id"] for u in selected] == [2]


def test_upsert_garmin_activities_does_not_steal_another_users_row():
    supabase.table("garmin_activities").data["garmin_activities"] = []
    upsert_garmin_activities("2", [{
        "activity_id": "santa_monica_1",
        "activity_name": "Santa Monica Running",
        "start_time_local": "2026-09-15T06:12:00",
        "activity_type": "running",
    }])
    upsert_garmin_activities("100", [{
        "activity_id": "santa_monica_1",
        "activity_name": "Santa Monica Running",
        "start_time_local": "2026-09-15T06:12:00",
        "activity_type": "running",
    }])
    rows = supabase.table("garmin_activities").select("*").execute().data
    owners = {(str(r["user_id"]), r["activity_id"]) for r in rows}
    assert ("2", "santa_monica_1") in owners
    assert ("100", "santa_monica_1") in owners
    user2 = [r for r in rows if str(r["user_id"]) == "2"]
    assert len(user2) == 1


def test_user_scoped_unique_migration_sql():
    from pathlib import Path
    sql = Path("migrations/20260916_garmin_activities_user_scoped.sql").read_text()
    assert "DROP CONSTRAINT IF EXISTS garmin_activities_activity_id_key" in sql
    assert "UNIQUE INDEX" in sql.upper() or "user_id, activity_id" in sql
