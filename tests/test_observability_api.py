from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from fastapi.testclient import TestClient

    from model_observability_platform.api import Settings, create_app
    from model_observability_platform.dashboard import render_dashboard
    from model_observability_platform.notification_dispatch import (
        OutboxDispatcher,
        SqliteReceiptSink,
    )
    from model_observability_platform.notification_worker import main as notification_worker_main
    from model_observability_platform.runtime_state import IncidentStore, OutboxLeaseConflict
    from model_observability_platform.telemetry import generate_records

    RUNTIME_AVAILABLE = True
except ImportError:
    TestClient = None
    Settings = None
    create_app = None
    generate_records = None
    render_dashboard = None
    OutboxDispatcher = None
    SqliteReceiptSink = None
    notification_worker_main = None
    OutboxLeaseConflict = None
    IncidentStore = None
    RUNTIME_AVAILABLE = False


NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
MODEL_VERSION = "risk-model-2026-07-15"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"


@unittest.skipUnless(RUNTIME_AVAILABLE, "runtime dependencies are not installed")
class ObservabilityApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def app(self, **overrides):
        values = {
            "state_root": self.state_root,
            "capture_spans": True,
            "trace_sample_ratio": 1.0,
            "max_request_bytes": 2_000_000,
            "auto_resolve_after": 2,
        }
        values.update(overrides)
        return create_app(Settings(**values), clock=lambda: NOW)

    @staticmethod
    def payload(
        evaluation_id: str,
        *,
        drift: bool,
        errors: bool = False,
        current_seed: int = 71,
    ) -> dict:
        reference = generate_records(
            window="reference",
            rows=40,
            seed=71,
            started_at=NOW - timedelta(days=1),
        )
        current = generate_records(
            window="current",
            rows=40,
            seed=current_seed,
            drift=drift,
            errors=errors,
            started_at=NOW - timedelta(minutes=9),
        )
        return {
            "evaluation_id": evaluation_id,
            "model_name": "credit-risk-router",
            "model_version": MODEL_VERSION,
            "policy_version": "2026.07",
            "reference_window": reference,
            "current_window": current,
        }

    def open_incident(self, client: TestClient, evaluation_id: str = "eval-drift-001"):
        result = client.post(
            "/v1/evaluations",
            json=self.payload(evaluation_id, drift=True, errors=True),
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["passed"])
        incidents = client.get("/v1/incidents").json()["incidents"]
        self.assertGreater(len(incidents), 0)
        return result, incidents[0]

    def test_health_evaluation_metrics_and_trace_contract(self) -> None:
        app = self.app()
        with TestClient(app) as client:
            self.assertEqual(client.get("/health/live").json(), {"live": True})
            self.assertEqual(client.get("/health/ready").json(), {"ready": True})
            runtime = client.get("/v1/runtime").json()
            self.assertEqual(runtime["state_backend"], "sqlite-wal")
            self.assertEqual(runtime["telemetry"]["metrics"], "prometheus")

            response = client.post(
                "/v1/evaluations",
                headers={"traceparent": TRACEPARENT, "x-request-id": "request-001"},
                json=self.payload("eval-traced-001", drift=True, errors=True),
            )
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertFalse(result["passed"])
            self.assertTrue(result["decision"]["release_frozen"])
            self.assertEqual(response.headers["x-trace-id"], TRACE_ID)
            self.assertEqual(response.headers["x-request-id"], "request-001")
            self.assertEqual(response.headers["x-idempotent-replay"], "false")

            metrics = client.get("/metrics").text
            self.assertIn("model_observability_evaluations_total", metrics)
            self.assertIn("model_observability_open_incidents", metrics)
            self.assertIn('check="feature_drift"', metrics)
            self.assertNotIn("eval-traced-001", metrics)
            self.assertNotIn("request-001", metrics)
            self.assertNotIn(MODEL_VERSION, metrics)

            exporter = app.state.span_exporter
            spans = exporter.finished_spans()
            names = {span.name for span in spans}
            self.assertIn("POST /v1/evaluations", names)
            self.assertIn("model_observability.evaluate", names)
            server_span = next(span for span in spans if span.name == "POST /v1/evaluations")
            self.assertEqual(format(server_span.context.trace_id, "032x"), TRACE_ID)
            self.assertEqual(server_span.attributes["http.route"], "/v1/evaluations")
            self.assertNotIn("url.full", server_span.attributes)

    def test_runtime_schema_migrates_v1_and_rejects_future_versions(self) -> None:
        legacy_path = self.state_root / "legacy" / "incidents.sqlite3"
        legacy_path.parent.mkdir(parents=True)
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                "CREATE TABLE runtime_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO runtime_metadata(key, value) VALUES ('schema_version', '1')"
            )
        migrated = IncidentStore(legacy_path)
        self.assertTrue(migrated.ready())
        self.assertEqual(migrated.summary()["schema_version"], "2")
        self.assertEqual(migrated.summary()["notifications_by_status"]["pending"], 0)

        future_path = self.state_root / "future" / "incidents.sqlite3"
        future_path.parent.mkdir(parents=True)
        with sqlite3.connect(future_path) as connection:
            connection.execute(
                "CREATE TABLE runtime_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO runtime_metadata(key, value) VALUES ('schema_version', '99')"
            )
        with self.assertRaisesRegex(RuntimeError, "newer than supported"):
            IncidentStore(future_path)

    def test_evaluation_idempotency_survives_restart_and_rejects_conflict(self) -> None:
        payload = self.payload("eval-restart-001", drift=True)
        first_app = self.app()
        with TestClient(first_app) as client:
            first = client.post("/v1/evaluations", json=payload)
            self.assertEqual(first.status_code, 200, first.text)
            before = client.get("/v1/incidents").json()["incidents"]
            occurrences = {
                incident["incident_id"]: incident["occurrence_count"]
                for incident in before
            }

        second_app = self.app()
        with TestClient(second_app) as client:
            replay = client.post("/v1/evaluations", json=payload)
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertTrue(replay.json()["replayed"])
            self.assertEqual(replay.headers["x-idempotent-replay"], "true")
            after = client.get("/v1/incidents").json()["incidents"]
            self.assertEqual(
                occurrences,
                {
                    incident["incident_id"]: incident["occurrence_count"]
                    for incident in after
                },
            )

            conflict_payload = self.payload(
                "eval-restart-001",
                drift=True,
                current_seed=72,
            )
            conflict = client.post("/v1/evaluations", json=conflict_payload)
            self.assertEqual(conflict.status_code, 409)
            self.assertIn("different payload", conflict.json()["error"])

    def test_stable_fingerprint_updates_evidence_without_duplicate_incidents(self) -> None:
        with TestClient(self.app()) as client:
            first = client.post(
                "/v1/evaluations",
                json=self.payload("eval-evidence-001", drift=True),
            )
            self.assertEqual(first.status_code, 200, first.text)
            initial = {
                item["check"]: item
                for item in client.get("/v1/incidents").json()["incidents"]
            }
            second = client.post(
                "/v1/evaluations",
                json=self.payload(
                    "eval-evidence-002",
                    drift=True,
                    current_seed=72,
                ),
            )
            self.assertEqual(second.status_code, 200, second.text)
            updated = {
                item["check"]: item
                for item in client.get("/v1/incidents").json()["incidents"]
            }
            self.assertEqual(set(initial), set(updated))
            for check_name in initial:
                self.assertEqual(
                    initial[check_name]["incident_id"],
                    updated[check_name]["incident_id"],
                )
                self.assertEqual(
                    updated[check_name]["occurrence_count"],
                    initial[check_name]["occurrence_count"] + 1,
                )

    def test_incident_transitions_are_optimistic_and_idempotent(self) -> None:
        with TestClient(self.app()) as client:
            _, incident = self.open_incident(client)
            incident_id = incident["incident_id"]
            acknowledgement = {
                "transition_id": "transition-ack-001",
                "expected_version": incident["version"],
                "actor": "oncall-engineer",
                "note": "investigation started",
            }
            acknowledged = client.post(
                f"/v1/incidents/{incident_id}/acknowledge",
                json=acknowledgement,
            )
            self.assertEqual(acknowledged.status_code, 200, acknowledged.text)
            self.assertEqual(acknowledged.json()["incident"]["status"], "acknowledged")
            acknowledged_version = acknowledged.json()["incident"]["version"]

            replay = client.post(
                f"/v1/incidents/{incident_id}/acknowledge",
                json=acknowledgement,
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertTrue(replay.json()["replayed"])

            reused_key = dict(acknowledgement, note="different request")
            conflict = client.post(
                f"/v1/incidents/{incident_id}/acknowledge",
                json=reused_key,
            )
            self.assertEqual(conflict.status_code, 409)

            stale = client.post(
                f"/v1/incidents/{incident_id}/resolve",
                json={
                    "transition_id": "transition-resolve-stale",
                    "expected_version": incident["version"],
                    "actor": "oncall-engineer",
                },
            )
            self.assertEqual(stale.status_code, 409)

            resolved = client.post(
                f"/v1/incidents/{incident_id}/resolve",
                json={
                    "transition_id": "transition-resolve-001",
                    "expected_version": acknowledged_version,
                    "actor": "oncall-engineer",
                    "note": "evidence reviewed",
                },
            )
            self.assertEqual(resolved.status_code, 200, resolved.text)
            self.assertEqual(resolved.json()["incident"]["status"], "resolved")
            events = client.get(f"/v1/incidents/{incident_id}/events").json()
            self.assertEqual(events["events"][-2]["event_type"], "acknowledged")
            self.assertEqual(events["events"][-1]["event_type"], "resolved")
            bounded = client.get(
                f"/v1/incidents/{incident_id}/events",
                params={"limit": 1},
            ).json()
            self.assertEqual(bounded["count"], 1)
            self.assertEqual(bounded["events"][0]["event_type"], "resolved")

    def test_incident_events_create_atomic_cloudevents_outbox_records(self) -> None:
        with TestClient(self.app()) as client:
            response, incident = self.open_incident(client, "eval-outbox-001")
            created_changes = response.json()["incident_changes"]
            listing = client.get("/v1/notifications").json()
            self.assertEqual(listing["count"], len(created_changes))
            event_ids = set()
            for notification in listing["notifications"]:
                event = notification["cloud_event"]
                event_ids.add(event["id"])
                self.assertEqual(event["specversion"], "1.0")
                self.assertEqual(
                    event["type"],
                    "io.github.kevinmeix1.model-observability.incident.lifecycle.v1",
                )
                self.assertEqual(event["id"], notification["event_id"])
                self.assertEqual(event["subject"], notification["incident_id"])
                self.assertEqual(event["data"]["incident_version"], 1)
                self.assertEqual(notification["status"], "pending")
            self.assertEqual(len(event_ids), listing["count"])

            replay = client.post(
                "/v1/evaluations",
                json=self.payload("eval-outbox-001", drift=True, errors=True),
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertTrue(replay.json()["replayed"])
            self.assertEqual(client.get("/v1/notifications").json()["count"], len(event_ids))

            acknowledgement = client.post(
                f"/v1/incidents/{incident['incident_id']}/acknowledge",
                json={
                    "transition_id": "transition-outbox-ack-001",
                    "expected_version": incident["version"],
                    "actor": "oncall-engineer",
                },
            )
            self.assertEqual(acknowledgement.status_code, 200, acknowledgement.text)
            outbox = client.get("/v1/notifications").json()["notifications"]
            lifecycle = [
                item for item in outbox if item["incident_id"] == incident["incident_id"]
            ]
            self.assertEqual([item["incident_version"] for item in lifecycle], [1, 2])
            self.assertEqual([item["event_type"] for item in lifecycle], ["opened", "acknowledged"])
            metrics = client.get("/metrics").text
            self.assertIn("model_observability_notification_outbox_events", metrics)
            self.assertNotIn(next(iter(event_ids)), metrics)

    def test_outbox_claims_are_disjoint_ordered_and_lease_safe(self) -> None:
        app = self.app()
        with TestClient(app) as client:
            _, incident = self.open_incident(client, "eval-outbox-leases-001")
            acknowledged = client.post(
                f"/v1/incidents/{incident['incident_id']}/acknowledge",
                json={
                    "transition_id": "transition-outbox-leases-001",
                    "expected_version": incident["version"],
                    "actor": "oncall-engineer",
                },
            )
            self.assertEqual(acknowledged.status_code, 200, acknowledged.text)

        store = app.state.incident_store

        def claim(worker: str) -> list[dict]:
            return store.claim_notifications(
                worker_id=worker,
                limit=2,
                lease_seconds=10,
                claimed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = executor.map(claim, ("worker-a", "worker-b"))
        first_ids = {item["event_id"] for item in first}
        second_ids = {item["event_id"] for item in second}
        self.assertTrue(first_ids)
        self.assertTrue(second_ids)
        self.assertTrue(first_ids.isdisjoint(second_ids))

        incident_claims = [
            item
            for item in [*first, *second]
            if item["incident_id"] == incident["incident_id"]
        ]
        self.assertEqual(len(incident_claims), 1)
        self.assertEqual(incident_claims[0]["incident_version"], 1)
        leased = incident_claims[0]
        original_worker = leased["lease_owner"]
        takeover = store.claim_notifications(
            worker_id="worker-takeover",
            limit=100,
            lease_seconds=10,
            claimed_at=NOW + timedelta(seconds=11),
        )
        taken = next(item for item in takeover if item["event_id"] == leased["event_id"])
        with self.assertRaises(OutboxLeaseConflict):
            store.complete_notification(
                event_id=leased["event_id"],
                worker_id=original_worker,
                delivered=True,
                completed_at=NOW + timedelta(seconds=12),
            )
        retry, _ = store.complete_notification(
            event_id=taken["event_id"],
            worker_id="worker-takeover",
            delivered=False,
            error="receiver unavailable",
            max_attempts=3,
            base_backoff_seconds=2,
            completed_at=NOW + timedelta(seconds=12),
        )
        self.assertEqual(retry["status"], "pending")
        attempts = store.notification_attempts(taken["event_id"])
        self.assertEqual(
            [attempt["outcome"] for attempt in attempts],
            ["lease_expired", "retry_scheduled"],
        )

        sink = SqliteReceiptSink(self.state_root / "receiver" / "receipts.sqlite3")
        dispatcher = OutboxDispatcher(
            store=store,
            sink=sink,
            worker_id="worker-recovery",
            lease_seconds=10,
            max_attempts=3,
            base_backoff_seconds=2,
        )
        recovered = dispatcher.run_once(
            limit=100,
            now=NOW + timedelta(seconds=17),
        )
        self.assertGreaterEqual(recovered["delivered"], 1)
        delivered = {
            item["event_id"]: item
            for item in store.list_notifications(status="delivered")
        }
        self.assertIn(taken["event_id"], delivered)
        receipt_replay = sink.send(delivered[taken["event_id"]]["cloud_event"])
        self.assertTrue(receipt_replay["replayed"])

        next_claim = store.claim_notifications(
            worker_id="worker-next-version",
            limit=100,
            lease_seconds=10,
            claimed_at=NOW + timedelta(seconds=18),
        )
        incident_versions = [
            item["incident_version"]
            for item in next_claim
            if item["incident_id"] == incident["incident_id"]
        ]
        self.assertEqual(incident_versions, [2])

    def test_notification_worker_entrypoint_drains_due_events_once(self) -> None:
        app = self.app()
        with TestClient(app) as client:
            self.open_incident(client, "eval-worker-entrypoint-001")
        output = io.StringIO()
        with redirect_stdout(output):
            result = notification_worker_main(
                [
                    "--state-root",
                    str(self.state_root),
                    "--worker-id",
                    "worker-entrypoint-test",
                    "--batch-size",
                    "100",
                    "--once",
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn('"event":"notification_dispatch_batch"', output.getvalue())
        summary = app.state.incident_store.summary()
        self.assertEqual(summary["notifications_by_status"]["pending"], 0)
        self.assertEqual(summary["notifications_by_status"]["in_flight"], 0)
        self.assertGreater(summary["notifications_by_status"]["delivered"], 0)

    def test_two_healthy_windows_auto_resolve_open_incidents(self) -> None:
        with TestClient(self.app(auto_resolve_after=2)) as client:
            self.open_incident(client, "eval-recovery-failed")
            first = client.post(
                "/v1/evaluations",
                json=self.payload("eval-recovery-healthy-1", drift=False),
            )
            self.assertEqual(first.status_code, 200, first.text)
            self.assertTrue(first.json()["passed"])
            self.assertGreater(first.json()["decision"]["open_incident_count"], 0)

            second = client.post(
                "/v1/evaluations",
                json=self.payload("eval-recovery-healthy-2", drift=False),
            )
            self.assertEqual(second.status_code, 200, second.text)
            self.assertTrue(second.json()["passed"])
            self.assertEqual(second.json()["decision"]["open_incident_count"], 0)
            resolved = client.get("/v1/incidents", params={"status": "resolved"}).json()
            self.assertGreater(resolved["count"], 0)
            runtime = client.get("/v1/runtime").json()
            self.assertEqual(runtime["summary"]["open_count"], 0)

            reopened = client.post(
                "/v1/evaluations",
                json=self.payload("eval-recovery-failed-again", drift=True, errors=True),
            )
            self.assertEqual(reopened.status_code, 200, reopened.text)
            self.assertGreater(reopened.json()["decision"]["open_incident_count"], 0)
            self.assertIn(
                "reopened",
                {change["change"] for change in reopened.json()["incident_changes"]},
            )

    def test_dashboard_distinguishes_executable_runtime_evidence(self) -> None:
        with TestClient(self.app()) as client:
            result, incident = self.open_incident(client, "eval-dashboard-001")
            runtime = client.get("/v1/runtime").json()
        path = render_dashboard(
            self.state_root / "dashboard.html",
            report=result.json()["report"],
            incident_summary={
                "incidents": [incident],
                "open_count": 1,
                "created_count": 1,
                "severity": "high",
            },
            reliability_plan={
                "recommended_action": "page_and_freeze_rollouts",
                "error_budget_burn_rate": 5.2,
                "routing": {"owner": "ml-platform-oncall"},
                "impacted_assets": ["credit_risk_api"],
            },
            runtime_contract={
                "passed": True,
                "checks": {
                    "evaluation_replay": True,
                    "transition_replay": True,
                    "stable_trace_header": True,
                    "low_cardinality_metrics": True,
                },
                "runtime": runtime,
            },
            notification_contract={
                "delivery_semantics": "transactional-outbox-at-least-once",
                "checks": {
                    "lease_takeover": True,
                    "stale_worker_rejected": True,
                    "ordered_delivery": True,
                    "dead_letter_terminal_state": True,
                },
            },
        )
        html = path.read_text(encoding="utf-8")
        self.assertIn("Executable Runtime", html)
        self.assertIn("sqlite-wal", html)
        self.assertIn("Metric cardinality", html)
        self.assertIn("Notification Delivery", html)
        self.assertIn("Stale worker fencing", html)
        self.assertIn("Live Incident Response Lab", html)
        self.assertIn("function runRecovery", html)
        self.assertIn('class="table-wrap"', html)
        self.assertNotIn('class="summary"', html)

    def test_validation_body_limit_filters_and_not_found_are_bounded(self) -> None:
        payload = self.payload("eval-invalid-001", drift=False)
        payload["current_window"] = payload["current_window"][:10]
        with TestClient(self.app()) as client:
            invalid = client.post("/v1/evaluations", json=payload)
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(
                invalid.json()["error"],
                "request schema validation failed",
            )
            bad_filter = client.get("/v1/incidents", params={"status": "unknown"})
            self.assertEqual(bad_filter.status_code, 422)
            missing = client.get("/v1/incidents/inc_missing")
            self.assertEqual(missing.status_code, 404)

        with TestClient(self.app(max_request_bytes=1_024)) as client:
            too_large = client.post(
                "/v1/evaluations",
                json=self.payload("eval-too-large-001", drift=False),
            )
            self.assertEqual(too_large.status_code, 413)
            self.assertIn("configured limit", too_large.json()["error"])


if __name__ == "__main__":
    unittest.main()
