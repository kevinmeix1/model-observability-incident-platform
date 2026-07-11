from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import threading
from datetime import UTC, datetime
from pathlib import Path

from .notification_dispatch import HttpCloudEventSink, OutboxDispatcher, SqliteReceiptSink
from .runtime_state import IncidentStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deliver transactional incident notifications")
    parser.add_argument(
        "--state-root",
        default=os.getenv("OBSERVABILITY_STATE_ROOT", ".local"),
    )
    parser.add_argument(
        "--worker-id",
        default=os.getenv("NOTIFICATION_WORKER_ID")
        or f"{socket.gethostname()}-{os.getpid()}",
    )
    parser.add_argument("--webhook-url", default=os.getenv("NOTIFICATION_WEBHOOK_URL"))
    parser.add_argument("--receipt-db")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--lease-seconds", type=float, default=30.0)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--base-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--max-backoff-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.batch_size < 1:
        raise ValueError("batch-size must be positive")
    if args.poll_seconds <= 0:
        raise ValueError("poll-seconds must be positive")
    root = Path(args.state_root)
    store = IncidentStore(root / "runtime" / "incidents.sqlite3")
    if args.webhook_url and args.receipt_db:
        raise ValueError("choose either webhook-url or receipt-db")
    sink = (
        HttpCloudEventSink(args.webhook_url)
        if args.webhook_url
        else SqliteReceiptSink(
            args.receipt_db or root / "runtime" / "notification-receipts.sqlite3"
        )
    )
    dispatcher = OutboxDispatcher(
        store=store,
        sink=sink,
        worker_id=args.worker_id,
        lease_seconds=args.lease_seconds,
        max_attempts=args.max_attempts,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
    )
    stopping = threading.Event()

    def stop(_: int, __: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping.is_set():
        report = dispatcher.run_once(limit=args.batch_size)
        print(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "event": "notification_dispatch_batch",
                    **report,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )
        if args.once:
            break
        stopping.wait(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
