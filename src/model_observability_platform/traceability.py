from __future__ import annotations

import hashlib
from pathlib import Path

from .io import write_json


def _hex(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def span(trace_id: str, name: str, *, parent: str | None, service: str, duration_ms: float, attributes: dict) -> dict:
    span_id = _hex(f"{trace_id}:{name}:{service}", 16)
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent,
        "name": name,
        "service": service,
        "kind": "internal",
        "status": "ok",
        "duration_ms": duration_ms,
        "attributes": attributes,
    }


def build_trace_report(root: str | Path) -> dict:
    root = Path(root)
    trace_id = _hex("model-observability-incident-trace", 32)
    ingest = span(trace_id, "telemetry.ingest", parent=None, service="collector", duration_ms=90.0, attributes={"source": "prediction_logs"})
    drift = span(trace_id, "checks.drift", parent=ingest["span_id"], service="observability-api", duration_ms=130.0, attributes={"method": "psi"})
    slo = span(trace_id, "checks.slo", parent=ingest["span_id"], service="observability-api", duration_ms=45.0, attributes={"slo": "latency_p95"})
    incident = span(trace_id, "incident.dedupe", parent=drift["span_id"], service="incident-manager", duration_ms=18.0, attributes={"key": "fingerprint"})
    route = span(trace_id, "alert.route", parent=incident["span_id"], service="alert-router", duration_ms=9.0, attributes={"channel": "ml-reliability"})
    spans = [ingest, drift, slo, incident, route]
    report = {
        "trace_id": trace_id,
        "span_count": len(spans),
        "critical_path_ms": round(ingest["duration_ms"] + drift["duration_ms"] + incident["duration_ms"] + route["duration_ms"], 2),
        "root_service": "collector",
        "leaf_service": "alert-router",
        "spans": spans,
    }
    write_json(root / "reports" / "trace_report.json", report)
    return report
