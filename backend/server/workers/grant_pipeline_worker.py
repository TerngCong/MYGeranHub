"""
Daily grant pipeline worker that orchestrates the full JamAI flow:
1. Scrape grants (Agent 1)
2. Verify/correct grants (Agent 2)
3. Wait for the `grant_decider` LLM column
4. Sync approved records into the knowledge table

Run with:
    python -m backend.server.workers.grant_pipeline_worker --once
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from jamaibase import JamAI  # type: ignore[import-not-found]

from agents.agent1 import run_scraper_job
from agents.agent2 import run_grant_verifier
from server.core.config import settings
from server.services.grant_sync import grant_sync_service

DEFAULT_HOUR = 3
DEFAULT_MINUTE = 30
DEFAULT_DECIDER_TIMEOUT = 180  # seconds
DEFAULT_DECIDER_POLL = 15  # seconds

logger = logging.getLogger(__name__)
OBSERVABILITY_LOG_PATH = Path(__file__).resolve().parents[3] / "debug_grant_manager.log"
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
    logger.info(
        "Next grant pipeline run scheduled at %s (sleeping %.1f seconds)",
        (datetime.now() + timedelta(seconds=wait_seconds)).strftime("%Y-%m-%d %H:%M:%S"),
        wait_seconds,
    )
    slept = 0.0
    while slept < wait_seconds and not _shutdown_requested:
        chunk = min(60.0, wait_seconds - slept)
        time.sleep(chunk)
        slept += chunk


def _extract_column_value(row: Dict[str, object], column_name: str) -> Optional[str]:
    data = row.get(column_name)
    if data is None and "columns" in row and isinstance(row["columns"], dict):
        data = row["columns"].get(column_name)

    if isinstance(data, dict):
        for key in ("value", "text", "description"):
            if key in data and isinstance(data[key], str):
                value = data[key].strip()
                return value or None
    elif isinstance(data, str):
        value = data.strip()
        return value or None
    return None


def _extract_response_items(response: Any) -> Optional[List[Any]]:
    if response is None:
        return None
    items_attr = getattr(response, "items", None)
    if callable(items_attr):
        try:
            result = items_attr()
            if isinstance(result, list):
                return result
        except TypeError:
            pass
    elif isinstance(items_attr, list):
        return items_attr
    if isinstance(response, dict):
        result = response.get("items")
        if isinstance(result, list):
            return result
    return None


def _wait_for_grant_decider(
    row_ids: List[str],
    timeout: int = DEFAULT_DECIDER_TIMEOUT,
    poll_interval: int = DEFAULT_DECIDER_POLL,
) -> Dict[str, Optional[str]]:
    if not row_ids:
        return {}

    project_id = settings.jamai_sdk_project_id or settings.jamai_project_id
    token = settings.jamai_sdk_token or settings.jamai_api_key
    if not project_id or not token:
        logger.warning("JamAI credentials missing; skipping grant_decider polling.")
        return {row_id: None for row_id in row_ids}

    table_id = settings.jamai_scrap_result_table_id or os.getenv("JAMAI_SCRAP_RESULT_TABLE_ID", "scrap_result")
    client = JamAI(project_id=project_id, token=token)
    pending = set(row_ids)
    decider_results: Dict[str, Optional[str]] = {row_id: None for row_id in row_ids}
    deadline = time.time() + max(1, timeout)

    while pending and time.time() < deadline and not _shutdown_requested:
        logger.info("Polling grant_decider for %d rows...", len(pending))
        still_pending: List[str] = []
        for row_id in list(pending):
            try:
                response = client.table.get_table_row("action", table_id, row_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch row %s while waiting for grant_decider: %s", row_id, exc)
                still_pending.append(row_id)
                continue

            items = _extract_response_items(response)
            row_data = items[0] if items else {}
            decider_value = _extract_column_value(row_data, "grant_decider")
            if decider_value:
                decider_results[row_id] = decider_value
            else:
                still_pending.append(row_id)

        pending = set(still_pending)
        if pending:
            time.sleep(poll_interval)

    if pending:
        logger.warning("grant_decider polling timed out for rows: %s", ", ".join(sorted(pending)))
    return decider_results


def _run_pipeline(limit: Optional[int], max_candidates: Optional[int]) -> Dict[str, object]:
    logger.info("Starting full grant pipeline run...")
    stage_summary: Dict[str, object] = {}

    scraper_summary = run_scraper_job(
        skip_existing=True,
        max_candidates=max_candidates,
    )
    stage_summary["scraper"] = scraper_summary.to_dict()

    row_ids = scraper_summary.processed_row_ids
    verifier_summary = None
    if row_ids:
        verifier_summary = run_grant_verifier(row_ids=row_ids)
        stage_summary["verifier"] = verifier_summary.to_dict()
        decider_results = _wait_for_grant_decider(row_ids)
        stage_summary["grant_decider"] = decider_results
    else:
        stage_summary["verifier"] = {"skipped": True, "reason": "no new/updated rows"}
        stage_summary["grant_decider"] = {}

    try:
        sync_result = grant_sync_service.sync_pending_grants(limit=limit or 20)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Knowledge sync failed: %s", exc)
        sync_result = {"processed": 0, "synced": 0, "failed": 0, "skipped": 0, "error": str(exc)}

    stage_summary["knowledge_sync"] = sync_result
    _append_observability_log(stage_summary)
    logger.info("Grant pipeline run completed: %s", json.dumps(stage_summary, indent=2))
    return stage_summary


def _append_observability_log(entry: Dict[str, object]) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "entry": entry,
    }
    try:
        OBSERVABILITY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OBSERVABILITY_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to append observability log: %s", exc)


def run_worker(
    hour: int,
    minute: int,
    limit: Optional[int],
    max_candidates: Optional[int],
    run_once: bool,
) -> None:
    if run_once:
        _run_pipeline(limit, max_candidates)
        return

    logger.info(
        "Grant pipeline worker started. Running daily at %02d:%02d local time.",
        hour,
        minute,
    )

    while not _shutdown_requested:
        _sleep_until_next_run(hour, minute)
        if _shutdown_requested:
            break
        try:
            _run_pipeline(limit, max_candidates)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Grant pipeline run failed: %s", exc)

    logger.info("Grant pipeline worker stopped.")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Daily grant pipeline worker")
    parser.add_argument("--hour", type=int, default=DEFAULT_HOUR, help="Hour (0-23) to run the pipeline.")
    parser.add_argument("--minute", type=int, default=DEFAULT_MINUTE, help="Minute (0-59) to run the pipeline.")
    parser.add_argument("--limit", type=int, default=None, help="Row limit for the knowledge sync stage.")
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Optional cap for Agent 1 grant candidates per run.",
    )
    parser.add_argument("--once", action="store_true", help="Run the pipeline immediately and exit.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not 0 <= args.hour <= 23:
        parser.error("hour must be between 0 and 23")
    if not 0 <= args.minute <= 59:
        parser.error("minute must be between 0 and 59")

    run_worker(
        hour=args.hour,
        minute=args.minute,
        limit=args.limit,
        max_candidates=args.max_candidates,
        run_once=args.once,
    )


if __name__ == "__main__":
    main()

