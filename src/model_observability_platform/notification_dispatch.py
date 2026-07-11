from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from .runtime_state import IncidentStore, canonical_hash, parse_utc


class ReceiptConflict(RuntimeError):
    pass


class NotificationSink(Protocol):
    def send(self, cloud_event: dict[str, Any]) -> dict[str, Any]: ...


class SqliteReceiptSink:
    """A durable idempotent consumer used by the executable local contract."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_receipts (
                    event_id TEXT PRIMARY KEY,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def send(self, cloud_event: dict[str, Any]) -> dict[str, Any]:
        event_id = str(cloud_event["id"])
        payload_hash = canonical_hash(cloud_event)
        payload_json = json.dumps(cloud_event, sort_keys=True, separators=(",", ":"))
        received_at = datetime.now(UTC).isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT payload_hash, received_at
                FROM notification_receipts
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                if existing["payload_hash"] != payload_hash:
                    raise ReceiptConflict(
                        f"event id {event_id} was already received with another payload"
                    )
                return {
                    "event_id": event_id,
                    "replayed": True,
                    "received_at": existing["received_at"],
                }
            connection.execute(
                """
                INSERT INTO notification_receipts (
                    event_id, payload_hash, payload_json, received_at
                ) VALUES (?, ?, ?, ?)
                """,
                (event_id, payload_hash, payload_json, received_at),
            )
            connection.commit()
            return {
                "event_id": event_id,
                "replayed": False,
                "received_at": received_at,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM notification_receipts"
                ).fetchone()["count"]
            )


class HttpCloudEventSink:
    def __init__(self, url: str, *, timeout_seconds: float = 5.0) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("webhook URL must use http or https")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.url = url
        self.timeout_seconds = timeout_seconds

    def send(self, cloud_event: dict[str, Any]) -> dict[str, Any]:
        event_id = str(cloud_event["id"])
        request = urllib.request.Request(
            self.url,
            data=json.dumps(cloud_event, sort_keys=True).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/cloudevents+json",
                "Idempotency-Key": event_id,
                "User-Agent": "model-observability-outbox/0.3",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"notification webhook returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"notification webhook failed: {exc.reason}") from exc
        if not 200 <= status < 300:
            raise RuntimeError(f"notification webhook returned HTTP {status}")
        return {"event_id": event_id, "replayed": False, "status_code": status}


@dataclass(frozen=True)
class OutboxDispatcher:
    store: IncidentStore
    sink: NotificationSink
    worker_id: str
    lease_seconds: float = 30.0
    max_attempts: int = 5
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 300.0

    def run_once(
        self,
        *,
        limit: int = 10,
        now: str | datetime | None = None,
    ) -> dict[str, Any]:
        dispatch_time = parse_utc(now or datetime.now(UTC))
        claimed = self.store.claim_notifications(
            worker_id=self.worker_id,
            limit=limit,
            lease_seconds=self.lease_seconds,
            claimed_at=dispatch_time,
        )
        results: list[dict[str, Any]] = []
        for notification in claimed:
            started = time.perf_counter()
            try:
                receipt = self.sink.send(notification["cloud_event"])
            except Exception as exc:
                updated, _ = self.store.complete_notification(
                    event_id=notification["event_id"],
                    worker_id=self.worker_id,
                    delivered=False,
                    error=f"{type(exc).__name__}: {exc}",
                    max_attempts=self.max_attempts,
                    base_backoff_seconds=self.base_backoff_seconds,
                    max_backoff_seconds=self.max_backoff_seconds,
                    completed_at=dispatch_time,
                )
                results.append(
                    {
                        "event_id": notification["event_id"],
                        "outcome": updated["status"],
                        "attempt_count": updated["attempt_count"],
                        "error": updated["last_error"],
                        "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
                    }
                )
                continue
            updated, replayed = self.store.complete_notification(
                event_id=notification["event_id"],
                worker_id=self.worker_id,
                delivered=True,
                max_attempts=self.max_attempts,
                base_backoff_seconds=self.base_backoff_seconds,
                max_backoff_seconds=self.max_backoff_seconds,
                completed_at=dispatch_time,
            )
            results.append(
                {
                    "event_id": notification["event_id"],
                    "outcome": "delivered",
                    "completion_replayed": replayed,
                    "sink_replayed": bool(receipt.get("replayed", False)),
                    "attempt_count": updated["attempt_count"],
                    "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
                }
            )
        return {
            "worker_id": self.worker_id,
            "claimed": len(claimed),
            "delivered": sum(result["outcome"] == "delivered" for result in results),
            "retry_scheduled": sum(result["outcome"] == "pending" for result in results),
            "dead_lettered": sum(result["outcome"] == "dead_letter" for result in results),
            "results": results,
        }
