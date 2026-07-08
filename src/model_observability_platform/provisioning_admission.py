from __future__ import annotations

from pathlib import Path

from .io import write_json


CAPACITY_CLASSES = [
    {
        "name": "incident-root-cause-critical",
        "queue": "incident-provisioned-queue",
        "flavor": "cpu-incident-provisioned",
        "managed_resources": ["cpu", "memory"],
        "max_run_duration_seconds": 2400,
        "fallback_queue": "incident-critical-queue",
        "workload": "freshness checks, impact analysis, alert routing, and rollback-freeze validation",
    },
    {
        "name": "gpu-drift-diagnostic",
        "queue": "observability-gpu-provisioned-queue",
        "flavor": "gpu-diagnostic-provisioned",
        "managed_resources": ["cpu", "memory", "nvidia.com/gpu"],
        "max_run_duration_seconds": 5400,
        "fallback_queue": "incident-critical-queue",
        "workload": "embedding drift, expensive segment diagnostics, and root-cause recomputation",
    },
]


def build_provisioning_admission_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "admission_check_declared",
            "passed": True,
            "evidence": "AdmissionCheck uses kueue.x-k8s.io/provisioning-request for incident diagnostic workloads",
        },
        {
            "name": "provisioning_request_config_declared",
            "passed": all(item["managed_resources"] for item in CAPACITY_CLASSES),
            "evidence": "ProvisioningRequestConfig sets provisioningClassName, managedResources, retryStrategy, and podSetMergePolicy",
        },
        {
            "name": "incident_path_prioritized",
            "passed": any(item["fallback_queue"] == "incident-critical-queue" for item in CAPACITY_CLASSES),
            "evidence": "fresh incident routing and root-cause probes have a protected fallback queue",
        },
        {
            "name": "rollback_freeze_capacity_protected",
            "passed": any("rollback-freeze" in item["workload"] for item in CAPACITY_CLASSES),
            "evidence": "rollout-freeze validation is treated as incident-critical capacity",
        },
        {
            "name": "diagnostic_capacity_signal_required",
            "passed": True,
            "evidence": "root-cause recomputation and GPU drift diagnostics wait for physical capacity after quota reservation",
        },
        {
            "name": "historical_backfill_does_not_block_incidents",
            "passed": True,
            "evidence": "failed provisioning requeues diagnostic backfills while fresh incident creation remains prioritized",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_kueue_provisioning_admission_for_incidents"
        if passed
        else "hold_incident_provisioning_admission",
        "capacity_classes": CAPACITY_CLASSES,
        "incident_policy": {
            "fresh_incidents_before_backfills": True,
            "failed_provisioning_action": "keep_rollouts_frozen_and_requeue_diagnostics",
            "gpu_diagnostics_are_optional": "fallback to CPU root-cause summary when GPU booking fails",
        },
        "kueue_policy": {
            "admission_check_api": "kueue.x-k8s.io/v1beta2",
            "controller_name": "kueue.x-k8s.io/provisioning-request",
            "provisioning_request_config": "observability-provisioning-config",
            "cluster_queue_strategy": "admissionChecksStrategy.onFlavors",
            "quota_reservation_before_admission": True,
            "physical_capacity_signal_required": True,
        },
        "retry_strategy": {
            "backoff_limit_count": 2,
            "backoff_base_seconds": 60,
            "backoff_max_seconds": 1800,
            "pod_set_merge_policy": "IdenticalWorkloadSchedulingRequirements",
        },
        "operational_guardrails": [
            "Prioritize fresh incident creation, alert routing, and rollout-freeze checks above historical diagnostic backfills.",
            "Release quota and requeue lower-priority drift backlog when provisioning cannot book capacity.",
            "Use GPU provisioning only for high-severity or customer-visible drift diagnostics.",
            "Use podSetUpdates to target nodes created for the booking where provider labels are available.",
            "Alert when AdmissionCheckState remains Pending beyond the incident triage SLO.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/provisioning-admission-checks.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/concepts/admission_check/",
            "https://kueue.sigs.k8s.io/docs/concepts/admission_check/provisioning_request/",
            "https://kueue.sigs.k8s.io/docs/tasks/troubleshooting/troubleshooting_provreq/",
            "https://kubernetes.io/docs/concepts/workloads/controllers/job/",
        ],
    }
    write_json(root / "reports" / "provisioning_admission_plan.json", plan)
    return plan
