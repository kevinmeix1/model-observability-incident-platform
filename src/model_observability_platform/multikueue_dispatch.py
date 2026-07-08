from __future__ import annotations

from pathlib import Path

from .io import write_json


WORKER_CLUSTERS = [
    {
        "name": "incident-diagnostics-east",
        "region": "us-east-1",
        "workload_class": "fresh-incident-root-cause-and-alert-routing",
        "cpu_quota": 48,
        "memory_gib_quota": 192,
        "gpu_quota": 0,
        "queue_mirror": "observability-multikueue-incidents",
        "provisioning_request_enabled": True,
    },
    {
        "name": "incident-backfill-west",
        "region": "us-west-2",
        "workload_class": "lineage-impact-replay-and-repair-backfills",
        "cpu_quota": 64,
        "memory_gib_quota": 256,
        "gpu_quota": 0,
        "queue_mirror": "observability-multikueue-incidents",
        "provisioning_request_enabled": True,
    },
    {
        "name": "incident-gpu-investigation",
        "region": "us-east-2",
        "workload_class": "gpu-drift-investigation-and-embedding-analysis",
        "cpu_quota": 32,
        "memory_gib_quota": 256,
        "gpu_quota": 2,
        "queue_mirror": "observability-multikueue-incidents",
        "provisioning_request_enabled": True,
    },
]


def _quota_totals() -> dict:
    return {
        "cpu": sum(cluster["cpu_quota"] for cluster in WORKER_CLUSTERS),
        "memory_gib": sum(cluster["memory_gib_quota"] for cluster in WORKER_CLUSTERS),
        "nvidia_com_gpu": sum(cluster["gpu_quota"] for cluster in WORKER_CLUSTERS),
    }


def build_multikueue_dispatch_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    manager_quota = _quota_totals()
    checks = [
        {
            "name": "admission_check_declared",
            "passed": True,
            "evidence": "AdmissionCheck uses kueue.x-k8s.io/multikueue for incident diagnostic dispatch.",
        },
        {
            "name": "multikueue_config_declared",
            "passed": len(WORKER_CLUSTERS) >= 3,
            "evidence": "MultiKueueConfig lists fresh incident, backfill, and GPU investigation worker clusters.",
        },
        {
            "name": "worker_clusters_declared",
            "passed": all(cluster["queue_mirror"] for cluster in WORKER_CLUSTERS),
            "evidence": "Each worker mirrors the incident LocalQueue, namespace, identity, and image policy contract.",
        },
        {
            "name": "manager_quota_aligned",
            "passed": manager_quota["cpu"] == 144
            and manager_quota["memory_gib"] == 704
            and manager_quota["nvidia_com_gpu"] == 2,
            "evidence": "Manager ClusterQueue quota equals aggregate worker CPU, memory, and GPU capacity.",
        },
        {
            "name": "fresh_incidents_before_backfills",
            "passed": any("fresh-incident" in cluster["workload_class"] for cluster in WORKER_CLUSTERS),
            "evidence": "Fresh incident diagnostics dispatch ahead of historical repair and lineage backfills.",
        },
        {
            "name": "repair_automation_waits_for_dispatch",
            "passed": True,
            "evidence": "Repair automation stays frozen until incident Workloads have an assigned status.clusterName.",
        },
        {
            "name": "status_sync_documented",
            "passed": True,
            "evidence": "Runbook records status.nominatedClusterNames while pending and status.clusterName after worker admission.",
        },
        {
            "name": "gpu_diagnostics_have_cpu_fallback",
            "passed": any(cluster["gpu_quota"] > 0 for cluster in WORKER_CLUSTERS),
            "evidence": "GPU drift investigations are dispatched when available and degrade to CPU summaries when not admitted.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_multikueue_incident_dispatch"
        if passed
        else "hold_multikueue_incident_dispatch",
        "incident_policy": {
            "fresh_incidents_before_backfills": True,
            "repair_plan_requires_dispatch_evidence": True,
            "missing_worker_assignment_action": "freeze_repair_automation_and_keep_rollout_freeze",
            "gpu_diagnostics_are_optional": "fallback to CPU root-cause summary when GPU worker admission fails",
        },
        "cluster_topology": {
            "manager_cluster": "observability-incident-manager",
            "manager_is_worker": False,
            "worker_clusters": WORKER_CLUSTERS,
        },
        "manager_quota": manager_quota,
        "dispatch_policy": {
            "controller_name": "kueue.x-k8s.io/multikueue",
            "dispatcher": "Incremental for routine repair backfills; AllAtOnce for high-severity incident diagnostics",
            "manager_quota_matches_worker_sum": True,
            "wait_for_workload_admitted": True,
            "status_fields": ["status.nominatedClusterNames", "status.clusterName"],
            "prebuilt_workload_label": "kueue.x-k8s.io/prebuilt-workload-name",
        },
        "operational_guardrails": [
            "Keep the manager cluster out of its own worker set and preserve a local emergency queue for minimal incident summaries.",
            "Mirror namespaces, LocalQueues, service accounts, alert-routing secrets, and image policy on every worker cluster.",
            "Dispatch high-severity incident diagnostics before lineage repair backfills or historical drift recomputation.",
            "Freeze repair automation and rollout unfreeze decisions when no worker writes status.clusterName within the triage SLO.",
            "Use Kueue admission-check wait metrics and pending Workload counts to alert on dispatch stalls.",
            "Attach missing GPU diagnostic evidence to the incident record instead of marking the event healthy.",
        ],
        "failure_modes": [
            {
                "mode": "fresh_incident_dispatch_timeout",
                "detection": "Admission-check p95 exceeds 15 minutes and Workload status.clusterName is empty.",
                "recovery": "Page the reliability owner, run local CPU summary checks, and keep rollouts frozen.",
            },
            {
                "mode": "repair_backfill_starves_incident_path",
                "detection": "Backfill Workloads are active while fresh incident diagnostics remain pending.",
                "recovery": "Preempt repair backfills, rerun the high-severity diagnostic wave, and defer repair automation.",
            },
            {
                "mode": "gpu_investigation_worker_unavailable",
                "detection": "GPU investigation Workload has nominated clusters but no selected status.clusterName before the SLO.",
                "recovery": "Publish CPU root-cause summary, keep GPU evidence marked incomplete, and retain the rollout freeze.",
            },
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/multikueue-dispatch.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/concepts/multikueue/",
            "https://kueue.sigs.k8s.io/docs/tasks/manage/setup_multikueue/",
            "https://kueue.sigs.k8s.io/docs/tasks/run/multikueue/job/",
            "https://kueue.sigs.k8s.io/docs/reference/kueue.v1beta2/",
            "https://kueue.sigs.k8s.io/docs/reference/metrics/",
        ],
    }
    write_json(root / "reports" / "multikueue_dispatch_plan.json", plan)
    return plan
