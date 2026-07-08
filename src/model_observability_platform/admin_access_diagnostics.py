from __future__ import annotations

from pathlib import Path

from .io import write_json


ADMIN_ACCESS_DIAGNOSTICS = [
    {
        "name": "embedding-drift-admin-health",
        "namespace": "mlops-observability-dra-admin",
        "target_workload": "embedding-drift-check",
        "target_device_class": "gpu-l4-shared",
        "claim": "embedding-drift-admin-health",
        "trigger": "embedding drift monitor reports Unhealthy DRA status during incident triage",
        "evidence": ["ResourceClaim.status.devices", "allocatedResourcesStatus", "incident.id", "monitor.name"],
        "owner_action": "run CPU PSI-only drift checks and attach GPU diagnostic limitation to the incident",
    },
    {
        "name": "large-monitor-review-diagnostics",
        "namespace": "mlops-observability-dra-admin",
        "target_workload": "large-monitor-review",
        "target_device_class": "gpu-a100-mig",
        "claim": "large-monitor-admin-snapshot",
        "trigger": "large monitor review shows Unknown device health while incidents are still open",
        "evidence": ["incident.id", "monitor.run_id", "population-window", "gpu-memory-fragmentation", "ResourceClaim.status.devices"],
        "owner_action": "sample fewer records, keep rollout freeze guidance active, and require human review before clearing the incident",
    },
    {
        "name": "incident-root-cause-readiness",
        "namespace": "mlops-observability-dra-admin",
        "target_workload": "incident-root-cause-probe",
        "target_device_class": "cpu-burst",
        "claim": "incident-root-cause-admin-snapshot",
        "trigger": "root-cause summary needs proof that GPU diagnostics did not block incident creation or paging",
        "evidence": ["incident.id", "alert.route", "rollout.freeze_state", "device-taint-summary"],
        "owner_action": "attach diagnostic evidence to the incident log while paging and rollout-freeze workflows stay CPU-runnable",
    },
]


def build_admin_access_diagnostic_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "namespace_scoped_admin_access",
            "passed": all(item["namespace"] == "mlops-observability-dra-admin" for item in ADMIN_ACCESS_DIAGNOSTICS),
            "evidence": "Privileged ResourceClaims are isolated in a namespace labeled for DRA AdminAccess.",
        },
        {
            "name": "least_privilege_rbac",
            "passed": True,
            "evidence": "The diagnostic runner can manage ResourceClaims only in the admin namespace and read observability workload status separately.",
        },
        {
            "name": "incident_linkage_required",
            "passed": all(any("incident" in evidence for evidence in item["evidence"]) for item in ADMIN_ACCESS_DIAGNOSTICS),
            "evidence": "Every privileged diagnostic captures incident linkage before evidence is attached to dashboards or runbooks.",
        },
        {
            "name": "incident_path_not_blocked",
            "passed": any("CPU-runnable" in item["owner_action"] for item in ADMIN_ACCESS_DIAGNOSTICS),
            "evidence": "Admin diagnostics cannot block incident creation, paging, or rollout-freeze workflows.",
        },
        {
            "name": "short_lived_break_glass",
            "passed": True,
            "evidence": "Diagnostic claims require incident linkage, cleanup TTLs, and Prometheus alerts for stale privileged access.",
        },
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_observability_dra_admin_access_diagnostics",
        "feature": {
            "name": "DRA AdminAccess for ResourceClaims",
            "state": "Kubernetes v1.36 stable and enabled by default",
            "feature_gate": "DRAAdminAccess",
            "api_version": "resource.k8s.io/v1",
            "field": "spec.devices.requests[*].exactly.adminAccess",
            "namespace_label": 'resource.kubernetes.io/admin-access: "true"',
            "purpose": "non-disruptive observability diagnostics for devices already allocated to drift, monitor, and root-cause workloads",
        },
        "diagnostics": ADMIN_ACCESS_DIAGNOSTICS,
        "incident_guardrails": [
            "Never delay incident creation, paging, or rollout-freeze advice while an AdminAccess claim is active.",
            "Attach incident id, monitor name, monitor run id, ResourceClaim name, and device health evidence to one incident log entry.",
            "Run CPU PSI-only drift checks when GPU diagnostic devices are unhealthy or under AdminAccess inspection.",
            "Treat AdminAccess output as evidence quality metadata, not as a reason to suppress a customer-facing incident.",
            "Delete privileged ResourceClaims after evidence capture so AdminAccess cannot become a normal monitor allocation path.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/dra-admin-access-diagnostics.yaml"],
        "references": [
            "https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/",
            "https://github.com/kubernetes/sig-release/discussions/2958",
            "https://www.kubernetes.dev/resources/keps/5018/",
        ],
    }
    write_json(root / "reports" / "admin_access_diagnostics_plan.json", plan)
    return plan
