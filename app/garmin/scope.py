"""
Scope Garmin sync to one athlete.

`garmin_activities.activity_id` used to be UNIQUE globally, so syncing a second
user (e.g. 100) with the same Garmin account upserted those rows onto that user
and user 2's activities disappeared. Prefer --user-id / GYMBRO_GARMIN_SYNC_USER_IDS.

Duplicate garmin_email across test users is a second fan-out: deep sync of the
same Garmin account wrote activities onto user 100 while biometrics stayed on
user 2. Collapse to one user per email (allowlist, then lowest numeric id).
Do not log or return Garmin emails.
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


def normalize_garmin_email(email: Any) -> str:
    return str(email or "").strip().lower()


def _user_id_sort_key(user: Dict[str, Any]) -> Tuple[int, Any]:
    uid = user.get("id")
    try:
        return (0, int(uid))
    except (TypeError, ValueError):
        return (1, str(uid))


def preferred_user_for_garmin_group(group: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep allowlisted id if present, else the lowest numeric user id."""
    if not group:
        raise ValueError("preferred_user_for_garmin_group requires at least one user")
    allow = parse_sync_user_allowlist() or set()
    allowlisted = [u for u in group if str(u.get("id")) in allow]
    pool = allowlisted or list(group)
    return sorted(pool, key=_user_id_sort_key)[0]


def collapse_duplicate_garmin_emails(
    rows: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    One Garmin email → one user. Prefer GYMBRO_GARMIN_SYNC_USER_IDS, else
    lowest numeric id. Returns (kept_rows, skipped_user_ids). Never includes
    email addresses in skipped_user_ids.
    """
    kept: List[Dict[str, Any]] = []
    skipped: List[str] = []
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for user in rows:
        email = normalize_garmin_email(user.get("garmin_email"))
        if not email:
            kept.append(user)
            continue
        groups.setdefault(email, []).append(user)
    for group in groups.values():
        winner = preferred_user_for_garmin_group(group)
        winner_id = str(winner.get("id"))
        kept.append(winner)
        for user in group:
            uid = str(user.get("id"))
            if uid != winner_id:
                skipped.append(uid)
    return kept, skipped


def _canonical_user_sharing_email(
    rows: Sequence[Dict[str, Any]], user_id: str
) -> Optional[Dict[str, Any]]:
    requested = next((u for u in rows if str(u.get("id")) == str(user_id)), None)
    if not requested:
        return None
    email = normalize_garmin_email(requested.get("garmin_email"))
    if not email:
        return requested
    group = [u for u in rows if normalize_garmin_email(u.get("garmin_email")) == email]
    return preferred_user_for_garmin_group(group)


def select_users_for_garmin_sync(
    rows: Sequence[Dict[str, Any]],
    *,
    user_id: Optional[str] = None,
    all_users: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Pick which Garmin-connected users to sync.

    Returns (selected_rows, error_message). error_message is set when the
    caller must pass --user-id because several accounts share Garmin creds,
    or when --user-id points at a duplicate of the canonical athlete.
    Messages include user ids only — never Garmin emails.
    """
    all_rows = list(rows)
    if user_id is not None:
        selected = [u for u in all_rows if str(u.get("id")) == str(user_id)]
        if not selected:
            return [], f"no Garmin-connected user with id={user_id}"
        canonical = _canonical_user_sharing_email(all_rows, str(user_id))
        if canonical is not None and str(canonical.get("id")) != str(user_id):
            return [], (
                "user_id={requested} shares a Garmin account with user_id={canonical}. "
                "Sync the canonical athlete (--user-id {canonical}) instead of "
                "duplicate test users."
            ).format(requested=user_id, canonical=canonical.get("id"))
        return selected, None

    selected = apply_sync_user_allowlist(all_rows)
    selected, _skipped = collapse_duplicate_garmin_emails(selected)
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
