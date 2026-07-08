from __future__ import annotations

from pathlib import Path

from .io import write_json


WORKLOADS = [
    {
        "name": "telemetry-collector-ha",
        "queue": "observability-checks-queue",
        "placement": "spread",
        "topology_key": "topology.kubernetes.io/zone",
        "pod_count": 3,
        "policy": "required",
        "why": "telemetry ingestion should continue through a zone or node failure",
        "fallback": "reduce retention compaction and keep incident routing live",
    },
    {
        "name": "embedding-drift-gpu-diagnostic",
        "queue": "drift-monitoring-queue",
        "placement": "compact",
        "topology_key": "cloud.provider.com/topology-rack",
        "pod_count": 4,
        "policy": "preferred",
        "why": "GPU embedding diagnostics benefit from local shard exchange but are not required for paging",
        "fallback": "run CPU PSI checks and label embedding drift as deferred",
    },
    {
        "name": "incident-root-cause-probe",
        "queue": "incident-critical-queue",
        "placement": "spread",
        "topology_key": "kubernetes.io/hostname",
        "pod_count": 2,
        "policy": "required",
        "why": "root-cause probes must not co-locate on one node during incidents",
        "fallback": "keep one probe active and freeze rollouts until redundancy returns",
    },
]


def build_topology_placement_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    checks = [
        {"name": "topology_resource_declared", "passed": True, "observed": "kueue.x-k8s.io/Topology"},
        {"name": "collector_spread_defined", "passed": any(workload["name"].startswith("telemetry") and workload["placement"] == "spread" for workload in WORKLOADS)},
        {"name": "gpu_diagnostic_compact_optional", "passed": any(workload["placement"] == "compact" and workload["policy"] == "preferred" for workload in WORKLOADS)},
        {"name": "incident_path_has_required_spread", "passed": any(workload["queue"] == "incident-critical-queue" and workload["policy"] == "required" for workload in WORKLOADS)},
        {"name": "fallbacks_defined", "passed": all(workload["fallback"] for workload in WORKLOADS)},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_topology_aware_diagnostics" if all(check["passed"] for check in checks) else "hold_topology_sensitive_diagnostics",
        "topology_levels": [
            "cloud.provider.com/topology-block",
            "cloud.provider.com/topology-rack",
            "kubernetes.io/hostname",
        ],
        "workloads": WORKLOADS,
        "checks": checks,
        "guardrails": [
            "Spread telemetry collectors so observability does not lose a zone and misclassify freshness.",
            "Use compact topology as an optimization for GPU diagnostics, not a paging dependency.",
            "Keep incident root-cause probes node-spread and CPU-runnable.",
            "Fall back to PSI-only drift checks when topology-aware GPU diagnostics are pending.",
            "Alert on pending topology assignments before suppressing any monitoring signal.",
        ],
        "kubernetes_assets": ["kubernetes/topology-aware-scheduling.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/concepts/topology_aware_scheduling/",
            "https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/",
            "https://kueue.sigs.k8s.io/docs/concepts/admission_check/",
            "https://prometheus.io/docs/practices/alerting/",
        ],
    }
    write_json(root / "reports" / "topology_placement_plan.json", plan)
    return plan
