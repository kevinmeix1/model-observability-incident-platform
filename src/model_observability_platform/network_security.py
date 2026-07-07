from __future__ import annotations

from pathlib import Path

from .io import write_json


ALLOWED_FLOWS = [
    {
        "source": "model-serving-runtime",
        "destination": "telemetry-collector",
        "port": 4317,
        "protocol": "OTLP gRPC over mesh mTLS",
        "justification": "send prediction traces and metrics",
    },
    {
        "source": "telemetry-collector",
        "destination": "drift-evaluator",
        "port": 8080,
        "protocol": "HTTP over mesh mTLS",
        "justification": "trigger drift and freshness checks from new telemetry windows",
    },
    {
        "source": "incident-router",
        "destination": "alert-webhook",
        "port": 443,
        "protocol": "HTTPS over mesh mTLS",
        "justification": "send alert-ready incident notifications",
    },
]


DENIED_FLOWS = [
    {
        "source": "drift-evaluator",
        "destination": "incident-router-admin",
        "reason": "analysis jobs cannot mutate incident routing policy",
    },
    {
        "source": "telemetry-collector",
        "destination": "model-registry",
        "reason": "telemetry collectors should not read or mutate model registry state",
    },
]


def build_network_security_report(root: str | Path) -> dict:
    root = Path(root)
    report = {
        "platform": "model-observability-incident-platform",
        "namespace": "ml-observability",
        "default_policy": "deny all ingress and egress, then allow telemetry, evaluator, and incident flows",
        "mtls_mode": "STRICT",
        "gateway_boundary": "observability namespace exposes only alert webhook egress, not public ingress",
        "allowed_flow_count": len(ALLOWED_FLOWS),
        "denied_flow_count": len(DENIED_FLOWS),
        "allowed_flows": ALLOWED_FLOWS,
        "denied_by_default": DENIED_FLOWS,
        "controls": [
            "default deny NetworkPolicy for observability namespace",
            "DNS egress allow for service discovery",
            "collector ingress is limited to serving runtime telemetry",
            "AuthorizationPolicy reserves incident routing to the incident service account",
        ],
    }
    write_json(root / "reports" / "network_security.json", report)
    return report
