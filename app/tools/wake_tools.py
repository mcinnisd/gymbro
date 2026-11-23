"""Read-only wake status for the coach. Same function the Garmin CLI calls."""

from typing import Any, Dict, Optional

from app.garmin.wake import get_wake_status as _get_wake_status


def get_wake_status(
    user_id: str,
    as_of: Optional[str] = None,
    timezone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Whether last night's sleep is finalized, or a secondary morning signal says the athlete is up.

    Server-bound ``user_id``. ``as_of`` is the local wake date (YYYY-MM-DD).
    Does not call Garmin.
    """
    return _get_wake_status(user_id, as_of=as_of, timezone=timezone)
