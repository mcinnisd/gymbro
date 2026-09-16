"""
Scope Garmin sync to one athlete.

`garmin_activities.activity_id` used to be UNIQUE globally, so syncing a second
user (e.g. 100) with the same Garmin account upserted those rows onto that user
and user 2's activities disappeared. Prefer --user-id / GYMBRO_GARMIN_SYNC_USER_IDS.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple


def parse_sync_user_allowlist() -> Optional[set]:
    raw = os.environ.get("GYMBRO_GARMIN_SYNC_USER_IDS", "").strip()
    if not raw:
        return None
    return {s.strip() for s in raw.split(",") if s.strip()}


def apply_sync_user_allowlist(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    allow = parse_sync_user_allowlist()
    if not allow:
        return list(rows)
    return [u for u in rows if str(u.get("id")) in allow]


def select_users_for_garmin_sync(
    rows: Sequence[Dict[str, Any]],
    *,
    user_id: Optional[str] = None,
    all_users: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Pick which Garmin-connected users to sync.

    Returns (selected_rows, error_message). error_message is set when the
    caller must pass --user-id because several accounts share Garmin creds.
    """
    selected = list(rows)
    if user_id is not None:
        selected = [u for u in selected if str(u.get("id")) == str(user_id)]
        if not selected:
            return [], f"no Garmin-connected user with id={user_id}"
        return selected, None

    selected = apply_sync_user_allowlist(selected)
    if all_users:
        return selected, None
    if len(selected) > 1:
        ids = ", ".join(str(u.get("id")) for u in selected)
        return [], (
            "multiple Garmin-connected users ({ids}). "
            "Pass --user-id 2 (the real athlete) or GYMBRO_GARMIN_SYNC_USER_IDS=2. "
            "Use --all-users only if you intend to sync every account."
        ).format(ids=ids)
    return selected, None


def normalize_garmin_user_id(user_id: Any) -> Any:
    return int(user_id) if str(user_id).isdigit() else user_id
