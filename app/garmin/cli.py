"""
Garmin → Supabase sync CLI.

Does not print passwords, emails, tokens, or ENCRYPTION_KEY.

Usage:
  PYTHONPATH=. python -m app.garmin.cli status
  PYTHONPATH=. python -m app.garmin.cli verify-tools
  PYTHONPATH=. python -m app.garmin.cli sync --mode incremental --user-id 2
  PYTHONPATH=. python -m app.garmin.cli remirror-calendar --user-id 2
"""
from __future__ import annotations

import argparse
import os
import sys


def _load_app():
    os.environ["ENABLE_TELEMETRY_SCHEDULER"] = "false"
    # CLI commands should not start the Streamable HTTP MCP runtime.
    os.environ.setdefault("GYMBRO_MCP_HTTP_DISABLE", "true")
    from app import create_app
    return create_app()


def _users_with_garmin(supabase):
    res = supabase.table("users").select(
        "id, garmin_email, garmin_password, garmin_sync_status, garmin_sync_completed_at, "
        "garmin_last_sync_error, garmin_sync_progress, goals"
    ).not_.is_("garmin_email", "null").execute()
    return res.data or []


def cmd_status(_args):
    from app.supabase_client import supabase
    if not supabase:
        print("status: supabase client is not configured (set SUPABASE_URL/SUPABASE_KEY or MOCK_DB=true)")
        return 1
    rows = _users_with_garmin(supabase)
    if not rows:
        print("garmin_connected_users: 0")
        print("No stored Garmin credentials. Reconnect in the app (POST /garmin/connect).")
        return 0
    print(f"garmin_connected_users: {len(rows)}")
    for u in rows:
        goals = u.get("goals") or {}
        last_error = u.get("garmin_last_sync_error")
        print(
            "user_id={id} garmin_connected=true status={status} progress={progress} "
            "last_completed={completed} last_synced_goal={goal} last_error={error}".format(
                id=u.get("id"),
                status=u.get("garmin_sync_status") or "unknown",
                progress=u.get("garmin_sync_progress") if u.get("garmin_sync_progress") is not None else goals.get("sync_progress"),
                completed=u.get("garmin_sync_completed_at") or "never",
                goal=goals.get("garmin_last_synced") or "n/a",
                error=(str(last_error)[:120] if last_error else "none"),
            )
        )
    return 0


def cmd_sync(args):
    from app.supabase_client import supabase
    from app.garmin.sync import sync_all_garmin_data_for_user
    from app.analytics.analytics_service import AnalyticsService

    if not supabase:
        print("sync: supabase client is not configured")
        return 1

    enc_key = os.environ.get("ENCRYPTION_KEY")
    if not enc_key:
        print("sync: ENCRYPTION_KEY is not set; cannot decrypt stored Garmin passwords.")
        print("Set it in the environment (do not commit it).")
        return 1

    rows = _users_with_garmin(supabase)
    from app.garmin.scope import select_users_for_garmin_sync

    rows, err = select_users_for_garmin_sync(
        rows, user_id=args.user_id, all_users=getattr(args, "all_users", False)
    )
    if err:
        print(f"sync: {err}")
        return 1

    if not rows:
        print("sync: no Garmin-connected users. Reconnect in the app.")
        return 1

    mode = args.mode
    days_back = args.days_back if args.days_back is not None else (365 if mode != "incremental" else 7)
    failures = 0
    for u in rows:
        uid = str(u["id"])
        if not u.get("garmin_password"):
            print(f"user_id={uid} skipped: garmin credentials incomplete")
            failures += 1
            continue
        print(f"user_id={uid} starting mode={mode} days_back={days_back} force={args.force}")
        try:
            sync_all_garmin_data_for_user(
                uid,
                days_back=days_back,
                encryption_key=enc_key,
                force_resync=args.force,
                mode=mode,
            )
            try:
                AnalyticsService.calculate_baselines(uid)
            except Exception as analytics_err:
                print(f"user_id={uid} analytics warning: {analytics_err}")
            print(f"user_id={uid} sync finished (check garmin_sync_status via `status`)")
        except Exception as err:
            failures += 1
            print(f"user_id={uid} sync failed: {err}")
    return 1 if failures else 0


def verify_mcp_tools_for_user(user_id: str, wellness_days: int = 7, activity_days: int = 14) -> dict:
    """
    Invoke the same domain tools MCP uses. `user_id` must come from the users table
    or a JWT — never invent one. Does not fabricate telemetry.
    """
    from app.tools.activity_tools import get_recent_activities, get_wellness_metrics
    from app.tools.calendar_tools import get_events

    uid = str(user_id)
    wellness = get_wellness_metrics(uid, days=wellness_days)
    activities = get_recent_activities(uid, days=activity_days)
    calendar = get_events(uid)
    return {
        "user_id": uid,
        "wellness": {
            "status": wellness.get("status"),
            "records_count": wellness.get("records_count", 0),
            "averages": wellness.get("averages"),
        },
        "activities": {
            "status": activities.get("status"),
            "count": activities.get("count", 0),
        },
        "calendar": {
            "status": calendar.get("status"),
            "count": calendar.get("count", 0),
        },
    }


