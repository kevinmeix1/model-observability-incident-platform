from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from model_observability_platform.checks import run_checks
from model_observability_platform.notification_dispatch import (
    OutboxDispatcher,
    SqliteReceiptSink,
)
from model_observability_platform.runtime_state import IncidentStore, OutboxLeaseConflict
from model_observability_platform.telemetry import generate_records

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
MODEL_VERSION = "risk-model-2026-07-15"


class FailingSink:
    def send(self, cloud_event: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(f"receiver unavailable for {cloud_event['id']}")


def evaluation_payload(evaluation_id: str) -> dict[str, Any]:
    return {
        "evaluation_id": evaluation_id,
        "model_name": "credit-risk-router",
        "model_version": MODEL_VERSION,
        "policy_version": "2026.07",
        "reference_window": generate_records(
            window="reference",
            rows=40,
            seed=71,
            started_at=NOW - timedelta(days=1),
        ),
        "current_window": generate_records(
            window="current",
            rows=40,
            seed=71,
            drift=True,
            errors=True,
            started_at=NOW - timedelta(minutes=9),
        ),
    }


def record(store: IncidentStore, evaluation_id: str, *, trace_id: str) -> dict[str, Any]:
    payload = evaluation_payload(evaluation_id)
    report = run_checks(
        payload["reference_window"],
        payload["current_window"],
        now=NOW,
    )
    response, replayed, changes = store.record_evaluation(
        request_payload=payload,
        report=report,
        trace_id=trace_id,
        created_at=NOW.isoformat(),
    )
    if replayed or not changes:
        raise RuntimeError("faulting evaluation did not create fresh incident events")
    return {"response": response, "changes": changes}


def run_contract(root: Path) -> dict[str, Any]:
    contract_root = root / "notification-outbox-contract"
    shutil.rmtree(contract_root, ignore_errors=True)
    store = IncidentStore(contract_root / "runtime" / "incidents.sqlite3")
    initial = record(store, "outbox-contract-eval-001", trace_id="1" * 32)
    target_id = initial["changes"][0]["incident_id"]
    target = store.get_incident(target_id)
    store.transition(
        incident_id=target_id,
        target_status="acknowledged",
        transition_id="outbox-contract-ack-001",
        expected_version=target["version"],
        actor="contract-oncall",
        note="exercise ordered lifecycle delivery",
        trace_id="2" * 32,
        created_at=(NOW + timedelta(seconds=1)).isoformat(),
    )
    initial_outbox = store.list_notifications()
    target_events = [item for item in initial_outbox if item["incident_id"] == target_id]
    first_event, second_event = target_events

    crashed = store.claim_notifications(
        worker_id="worker-crashed",
        limit=1,
        lease_seconds=10,
        claimed_at=NOW + timedelta(seconds=2),
    )
    standby = store.claim_notifications(
        worker_id="worker-standby",
        limit=100,
        lease_seconds=10,
        claimed_at=NOW + timedelta(seconds=5),
    )
    blocked_before_predecessor = second_event["event_id"] not in {
        item["event_id"] for item in standby
    }
    takeover = store.claim_notifications(
        worker_id="worker-recovery",
        limit=100,
        lease_seconds=10,
        claimed_at=NOW + timedelta(seconds=13),
    )
    recovered = next(item for item in takeover if item["event_id"] == first_event["event_id"])
    stale_worker_rejected = False
    try:
        store.complete_notification(
            event_id=first_event["event_id"],
            worker_id="worker-crashed",
            delivered=True,
            completed_at=NOW + timedelta(seconds=14),
        )
    except OutboxLeaseConflict:
        stale_worker_rejected = True
    retry, _ = store.complete_notification(
        event_id=recovered["event_id"],
        worker_id="worker-recovery",
        delivered=False,
        error="receiver returned HTTP 503",
        max_attempts=4,
        base_backoff_seconds=1,
        completed_at=NOW + timedelta(seconds=14),
    )

    sink = SqliteReceiptSink(contract_root / "receiver" / "receipts.sqlite3")
    dispatcher = OutboxDispatcher(
        store=store,
        sink=sink,
        worker_id="worker-delivery",
        lease_seconds=30,
        max_attempts=4,
        base_backoff_seconds=1,
    )
    first_delivery = dispatcher.run_once(
        limit=100,
        now=NOW + timedelta(seconds=17),
    )
    second_delivery = dispatcher.run_once(
        limit=100,
        now=NOW + timedelta(seconds=18),
    )
    delivered = {
        item["event_id"]: item for item in store.list_notifications(status="delivered")
    }
    receipt_replay = sink.send(delivered[first_event["event_id"]]["cloud_event"])

    fault = record(store, "outbox-contract-eval-002", trace_id="3" * 32)
    failure_dispatcher = OutboxDispatcher(
        store=store,
        sink=FailingSink(),
        worker_id="worker-dead-letter",
        lease_seconds=30,
        max_attempts=1,
    )
    dead_letter = failure_dispatcher.run_once(
        limit=100,
        now=NOW + timedelta(seconds=20),
    )
    attempts = store.notification_attempts(first_event["event_id"])
    envelope = first_event["cloud_event"]
    checks = {
        "atomic_outbox_write": len(initial_outbox) == len(initial["changes"]) + 1,
        "cloudevents_envelope": envelope.get("specversion") == "1.0"
        and envelope.get("id") == first_event["event_id"]
        and envelope.get("subject") == target_id
        and envelope.get("data", {}).get("incident_version") == 1,
        "per_incident_ordering": [item["incident_version"] for item in target_events]
        == [1, 2]
        and blocked_before_predecessor,
        "lease_takeover": crashed[0]["event_id"] == recovered["event_id"]
        and recovered["attempt_count"] == 2,
        "stale_worker_rejected": stale_worker_rejected,
        "exponential_retry": retry["status"] == "pending"
        and retry["available_at"] == (NOW + timedelta(seconds=16)).isoformat(),
        "ordered_delivery": first_event["event_id"] in delivered
        and second_event["event_id"] in delivered
        and first_delivery["delivered"] >= 1
        and second_delivery["delivered"] >= 1,
        "idempotent_consumer": receipt_replay["replayed"] is True,
        "immutable_attempt_audit": [item["outcome"] for item in attempts]
        == ["lease_expired", "retry_scheduled", "delivered"],
        "dead_letter_terminal_state": dead_letter["dead_lettered"] >= 1
        and bool(store.list_notifications(status="dead_letter")),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"notification outbox contract failed: {', '.join(failed)}")
    return {
        "passed": True,
        "checked_at": NOW.isoformat(),
        "delivery_semantics": "transactional-outbox-at-least-once",
        "ordering_scope": "incident_id",
        "checks": checks,
        "evidence": {
            "initial_events": len(initial_outbox),
            "delivery_receipts": sink.count(),
            "dead_letter_events": len(store.list_notifications(status="dead_letter")),
            "recovered_event_id": recovered["event_id"],
            "recovered_attempt_count": recovered["attempt_count"],
            "attempt_outcomes": [item["outcome"] for item in attempts],
            "fault_incident_changes": len(fault["changes"]),
        },
        "production_boundary": (
            "SQLite serializes one local writer. Production migration uses Postgres row locks "
            "or broker delivery, multiple workers, jittered retries, and an idempotent receiver."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise incident notification outbox recovery")
    parser.add_argument("--output", default=".local")
    args = parser.parse_args()
    root = Path(args.output)
    report = run_contract(root)
    path = root / "reports" / "notification_outbox_contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"contract_passed": True, "report": str(path), **report["evidence"]}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
