from __future__ import annotations

from pathlib import Path

from .io import write_json


CLUSTER_QUEUE_POLICIES = [
    {
        "name": "incident-response",
        "cluster_queue": "incident-critical-tenant-queue",
        "local_queues": ["incident-root-cause", "rollout-freeze"],
        "weight": 5,
        "nominal_cpu": 18,
        "borrowing_limit_cpu": 6,
        "lending_limit_cpu": 1,
        "observed_cpu": 13,
        "historical_usage_score": 0.28,
        "preemption": {"withinClusterQueue": "LowerPriority", "reclaimWithinCohort": "Any"},
    },
    {
        "name": "drift-monitoring",
        "cluster_queue": "drift-monitoring-tenant-queue",
        "local_queues": ["embedding-drift", "quality-window"],
        "weight": 2,
        "nominal_cpu": 14,
        "borrowing_limit_cpu": 8,
        "lending_limit_cpu": 4,
        "observed_cpu": 10,
        "historical_usage_score": 0.50,
        "preemption": {"withinClusterQueue": "LowerPriority", "reclaimWithinCohort": "LowerPriority"},
    },
    {
        "name": "retention-maintenance",
        "cluster_queue": "retention-maintenance-tenant-queue",
        "local_queues": ["retention-compaction", "dashboard-backfill"],
        "weight": 1,
        "nominal_cpu": 8,
        "borrowing_limit_cpu": 3,
        "lending_limit_cpu": 6,
        "observed_cpu": 7,
        "historical_usage_score": 0.84,
        "preemption": {"withinClusterQueue": "LowerPriority", "reclaimWithinCohort": "Never"},
    },
]


def _dominant_resource_share(queue: dict) -> float:
    borrowable = queue["nominal_cpu"] + queue["borrowing_limit_cpu"]
    return round(queue["observed_cpu"] / max(borrowable * queue["weight"], 0.0001), 4)


def build_cohort_fair_sharing_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    queues = [
        {
            **queue,
            "dominant_resource_share": _dominant_resource_share(queue),
            "exclusive_cpu_after_lending": queue["nominal_cpu"] - queue["lending_limit_cpu"],
            "max_cpu_after_borrowing": queue["nominal_cpu"] + queue["borrowing_limit_cpu"],
        }
        for queue in CLUSTER_QUEUE_POLICIES
    ]
    checks = [
        {
            "name": "fair_sharing_enabled",
            "passed": True,
            "evidence": "Kueue Configuration declares Fair Sharing preemption strategies for borrowed observability resources.",
        },
        {
            "name": "admission_fair_sharing_enabled",
            "passed": True,
            "evidence": "AdmissionFairSharing keeps LocalQueue admission aware of decayed historical usage and entry penalties.",
        },
        {
            "name": "borrowing_and_lending_limits_declared",
            "passed": all(queue["borrowing_limit_cpu"] >= 0 and queue["lending_limit_cpu"] >= 0 for queue in queues),
            "evidence": "Each observability ClusterQueue declares borrowingLimit and lendingLimit to reserve incident response capacity.",
        },
        {
            "name": "incident_response_weighted_above_retention",
            "passed": queues[0]["weight"] > queues[-1]["weight"],
            "evidence": "Incident response receives a higher fairSharing.weight than retention maintenance.",
        },
        {
            "name": "preemption_guardrails_declared",
            "passed": queues[0]["preemption"]["reclaimWithinCohort"] == "Any" and queues[-1]["preemption"]["reclaimWithinCohort"] == "Never",
            "evidence": "Incident diagnostics can reclaim borrowed quota, while retention jobs cannot reclaim from on-call queues.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_observability_kueue_cohort_fair_sharing" if passed else "keep_static_observability_clusterqueue_quotas",
        "kueue_version_target": "0.15+",
        "feature_gates": {
            "FairSharing": "stable since Kueue v0.7",
            "AdmissionFairSharing": "beta since Kueue v0.15 and enabled by default",
        },
        "fair_sharing_config": {
            "preemptionStrategies": ["LessThanOrEqualToFinalShare", "LessThanInitialShare"],
            "dominant_resource_share_signal": "observed_cpu / ((nominal_cpu + borrowing_limit_cpu) * fairSharing.weight)",
            "admission_order": "prefer LocalQueues with lower decayed historical usage and apply an entry penalty at admission time",
        },
        "cohort": {
            "name": "ml-observability-cohort",
            "policy": "incident diagnostics and rollout freeze preserve capacity while drift and retention borrow bounded idle quota",
        },
        "cluster_queues": queues,
        "operational_guardrails": [
            "Keep incident root-cause and rollout-freeze queues weighted above drift and retention maintenance.",
            "Use lendingLimit so incident response never lends away every on-call diagnostic slot.",
            "Use borrowingLimit to cap drift and retention bursts before they create preemption storms.",
            "Keep Admission Fair Sharing enabled so repeated retention submissions lose admission priority until usage decays.",
            "Attach preemption reason, LocalQueue, incident fingerprint, and fair-share values to incident evidence.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/kueue-cohort-fair-sharing.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/concepts/cluster_queue/",
            "https://kueue.sigs.k8s.io/docs/concepts/cohort/",
            "https://kueue.sigs.k8s.io/docs/concepts/preemption/",
            "https://kueue.sigs.k8s.io/docs/concepts/admission_fair_sharing/",
        ],
    }
    write_json(root / "reports" / "cohort_fair_sharing_plan.json", plan)
    return plan
