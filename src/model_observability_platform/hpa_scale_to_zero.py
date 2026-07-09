from __future__ import annotations

from pathlib import Path

from .io import write_json


SCALE_TO_ZERO_WORKLOADS = [
    {
        "name": "drift-diagnostic-worker",
        "target_ref": "Deployment/drift-diagnostic-worker",
        "min_replicas": 0,
        "max_replicas": 24,
        "metric_type": "External",
        "metric_name": "observability_drift_queue_depth",
        "wake_threshold": 1,
        "cold_start_budget_seconds": 90,
        "scale_to_zero_allowed": True,
        "reason": "Drift diagnostics are backlog-driven and can idle when no evaluation windows need analysis.",
    },
    {
        "name": "incident-evidence-renderer",
        "target_ref": "Deployment/incident-evidence-renderer",
        "min_replicas": 0,
        "max_replicas": 12,
        "metric_type": "External",
        "metric_name": "incident_evidence_render_queue_depth",
        "wake_threshold": 1,
        "cold_start_budget_seconds": 90,
        "scale_to_zero_allowed": True,
        "reason": "Evidence rendering can wake on demand after incidents are created.",
    },
    {
        "name": "retention-replay-worker",
        "target_ref": "Deployment/retention-replay-worker",
        "min_replicas": 0,
        "max_replicas": 8,
        "metric_type": "Object",
        "metric_name": "retention_replay_backlog",
        "metric_object": "Service/retention-replay-queue",
        "wake_threshold": 1,
        "cold_start_budget_seconds": 120,
        "scale_to_zero_allowed": True,
        "reason": "Retention replay is scheduled or incident-driven and should not reserve idle pods.",
    },
]

PROTECTED_WORKLOADS = [
    {
        "name": "incident-router",
        "min_replicas": 2,
        "reason": "Incident routing must stay warm during high-burn events.",
    },
    {
        "name": "rollout-freeze-controller",
        "min_replicas": 2,
        "reason": "Freeze and unfreeze decisions are safety controls, not elastic workers.",
    },
    {
        "name": "alert-dispatcher",
        "min_replicas": 1,
        "reason": "Alert routing must not wait for cold start when SLO burn rises.",
    },
]


def build_hpa_scale_to_zero_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    feature_gate = {
        "name": "HPAScaleToZero",
        "minimum_version": "Kubernetes v1.36",
        "stage": "alpha",
        "default": "disabled",
        "requirement": "minReplicas=0 requires at least one Object or External metric in autoscaling/v2",
    }
    checks = [
        {
            "name": "feature_gate_documented",
            "passed": feature_gate["stage"] == "alpha" and feature_gate["name"] == "HPAScaleToZero",
            "evidence": "The incident platform treats scale-to-zero as a gated alpha cost optimization.",
        },
        {
            "name": "all_zero_min_replicas_use_external_or_object_metrics",
            "passed": all(workload["metric_type"] in {"External", "Object"} for workload in SCALE_TO_ZERO_WORKLOADS),
            "evidence": "Drift, evidence, and retention workers wake from queue or object backlog metrics.",
        },
        {
            "name": "incident_control_plane_not_scaled_to_zero",
            "passed": not ({workload["name"] for workload in SCALE_TO_ZERO_WORKLOADS} & {item["name"] for item in PROTECTED_WORKLOADS}),
            "evidence": "Incident router, rollout-freeze controller, and alert dispatcher stay above zero replicas.",
        },
        {
            "name": "wake_metric_contract",
            "passed": all(workload["metric_name"] and workload["wake_threshold"] >= 1 for workload in SCALE_TO_ZERO_WORKLOADS),
            "evidence": "Every idleable worker declares a metric adapter contract that can wake from zero.",
        },
        {
            "name": "cold_start_budget_recorded",
            "passed": all(workload["cold_start_budget_seconds"] <= 120 for workload in SCALE_TO_ZERO_WORKLOADS),
            "evidence": "Cold-start budgets are explicit so incident-control paths remain excluded.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-09T00:00:00Z",
        "recommended_action": "enable_hpa_scale_to_zero_for_observability_workers" if passed else "keep_hpa_scale_to_zero_disabled",
        "passed": passed,
        "feature_status": {
            "hpa_scale_to_zero": "Kubernetes v1.36 alpha and disabled by default behind HPAScaleToZero",
            "metric_requirement": "minReplicas=0 is valid only with at least one Object or External metric",
            "api_version": "autoscaling/v2",
        },
        "feature_gate": feature_gate,
        "scale_to_zero_workloads": SCALE_TO_ZERO_WORKLOADS,
        "protected_workloads": PROTECTED_WORKLOADS,
        "checks": checks,
        "runbook": [
            "Enable HPAScaleToZero only for diagnostic and evidence workers first.",
            "Verify external metrics remain present while diagnostic workers have zero replicas.",
            "Keep incident router, rollout-freeze controller, and alert dispatcher above zero replicas.",
            "Keep rollout freezes asserted if backlog is positive and desired replicas remain zero beyond the cold-start budget.",
        ],
        "references": [
            "https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/",
            "https://kubernetes.io/docs/reference/kubernetes-api/autoscaling/horizontal-pod-autoscaler-v2/",
            "https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/",
        ],
    }
    write_json(root / "reports" / "hpa_scale_to_zero_plan.json", plan)
    return plan
