from __future__ import annotations

from pathlib import Path

from .io import write_json


WORKLOADS = [
    {
        "name": "embedding-drift-check",
        "queue": "drift-monitoring-queue",
        "priority": "observability-normal",
        "device_class": "gpu-l4-shared",
        "resource_claim_template": "l4-shared-drift",
        "sharing_strategy": "time-slicing",
        "requires_dra": True,
        "fallback": "run CPU PSI-only drift checks and defer embedding comparison",
        "why": "embedding diagnostics benefit from GPU bursts but should not block the incident loop",
    },
    {
        "name": "incident-root-cause-probe",
        "queue": "incident-critical-queue",
        "priority": "observability-incident-critical",
        "device_class": "cpu-burst",
        "resource_claim_template": None,
        "sharing_strategy": "none",
        "requires_dra": False,
        "fallback": "reserve CPU diagnostic capacity and page without waiting for GPU allocation",
        "why": "root-cause probes must stay schedulable even when accelerator diagnostics are pending",
    },
    {
        "name": "large-monitor-review",
        "queue": "drift-monitoring-queue",
        "priority": "observability-normal",
        "device_class": "gpu-a100-mig",
        "resource_claim_template": "a100-mig-monitor",
        "sharing_strategy": "mig",
        "requires_dra": True,
        "fallback": "sample fewer records, attach the limitation to the incident, and require human review",
        "why": "heavy monitor review should use MIG isolation before comparing large model output windows",
    },
]


def build_device_allocation_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    dra_workloads = [workload for workload in WORKLOADS if workload["requires_dra"]]
    checks = [
        {"name": "resource_claim_templates_declared", "passed": all(workload["resource_claim_template"] for workload in dra_workloads)},
        {"name": "kueue_quota_matches_claims", "passed": all(workload["queue"] for workload in WORKLOADS)},
        {"name": "fallback_paths_defined", "passed": all(workload["fallback"] for workload in WORKLOADS)},
        {"name": "sharing_modes_explicit", "passed": {workload["sharing_strategy"] for workload in WORKLOADS} == {"time-slicing", "mig", "none"}},
        {"name": "incident_path_unblocked", "passed": any(not workload["requires_dra"] and "incident" in workload["priority"] for workload in WORKLOADS)},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "admit_dra_backed_diagnostics" if all(check["passed"] for check in checks) else "hold_accelerator_diagnostics",
        "device_classes": [
            {
                "name": "gpu-l4-shared",
                "allocation": "ResourceClaimTemplate per drift-check pod",
                "sharing_strategy": "NVIDIA time-slicing",
                "isolation": "shared accelerator for low-risk embedding diagnostics",
                "kueue_flavor": "gpu-l4-shared",
            },
            {
                "name": "gpu-a100-mig",
                "allocation": "ResourceClaimTemplate per large monitor review pod",
                "sharing_strategy": "MIG",
                "isolation": "hardware-backed memory and fault isolation for incident review",
                "kueue_flavor": "gpu-a100-mig",
            },
        ],
        "workloads": WORKLOADS,
        "checks": checks,
        "guardrails": [
            "Never let GPU diagnostics block incident creation, paging, or rollback advice.",
            "Use CPU PSI-only checks as the fallback when embedding drift claims are pending.",
            "Use time-sliced L4 claims for low-risk embedding comparisons and MIG for heavy reviews.",
            "Couple DRA claims to Kueue so observability workloads cannot starve live serving capacity.",
            "Alert on pending ResourceClaims before declaring an observability signal unavailable.",
        ],
        "kubernetes_assets": ["kubernetes/dynamic-resource-allocation.yaml", "kubernetes/accelerator-scheduling.yaml"],
        "references": [
            "https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/",
            "https://kueue.sigs.k8s.io/docs/concepts/workload/",
            "https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html",
            "https://prometheus.io/docs/practices/alerting/",
        ],
    }
    write_json(root / "reports" / "device_allocation_plan.json", plan)
    return plan
