from __future__ import annotations

from pathlib import Path

from .io import write_json


RAY_WORKLOADS = [
    {
        "name": "incident-root-cause-fanout",
        "kind": "RayJob",
        "queue": "observability-checks-queue",
        "priority": "incident-critical",
        "min_workers": 2,
        "max_workers": 12,
        "gpus_per_worker": 0,
        "autoscaling": "elastic",
        "scheduling": "kueue_admitted_rayjob",
        "why": "fan out checks across impacted models, datasets, and serving routes during an incident",
        "fallback": "run the highest-severity checks serially and keep rollouts frozen",
    },
    {
        "name": "embedding-drift-diagnostic",
        "kind": "RayJob",
        "queue": "observability-gpu-queue",
        "priority": "diagnostic-standard",
        "min_workers": 0,
        "max_workers": 6,
        "gpus_per_worker": 1,
        "autoscaling": "elastic",
        "scheduling": "preemptible_gpu_queue",
        "why": "compute embedding drift and nearest-neighbor error clusters when GPUs are available",
        "fallback": "use tabular PSI and prediction-distribution drift only",
    },
    {
        "name": "retention-backfill-audit",
        "kind": "RayCluster",
        "queue": "observability-retention-queue",
        "priority": "opportunistic",
        "min_workers": 1,
        "max_workers": 8,
        "gpus_per_worker": 0,
        "autoscaling": "elastic",
        "scheduling": "workload_slices",
        "why": "parallelize historical log compaction and lineage enrichment outside the hot incident path",
        "fallback": "defer retention audit until the incident queue drains",
    },
]


def build_kuberay_capacity_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    checks = [
        {"name": "incident_fanout_declared", "passed": any(workload["priority"] == "incident-critical" for workload in RAY_WORKLOADS)},
        {"name": "gpu_diagnostic_optional", "passed": any(workload["gpus_per_worker"] > 0 and workload["priority"] != "incident-critical" for workload in RAY_WORKLOADS)},
        {"name": "retention_is_opportunistic", "passed": any(workload["name"] == "retention-backfill-audit" and workload["priority"] == "opportunistic" for workload in RAY_WORKLOADS)},
        {"name": "kueue_queue_labels_required", "passed": all(workload["queue"] for workload in RAY_WORKLOADS)},
        {"name": "fallbacks_defined", "passed": all(workload["fallback"] for workload in RAY_WORKLOADS)},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_kuberay_incident_fanout" if all(check["passed"] for check in checks) else "keep_incident_checks_serial",
        "workloads": RAY_WORKLOADS,
        "capacity": {
            "max_workers": sum(workload["max_workers"] for workload in RAY_WORKLOADS),
            "max_gpu_demand": sum(workload["max_workers"] * workload["gpus_per_worker"] for workload in RAY_WORKLOADS),
            "incident_reserved_workers": 4,
            "autoscaler_idle_timeout_seconds": 60,
        },
        "checks": checks,
        "guardrails": [
            "Incident-critical RayJobs can preempt retention audits, not serving rollback checks.",
            "GPU embedding drift diagnostics are optional and never block incident creation.",
            "Keep high-cardinality telemetry fanout outside the Airflow scheduler process.",
            "Freeze rollouts when Ray incident fanout is unavailable and severity is high.",
            "Publish Ray worker pending, queue wait, and diagnostic completion metrics into incident records.",
        ],
        "kubernetes_assets": ["kubernetes/kuberay-kueue-workloads.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/tasks/run/rayjobs/",
            "https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/kueue.html",
            "https://docs.ray.io/en/latest/cluster/kubernetes/examples/rayjob-kueue-gang-scheduling.html",
        ],
    }
    write_json(root / "reports" / "kuberay_capacity_plan.json", plan)
    return plan
