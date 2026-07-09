from __future__ import annotations

from pathlib import Path

from .io import write_json


RESOURCE_MUTATIONS = [
    {
        "name": "incident-root-cause-job",
        "suspended": True,
        "current_requests": {"cpu": "6", "memory": "12Gi"},
        "proposed_requests": {"cpu": "4", "memory": "10Gi"},
        "quota_reason": "Root-cause diagnostics can shrink CPU after incident scope and impacted assets are known.",
        "unsuspend_gate": "incident_priority_quota_fit_and_evidence_bundle_ready",
    },
    {
        "name": "drift-diagnostic-job",
        "suspended": True,
        "current_requests": {"cpu": "8", "memory": "24Gi", "nvidia.com/gpu": "1"},
        "proposed_requests": {"cpu": "5", "memory": "16Gi", "nvidia.com/gpu": "1"},
        "quota_reason": "Deep drift diagnostics fit GPU quota after the alert batch and reference window are selected.",
        "unsuspend_gate": "quota_fit_and_drift_window_manifest_ready",
    },
    {
        "name": "retention-replay-job",
        "suspended": True,
        "current_requests": {"cpu": "4", "memory": "8Gi"},
        "proposed_requests": {"cpu": "2", "memory": "6Gi"},
        "quota_reason": "Retention replay only needs the incident window, not the full observability retention sweep.",
        "unsuspend_gate": "pool_slots_available_and_replay_checkpoint_present",
    },
]

PROTECTED_JOBS = [
    {
        "name": "active-incident-router-smoke",
        "suspended": False,
        "reason": "Incident routing smoke checks should remain stable; resize with in-place Pod resize or replacement Jobs instead.",
    },
    {
        "name": "running-rollout-freeze-validation",
        "suspended": False,
        "reason": "Rollout-freeze validation must not have its Job template rewritten while Pods are active.",
    },
]


def _resource_delta_ok(item: dict) -> bool:
    current_cpu = float(item["current_requests"]["cpu"])
    proposed_cpu = float(item["proposed_requests"]["cpu"])
    return 0.25 <= proposed_cpu / current_cpu <= 1.5


def build_suspended_job_resource_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    feature = {
        "name": "MutablePodResourcesForSuspendedJobs",
        "state": "Kubernetes v1.36 beta and enabled by default",
        "scope": "resource requests and limits in the Pod template of suspended Jobs",
        "not_for": "actively running Pods; use in-place resize or recreate instead",
    }
    checks = [
        {
            "name": "beta_feature_status_recorded",
            "passed": feature["state"].startswith("Kubernetes v1.36 beta"),
            "evidence": "The plan records the beta feature status before using it for incident diagnostics.",
        },
        {
            "name": "only_suspended_jobs_mutated",
            "passed": all(item["suspended"] for item in RESOURCE_MUTATIONS),
            "evidence": "Every mutable diagnostic Job starts from spec.suspend=true.",
        },
        {
            "name": "active_jobs_not_resized",
            "passed": all(not item["suspended"] for item in PROTECTED_JOBS),
            "evidence": "Active incident routing and rollout-freeze Jobs are explicitly excluded.",
        },
        {
            "name": "incident_evidence_required",
            "passed": all(item["quota_reason"] and item["unsuspend_gate"] for item in RESOURCE_MUTATIONS),
            "evidence": "Each patch is tied to quota, evidence bundle, drift window, pool, or checkpoint readiness.",
        },
        {
            "name": "resource_delta_bounded",
            "passed": all(_resource_delta_ok(item) for item in RESOURCE_MUTATIONS),
            "evidence": "CPU changes are bounded so the queue controller cannot hide a major workload-shape rewrite.",
        },
        {
            "name": "unsuspend_gate_requires_operational_fit",
            "passed": all(
                "quota" in item["unsuspend_gate"]
                or "pool" in item["unsuspend_gate"]
                or "evidence" in item["unsuspend_gate"]
                for item in RESOURCE_MUTATIONS
            ),
            "evidence": "Unsuspend gates require quota, Airflow pool, evidence bundle, drift manifest, or checkpoint readiness.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-09T00:00:00Z",
        "recommended_action": "enable_suspended_job_resource_mutation_for_incident_diagnostics" if passed else "keep_suspended_job_resources_observe_only",
        "passed": passed,
        "feature": feature,
        "resource_mutations": RESOURCE_MUTATIONS,
        "protected_jobs": PROTECTED_JOBS,
        "checks": checks,
        "runbook": [
            "Create incident diagnostic Jobs with spec.suspend=true when queue admission owns the start decision.",
            "Patch CPU, memory, GPU, or extended resource requests only while the Job is suspended.",
            "Record incident priority, evidence bundle digest, Kueue quota fit, and Airflow pool fit before unsuspending.",
            "Use in-place resize or a replacement Job for active incident routers and rollout-freeze validation.",
        ],
        "references": [
            "https://kubernetes.io/blog/2026/04/27/kubernetes-v1-36-mutable-pod-resources-for-suspended-jobs/",
            "https://kubernetes.io/docs/concepts/workloads/controllers/job/",
        ],
    }
    write_json(root / "reports" / "suspended_job_resources_plan.json", plan)
    return plan
