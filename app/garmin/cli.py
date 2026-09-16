"""
Garmin → Supabase sync CLI.

Does not print passwords, emails, tokens, or ENCRYPTION_KEY.

Usage:
  PYTHONPATH=. python -m app.garmin.cli status
  PYTHONPATH=. python -m app.garmin.cli sync --mode incremental
  PYTHONPATH=. python -m app.garmin.cli sync --mode incremental --user-id 1
  PYTHONPATH=. python -m app.garmin.cli sync --mode all_time --force
"""
from __future__ import annotations

import argparse
import os
import sys


def _load_app():
    os.environ["ENABLE_TELEMETRY_SCHEDULER"] = "false"
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
    if args.user_id:
        rows = [u for u in rows if str(u.get("id")) == str(args.user_id)]
        if not rows:
            print(f"sync: no Garmin-connected user with id={args.user_id}")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Garmin → Supabase sync (no secrets printed).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show Garmin connection/sync state without credentials")

    sync_p = sub.add_parser("sync", help="Run Garmin sync for connected users")
    sync_p.add_argument("--mode", choices=["incremental", "deep_365", "all_time"], default="incremental")
    sync_p.add_argument("--days-back", type=int, default=None)
    sync_p.add_argument("--user-id", default=None, help="Limit to one athlete id (from the users table)")
    sync_p.add_argument("--force", action="store_true", help="Force resync (skip delta-date skipping)")

    args = parser.parse_args(argv)
    app = _load_app()
    with app.app_context():
        if args.command == "status":
            return cmd_status(args)
        if args.command == "sync":
            return cmd_sync(args)
        parser.error(f"unknown command {args.command}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