def cmd_verify_tools(args):
    from app.supabase_client import supabase
    if not supabase:
        print("verify-tools: supabase client is not configured")
        return 1

    rows = _users_with_garmin(supabase)
    if args.user_id:
        rows = [u for u in rows if str(u.get("id")) == str(args.user_id)]
        if not rows:
            print(f"verify-tools: no Garmin-connected user with id={args.user_id}")
            return 1

    if not rows:
        print("verify-tools: no Garmin-connected users in the database.")
        print("Reconnect Garmin in the app, or run pytest with MOCK_DB=true (no tunnel).")
        return 0

    wellness_days = args.days_wellness
    activity_days = args.days_activities
    print(f"verify-tools: localhost/in-process (no Cloudflare). wellness_days={wellness_days} activity_days={activity_days}")
    for u in rows:
        snapshot = verify_mcp_tools_for_user(
            u["id"],
            wellness_days=wellness_days,
            activity_days=activity_days,
        )
        avg = snapshot["wellness"].get("averages") or {}
        print(
            "user_id={uid} wellness_status={wstatus} records_count={records} "
            "sleep={sleep} hrv={hrv} rhr={rhr} activities_status={astatus} "
            "activity_count={acount} calendar_count={ccount}".format(
                uid=snapshot["user_id"],
                wstatus=snapshot["wellness"].get("status"),
                records=snapshot["wellness"].get("records_count"),
                sleep=avg.get("sleep_score"),
                hrv=avg.get("hrv_ms"),
                rhr=avg.get("resting_hr_bpm"),
                astatus=snapshot["activities"].get("status"),
                acount=snapshot["activities"].get("count"),
                ccount=(snapshot.get("calendar") or {}).get("count", 0),
            )
        )
    return 0


def cmd_remirror_calendar(args):
    """Mirror garmin_activities → training_events without calling Garmin."""
    from app.supabase_client import supabase
    from app.garmin.sync import remirror_garmin_calendar

    if not supabase:
        print("remirror-calendar: supabase client is not configured")
        return 1

    user_ids = []
    if args.user_id:
        user_ids = [str(args.user_id)]
    else:
        rows = _users_with_garmin(supabase)
        user_ids = [str(u["id"]) for u in rows]
        if not user_ids:
            print("remirror-calendar: no Garmin-connected users.")
            return 1

    failures = 0
    for uid in user_ids:
        result = remirror_garmin_calendar(uid)
        err = result.get("error")
        print(
            "user_id={uid} garmin_activities={source} mirrored={inserted} skipped={skipped}{err}".format(
                uid=result.get("user_id", uid),
                source=result.get("source", 0),
                inserted=result.get("inserted", 0),
                skipped=result.get("skipped", 0),
                err=f" error={err}" if err else "",
            )
        )
        if err:
            failures += 1
        elif result.get("source", 0) == 0:
            print(f"user_id={uid} no garmin_activities rows to remirror")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Garmin → Supabase sync (no secrets printed).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show Garmin connection/sync state without credentials")

    sync_p = sub.add_parser("sync", help="Run Garmin sync for connected users")
    sync_p.add_argument("--mode", choices=["incremental", "deep_365", "all_time"], default="incremental")
    sync_p.add_argument("--days-back", type=int, default=None)
    sync_p.add_argument("--user-id", default=None, help="Limit to one athlete id (from the users table)")
    sync_p.add_argument(
        "--all-users",
        action="store_true",
        help="Sync every Garmin-connected user (default is --user-id or GYMBRO_GARMIN_SYNC_USER_IDS)",
    )
    sync_p.add_argument("--force", action="store_true", help="Force resync (skip delta-date skipping)")

    verify_p = sub.add_parser(
        "verify-tools",
        help="Call get_wellness_metrics / get_recent_activities in-process (no Cloudflare tunnel)",
    )
    verify_p.add_argument("--user-id", default=None, help="Limit to one athlete id from the users table")
    verify_p.add_argument("--days-wellness", type=int, default=7)
    verify_p.add_argument("--days-activities", type=int, default=14)

    remirror_p = sub.add_parser(
        "remirror-calendar",
        help="Write training_events from existing garmin_activities (no Garmin API)",
    )
    remirror_p.add_argument("--user-id", default=None, help="Athlete id (from the users table)")

    args = parser.parse_args(argv)
    app = _load_app()
    with app.app_context():
        if args.command == "status":
            return cmd_status(args)
        if args.command == "sync":
            return cmd_sync(args)
        if args.command == "verify-tools":
            return cmd_verify_tools(args)
        if args.command == "remirror-calendar":
            return cmd_remirror_calendar(args)
        parser.error(f"unknown command {args.command}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
