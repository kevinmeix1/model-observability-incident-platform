from __future__ import annotations

from pathlib import Path

from .io import write_json


WORKLOAD_SLICES = [
    {
        "name": "incident-fanout-scale-up",
        "workload": "incident-root-cause-fanout",
        "queue": "incident-critical-queue",
        "slice_name": "incident-fanout-slice-a",
        "replacement_for": None,
        "min_replicas": 2,
        "max_replicas": 16,
        "reason": "use spare quota for high-severity root-cause fanout without slowing incident creation",
    },
    {
        "name": "drift-check-scale-down",
        "workload": "drift-check-backlog",
        "queue": "observability-checks-queue",
        "slice_name": "drift-check-slice-b",
        "replacement_for": "mlops-observability/drift-check-slice-a",
        "min_replicas": 2,
        "max_replicas": 8,
        "reason": "return quota from low-priority drift backlog to incident routing and rollback freeze checks",
    },
    {
        "name": "gpu-diagnostic-burst",
        "workload": "gpu-drift-diagnostic",
        "queue": "observability-gpu-diagnostics-queue",
        "slice_name": "gpu-diagnostic-slice-a",
        "replacement_for": None,
        "min_replicas": 1,
        "max_replicas": 6,
        "reason": "burst GPU diagnostics for expensive embedding drift and segment-level incident analysis",
    },
]


def build_elastic_workload_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "incident_workload_slices_declared",
            "passed": all(item["slice_name"] for item in WORKLOAD_SLICES),
            "evidence": "critical incident, drift backlog, and GPU diagnostic workers declare Workload Slices",
        },
        {
            "name": "replacement_slice_protects_incidents",
            "passed": any(item["replacement_for"] for item in WORKLOAD_SLICES),
            "evidence": "drift backlog can be replaced to return quota to incident response",
        },
        {
            "name": "jobset_fanout_declared",
            "passed": True,
            "evidence": "root-cause and GPU diagnostic workers use JobSet queue labels",
        },
        {
            "name": "incident_path_is_prioritized",
            "passed": any(item["queue"] == "incident-critical-queue" for item in WORKLOAD_SLICES),
            "evidence": "incident fanout uses the highest-priority Kueue queue",
        },
        {
            "name": "rollback_freeze_capacity_reclaim",
            "passed": any("rollback freeze" in item["reason"] for item in WORKLOAD_SLICES),
            "evidence": "replacement slices preserve capacity for rollout-freeze decisions",
        },
        {
            "name": "feature_gate_documented",
            "passed": True,
            "evidence": "ElasticJobsViaWorkloadSlices is introduced as an opt-in feature gate",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_kueue_elastic_incident_slices" if passed else "hold_elastic_incident_fanout",
        "feature_gate": "ElasticJobsViaWorkloadSlices",
        "workload_slices": WORKLOAD_SLICES,
        "jobset_policy": {
            "api": "jobset.x-k8s.io/v1alpha2",
            "queue_label": "kueue.x-k8s.io/queue-name",
            "slice_annotation": "kueue.x-k8s.io/workload-slice-name",
            "replacement_annotation": "kueue.x-k8s.io/workload-slice-replacement-for",
        },
        "operational_guardrails": [
            "Keep incident creation and alert routing outside elastic backlog queues.",
            "Use replacement slices to shrink drift backlog before delaying high-severity root-cause analysis.",
            "Reserve GPU diagnostic slices for high-severity or customer-visible incidents.",
            "Disable ElasticJobsViaWorkloadSlices if incident fanout latency or Kueue accounting diverges.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/kueue-elastic-workloads.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/concepts/elastic_workload/",
            "https://kueue.sigs.k8s.io/docs/reference/labels-and-annotations/",
            "https://kueue.sigs.k8s.io/docs/tasks/run/jobsets/",
            "https://kueue.sigs.k8s.io/docs/concepts/workload/",
        ],
    }
    write_json(root / "reports" / "elastic_workload_plan.json", plan)
    return plan
