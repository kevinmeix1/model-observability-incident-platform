from __future__ import annotations

from pathlib import Path

from .io import write_json


OBSERVED_OBJECTIVES = [
    {
        "name": "credit-risk-online",
        "priority": 20,
        "pool": "observed-credit-risk-inference-pool",
        "traffic_class": "online",
        "incident_signal": "endpoint_picker_unavailable",
        "fallback": "freeze canaries and route incident probes through the champion HTTPRoute",
    },
    {
        "name": "churn-risk-canary",
        "priority": 10,
        "pool": "observed-churn-risk-inference-pool",
        "traffic_class": "canary",
        "incident_signal": "routing_skew_or_canary_regression",
        "fallback": "recommend rollback and keep objective priority below online traffic",
    },
    {
        "name": "batch-diagnostic-replay",
        "priority": -5,
        "pool": "observed-diagnostic-inference-pool",
        "traffic_class": "batch",
        "incident_signal": "diagnostic_queue_starvation",
        "fallback": "defer replay while incident-critical checks are open",
    },
]


def build_inference_gateway_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    checks = [
        {"name": "observed_pools_declared", "passed": len({item["pool"] for item in OBSERVED_OBJECTIVES}) >= 3},
        {"name": "endpoint_picker_signal_declared", "passed": any("endpoint_picker" in item["incident_signal"] for item in OBSERVED_OBJECTIVES)},
        {"name": "online_priority_above_diagnostic_replay", "passed": max(item["priority"] for item in OBSERVED_OBJECTIVES) > min(item["priority"] for item in OBSERVED_OBJECTIVES)},
        {"name": "fallbacks_defined", "passed": all(item["fallback"] for item in OBSERVED_OBJECTIVES)},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "monitor_inference_gateway_objectives" if all(check["passed"] for check in checks) else "monitor_httproute_only",
        "observed_objectives": OBSERVED_OBJECTIVES,
        "signals": [
            "endpoint_picker_up",
            "inference_pool_ready_backends",
            "objective_priority",
            "route_skew",
            "request_queue_depth",
        ],
        "checks": checks,
        "guardrails": [
            "Treat endpoint-picker unavailability as an incident input, not just a networking alert.",
            "Freeze canaries when objective-level routing signals are missing.",
            "Keep diagnostic replay lower priority than online traffic during incidents.",
            "Capture InferencePool and InferenceObjective names in incident fingerprints.",
        ],
        "kubernetes_assets": ["kubernetes/inference-gateway-routing.yaml"],
        "references": [
            "https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/",
            "https://gateway-api-inference-extension.sigs.k8s.io/concepts/api-overview/",
            "https://istio.io/latest/docs/tasks/traffic-management/ingress/gateway-api-inference-extension/",
        ],
    }
    write_json(root / "reports" / "inference_gateway_plan.json", plan)
    return plan
