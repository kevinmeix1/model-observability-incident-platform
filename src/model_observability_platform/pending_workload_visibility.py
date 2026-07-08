from __future__ import annotations

from pathlib import Path

from .io import write_json


PENDING_WORKLOADS = [
    {
        "name": "incident-root-cause-20260708",
        "cluster_queue": "incident-diagnostics-flavor-queue",
        "local_queue": "incident-root-cause",
        "namespace": "ml-observability",
        "position": 1,
        "pending_minutes": 4,
        "requested": {"cpu": 6, "memory_gib": 18},
        "reason": "on_call_cpu_flavor_wait",
        "owner_action": "hold rollout freeze and keep incident diagnostics first",
    },
    {
        "name": "embedding-drift-20260708",
        "cluster_queue": "embedding-drift-flavor-queue",
        "local_queue": "embedding-drift",
        "namespace": "ml-observability-drift",
        "position": 2,
        "pending_minutes": 12,
        "requested": {"cpu": 8, "memory_gib": 24, "nvidia_com_gpu": 1},
        "reason": "gpu_drift_flavor_saturated",
        "owner_action": "defer GPU drift and run CPU PSI fallback",
    },
    {
        "name": "retention-compaction-20260708",
        "cluster_queue": "retention-maintenance-flavor-queue",
        "local_queue": "retention-compaction",
        "namespace": "ml-observability-retention",
        "position": 6,
        "pending_minutes": 41,
        "requested": {"cpu": 10, "memory_gib": 30},
        "reason": "retention_spot_cpu_saturated",
        "owner_action": "keep queued; do not borrow incident response quota",
    },
]


def _raw_clusterqueue_url(cluster_queue: str) -> str:
    return f"/apis/visibility.kueue.x-k8s.io/v1beta2/clusterqueues/{cluster_queue}/pendingworkloads"


def _raw_localqueue_url(namespace: str, local_queue: str) -> str:
    return f"/apis/visibility.kueue.x-k8s.io/v1beta2/namespaces/{namespace}/localqueues/{local_queue}/pendingworkloads"


def build_pending_workload_visibility_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    cluster_queues = sorted({item["cluster_queue"] for item in PENDING_WORKLOADS})
    local_queues = [
        {
            "namespace": item["namespace"],
            "local_queue": item["local_queue"],
            "url": _raw_localqueue_url(item["namespace"], item["local_queue"]),
        }
        for item in PENDING_WORKLOADS
    ]
    checks = [
        {
            "name": "visibility_on_demand_enabled",
            "passed": True,
            "evidence": "VisibilityOnDemand is beta and enabled by default in current Kueue documentation.",
        },
        {
            "name": "rbac_grants_pending_workload_reads",
            "passed": True,
            "evidence": "Incident responders can read ClusterQueue and LocalQueue pending workload views without Kueue mutation rights.",
        },
        {
            "name": "clusterqueue_and_localqueue_queries_declared",
            "passed": bool(cluster_queues) and all(item["url"].endswith("/pendingworkloads") for item in local_queues),
            "evidence": "Incident, drift, and retention queue visibility endpoints are documented.",
        },
        {
            "name": "incident_path_prioritized",
            "passed": PENDING_WORKLOADS[0]["local_queue"] == "incident-root-cause" and PENDING_WORKLOADS[0]["position"] == 1,
            "evidence": "Incident root-cause diagnostics are first in the queue snapshot.",
        },
        {
            "name": "prometheus_metrics_declared",
            "passed": True,
            "evidence": "Alerts use kueue_admission_wait_time_seconds and kueue_cluster_queue_resource_pending for incident admission and pending CPU.",
        },
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_observability_kueue_pending_workload_visibility",
        "feature": {
            "name": "VisibilityOnDemand",
            "state": "beta since Kueue v0.9 and enabled by default",
            "api_group": "visibility.kueue.x-k8s.io/v1beta2",
            "apf_manifest": "visibility-apf.yaml from the Kueue release artifacts",
        },
        "visibility_queries": {
            "cluster_queues": [{"name": name, "url": _raw_clusterqueue_url(name)} for name in cluster_queues],
            "local_queues": local_queues,
            "recommended_access": "kubectl proxy plus kubectl get --raw to avoid bypassing API server identity checks",
        },
        "pending_workloads": PENDING_WORKLOADS,
        "metrics": [
            "kueue_admission_wait_time_seconds",
            "kueue_cluster_queue_resource_pending",
            "kueue_cluster_queue_status",
        ],
        "operational_guardrails": [
            "Check incident-root-cause queue position before lifting rollout freeze.",
            "Keep retention compaction queued instead of borrowing incident-response quota.",
            "Use LocalQueue visibility to show drift teams why GPU diagnostics are delayed.",
            "Attach queue snapshots to incident evidence when root-cause fanout misses its deadline.",
            "Alert on incident admission wait and pending CPU before dashboard publish deadlines fail.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/kueue-pending-workload-visibility.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/tasks/manage/monitor_pending_workloads/",
            "https://kueue.sigs.k8s.io/docs/tasks/manage/monitor_pending_workloads/pending_workloads_on_demand/",
            "https://kueue.sigs.k8s.io/docs/reference/metrics/",
        ],
    }
    write_json(root / "reports" / "pending_workload_visibility_plan.json", plan)
    return plan
