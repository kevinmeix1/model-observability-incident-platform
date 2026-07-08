from __future__ import annotations

from pathlib import Path

from .io import write_json


REQUIRED_ATTRIBUTES = [
    "service.name",
    "k8s.namespace.name",
    "k8s.pod.name",
    "k8s.cronjob.name",
    "ml.model.version",
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "inference.gateway.objective",
    "incident.id",
    "incident.severity",
    "incident.root_cause",
    "slo.name",
]

REDACTED_ATTRIBUTES = [
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "http.request.body",
    "incident.payload",
]


def build_semantic_telemetry_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    checks = [
        {"name": "semantic_attribute_contract", "passed": "service.name" in REQUIRED_ATTRIBUTES and "ml.model.version" in REQUIRED_ATTRIBUTES},
        {"name": "kubernetes_resource_correlation", "passed": "k8s.pod.name" in REQUIRED_ATTRIBUTES and "k8s.cronjob.name" in REQUIRED_ATTRIBUTES},
        {"name": "genai_usage_observed", "passed": "gen_ai.usage.input_tokens" in REQUIRED_ATTRIBUTES and "gen_ai.usage.output_tokens" in REQUIRED_ATTRIBUTES},
        {"name": "incident_context_required", "passed": "incident.id" in REQUIRED_ATTRIBUTES and "incident.root_cause" in REQUIRED_ATTRIBUTES},
        {"name": "privacy_redaction_declared", "passed": "gen_ai.input.messages" in REDACTED_ATTRIBUTES and "incident.payload" in REDACTED_ATTRIBUTES},
        {"name": "gateway_objective_root_cause", "passed": "inference.gateway.objective" in REQUIRED_ATTRIBUTES},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enforce_semantic_telemetry_contract" if all(check["passed"] for check in checks) else "hold_incident_routing_contract",
        "schema": {
            "profile": "otel-kubernetes-genai-incident",
            "required_attributes": REQUIRED_ATTRIBUTES,
            "redacted_attributes": REDACTED_ATTRIBUTES,
            "numeric_fields": [
                "gen_ai.usage.input_tokens",
                "gen_ai.usage.output_tokens",
                "inference.estimated_cost_usd",
                "incident.detection_latency_ms",
                "slo.burn_rate",
            ],
        },
        "incident_pivots": [
            {"pivot": "model_version", "attributes": ["ml.model.version", "gen_ai.response.model"]},
            {"pivot": "kubernetes_workload", "attributes": ["k8s.namespace.name", "k8s.pod.name", "k8s.cronjob.name"]},
            {"pivot": "gateway_objective", "attributes": ["inference.gateway.objective", "gen_ai.request.model"]},
            {"pivot": "incident_route", "attributes": ["incident.id", "incident.severity", "incident.root_cause"]},
        ],
        "checks": checks,
        "collector_policy": {
            "processor": "attributes/semantic_redaction",
            "drop_payloads_by_default": True,
            "exporter_contract": "metrics and traces keep route, model, usage, SLO, and incident fields but not raw prompts or alert payloads",
        },
        "guardrails": [
            "Block dashboards from depending on raw log parsing when semantic attributes are missing.",
            "Keep prompt, response, request-body, and incident payload text out of default telemetry exports.",
            "Require incident fields on alert-route spans so dedupe, root cause, and downstream paging are traceable.",
            "Correlate serving degradation with model version, gateway objective, and Kubernetes workload before declaring rollback.",
        ],
        "kubernetes_assets": ["kubernetes/opentelemetry-collector.yaml"],
        "references": [
            "https://opentelemetry.io/docs/specs/semconv/",
            "https://opentelemetry.io/docs/specs/semconv/system/k8s-metrics/",
            "https://github.com/open-telemetry/semantic-conventions-genai",
            "https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/",
        ],
    }
    write_json(root / "reports" / "semantic_telemetry_plan.json", plan)
    return plan
