# app/scheduler.py
"""
In-process APScheduler registration for Garmin → Supabase telemetry sync.

`scheduled_telemetry_sync` already existed but was never added to a scheduler.
This module is the durable registration path for always-on processes
(local Flask, Cloudflare tunnel, a VM). Cloud Run scale-to-zero still needs
an external ping of POST /internal/jobs/telemetry-sync (see docs/garmin-sync.md).
"""
import fcntl
import logging
import os

from flask_apscheduler import APScheduler

logger = logging.getLogger(__name__)

scheduler = APScheduler()
DEFAULT_LOCK_PATH = "/tmp/gymbro_telemetry_scheduler.lock"


def should_start_scheduler(app) -> bool:
    """Return True when this process should own the in-process telemetry scheduler."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if app.config.get("TESTING"):
        return False
    flag = os.environ.get("ENABLE_TELEMETRY_SCHEDULER")
    if flag is not None:
        return flag.strip().lower() in ("1", "true", "yes")
    return True


def _try_acquire_lock(path: str):
    """Non-blocking flock so only one gunicorn worker starts APScheduler."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        return fd
    except BlockingIOError:
        os.close(fd)
        return None


def _run_scheduled_sync():
    from app.scheduler_jobs import scheduled_telemetry_sync
    scheduled_telemetry_sync()


def init_telemetry_scheduler(app):
    """
    Register and start the incremental Garmin/Strava sync job on this Flask app.

    Returns True if this process started the scheduler.
    """
    if not should_start_scheduler(app):
        logger.info("Telemetry scheduler not started (disabled or test environment).")
        return False

    # Flask debug reloader: only the child process (WERKZEUG_RUN_MAIN=true) should start.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        logger.info("Telemetry scheduler skipped in Flask reloader parent process.")
        return False

    lock_path = os.environ.get("SCHEDULER_LOCK_FILE", DEFAULT_LOCK_PATH)
    lock_fd = _try_acquire_lock(lock_path)
    if lock_fd is None:
        logger.info("Telemetry scheduler already owned by another worker; skipping.")
        return False

    app.extensions["telemetry_scheduler_lock_fd"] = lock_fd

    interval_hours = int(os.environ.get("TELEMETRY_SYNC_INTERVAL_HOURS", "6"))
    app.config.setdefault("SCHEDULER_API_ENABLED", False)
    app.config.setdefault("SCHEDULER_TIMEZONE", "UTC")

    scheduler.init_app(app)
    existing = None
    try:
        existing = scheduler.get_job("telemetry_sync")
    except Exception:
        existing = None
    if existing is None:
        scheduler.add_job(
            id="telemetry_sync",
            func=_run_scheduled_sync,
            trigger="interval",
            hours=interval_hours,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    scheduler.start()
    logger.info("Telemetry scheduler started (interval=%sh, incremental Garmin sync).", interval_hours)
    return True
