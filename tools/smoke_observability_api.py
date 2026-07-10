from __future__ import annotations

import argparse
import json
import shutil
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from model_observability_platform.telemetry import generate_records

MODEL_VERSION = "risk-model-2026-07-15"


class HttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "X-Request-ID": "smoke-client"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        body = response.read().decode("utf-8")
        content_type = response.headers.get("content-type", "")
        parsed: dict[str, Any] | str
        parsed = json.loads(body) if "json" in content_type else body
        return response.status, parsed, dict(response.headers)


class InProcessClient:
    def __init__(self, state_root: Path) -> None:
        from fastapi.testclient import TestClient

        from model_observability_platform.api import Settings, create_app

        shutil.rmtree(state_root / "runtime-contract", ignore_errors=True)
        self.client = TestClient(
            create_app(
                Settings(
                    state_root=state_root / "runtime-contract",
                    capture_spans=True,
                )
            )
        )
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        response = self.client.request(method, path, json=payload)
        content_type = response.headers.get("content-type", "")
        body = response.json() if "json" in content_type else response.text
        return response.status_code, body, dict(response.headers)


def require(status: int, expected: int, label: str) -> None:
    if status != expected:
        raise RuntimeError(f"{label}: expected HTTP {expected}, received {status}")


def payload(evaluation_id: str, *, now: datetime) -> dict[str, Any]:
    return {
        "evaluation_id": evaluation_id,
        "model_name": "credit-risk-router",
        "model_version": MODEL_VERSION,
        "policy_version": "2026.07",
        "reference_window": generate_records(
            window="reference",
            rows=40,
            seed=93,
            started_at=now - timedelta(days=1),
        ),
        "current_window": generate_records(
            window="current",
            rows=40,
            seed=93,
            drift=True,
            errors=True,
            started_at=now - timedelta(minutes=9),
        ),
    }


def run_contract(client: HttpClient | InProcessClient) -> dict[str, Any]:
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:12]
    evaluation = payload(f"smoke-eval-{suffix}", now=now)

    status, health, _ = client.request("GET", "/health/ready")
    require(status, 200, "readiness")
    status, first, first_headers = client.request("POST", "/v1/evaluations", evaluation)
    require(status, 200, "evaluation")
    status, replay, replay_headers = client.request("POST", "/v1/evaluations", evaluation)
    require(status, 200, "evaluation replay")
    status, listing, _ = client.request("GET", "/v1/incidents")
    require(status, 200, "incident listing")

    if not isinstance(listing, dict) or not listing.get("incidents"):
        raise RuntimeError("evaluation did not create an incident")
    incident = listing["incidents"][0]
    incident_id = incident["incident_id"]
    transition = {
        "transition_id": f"smoke-ack-{suffix}",
        "expected_version": incident["version"],
        "actor": "contract-smoke",
        "note": "smoke contract acknowledgement",
    }
    status, acknowledged, _ = client.request(
        "POST",
        f"/v1/incidents/{incident_id}/acknowledge",
        transition,
    )
    require(status, 200, "incident acknowledgement")
    status, transition_replay, _ = client.request(
        "POST",
        f"/v1/incidents/{incident_id}/acknowledge",
        transition,
    )
    require(status, 200, "transition replay")
    status, events, _ = client.request("GET", f"/v1/incidents/{incident_id}/events")
    require(status, 200, "incident event history")
    status, metrics, _ = client.request("GET", "/metrics")
    require(status, 200, "metrics")
    status, runtime, _ = client.request("GET", "/v1/runtime")
    require(status, 200, "runtime summary")

    checks = {
        "readiness": health == {"ready": True},
        "failed_evaluation_freezes_release": isinstance(first, dict)
        and first.get("decision", {}).get("release_frozen") is True,
        "evaluation_replay": isinstance(replay, dict)
        and replay.get("replayed") is True
        and replay_headers.get("x-idempotent-replay", "").lower() == "true",
        "stable_trace_header": len(first_headers.get("x-trace-id", "")) == 32,
        "incident_acknowledged": isinstance(acknowledged, dict)
        and acknowledged.get("incident", {}).get("status") == "acknowledged",
        "transition_replay": isinstance(transition_replay, dict)
        and transition_replay.get("replayed") is True,
        "audit_history": isinstance(events, dict) and events.get("count", 0) >= 2,
        "low_cardinality_metrics": isinstance(metrics, str)
        and "model_observability_evaluations_total" in metrics
        and evaluation["evaluation_id"] not in metrics
        and MODEL_VERSION not in metrics,
        "durable_summary": isinstance(runtime, dict)
        and runtime.get("state_backend") == "sqlite-wal",
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"runtime contract failed: {', '.join(failed)}")
    return {
        "passed": True,
        "checked_at": now.isoformat(),
        "checks": checks,
        "evaluation": {
            "passed": first["passed"],
            "failed_checks": first["failed_checks"],
            "release_frozen": first["decision"]["release_frozen"],
        },
        "incident": {
            "incident_id": incident_id,
            "check": incident["check"],
            "severity": incident["severity"],
            "status": acknowledged["incident"]["status"],
            "event_count": events["count"],
        },
        "runtime": runtime,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise the observability HTTP contract")
    parser.add_argument("--base-url")
    parser.add_argument("--output", default=".local")
    args = parser.parse_args()
    root = Path(args.output)
    client: HttpClient | InProcessClient
    client = HttpClient(args.base_url) if args.base_url else InProcessClient(root)
    try:
        report = run_contract(client)
    finally:
        if isinstance(client, InProcessClient):
            client.close()
    path = root / "reports" / "observability_runtime_contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "contract_passed": True,
                "report": str(path),
                "evaluation_passed": report["evaluation"]["passed"],
                "failed_checks": report["evaluation"]["failed_checks"],
                "release_frozen": report["evaluation"]["release_frozen"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
