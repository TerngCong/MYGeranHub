"""
Grant sync worker that mimics a cron job by running the JamAI sync once daily at 04:00.

Run with:
    python -m backend.server.workers.grant_sync_worker
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

from ..services.grant_sync import grant_sync_service

DEFAULT_HOUR = 4
DEFAULT_MINUTE = 0
logger = logging.getLogger(__name__)
_shutdown_requested = False


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _handle_signal(signum: int, frame) -> None:  # type: ignore[override]
    global _shutdown_requested
    logger.warning("Received signal %s. Graceful shutdown requested.", signum)
    _shutdown_requested = True


def _seconds_until(hour: int, minute: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    delta = target - now
    return delta.total_seconds()


def _sleep_until_next_run(hour: int, minute: int) -> None:
    wait_seconds = _seconds_until(hour, minute)
    logger.info("Next grant sync scheduled at %s (sleeping %.1f seconds)", (datetime.now() + timedelta(seconds=wait_seconds)).strftime("%Y-%m-%d %H:%M:%S"), wait_seconds)
    slept = 0.0
    while slept < wait_seconds and not _shutdown_requested:
        chunk = min(60.0, wait_seconds - slept)
        time.sleep(chunk)
        slept += chunk


def _run_sync(limit: Optional[int]) -> None:
    logger.info("Starting grant sync run (limit=%s)...", limit or "default")
    summary = grant_sync_service.sync_pending_grants(limit=limit or 20)
    logger.info("Grant sync completed: %s", summary)


def run_worker(hour: int, minute: int, limit: Optional[int], run_once: bool) -> None:
    if run_once:
        _run_sync(limit)
        return

    logger.info(
        "Grant sync worker started. Running daily at %02d:%02d local time.",
        hour,
        minute,
    )

    while not _shutdown_requested:
        _sleep_until_next_run(hour, minute)
        if _shutdown_requested:
            break
        try:
            _run_sync(limit)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Grant sync run failed: %s", exc)

    logger.info("Grant sync worker stopped.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Daily grant sync worker")
    parser.add_argument(
        "--hour",
        type=int,
        default=DEFAULT_HOUR,
        help="Hour (0-23) to run the sync. Defaults to 4.",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=DEFAULT_MINUTE,
        help="Minute (0-59) to run the sync. Defaults to 0.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit override for rows processed per run.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the sync immediately and exit (useful for manual triggers).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not 0 <= args.hour <= 23:
        parser.error("hour must be between 0 and 23")
    if not 0 <= args.minute <= 59:
        parser.error("minute must be between 0 and 59")

    run_worker(hour=args.hour, minute=args.minute, limit=args.limit, run_once=args.once)


if __name__ == "__main__":
    main()


