from __future__ import annotations

from pathlib import Path

from .io import write_json


DEVICE_SHARING_POLICIES = [
    {
        "name": "embedding-drift-prioritized-accelerator",
        "workload": "embedding-drift-check",
        "primary": "gpu-l4-shared",
        "alternatives": ["gpu-a100-mig", "cpu-psi-only"],
        "feature": "DRAPrioritizedList",
        "owner_action": "try shared L4 first, fall back to MIG review, then annotate the incident with CPU-only drift evidence",
    },
    {
        "name": "drift-backlog-consumable-capacity",
        "workload": "drift-backlog-review",
        "primary": "partitionable-a100",
        "alternatives": ["3GiB-vgpu-slice", "defer-heavy-review"],
        "feature": "DRAConsumableCapacity",
        "owner_action": "bound GPU memory for backlog review so incident-critical CPU probes stay schedulable",
    },
    {
        "name": "large-monitor-review-binding-readiness",
        "workload": "large-monitor-review",
        "primary": "fabric-attached-a100",
        "alternatives": ["sampled-cpu-review", "human-review-required"],
        "feature": "DRADeviceBindingConditions",
        "owner_action": "wait for diagnostic accelerator preparation before trusting heavy monitor evidence",
    },
]


def build_advanced_device_sharing_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {"name": "prioritized_device_alternatives_defined", "passed": all(policy["alternatives"] for policy in DEVICE_SHARING_POLICIES), "evidence": "Diagnostic workloads declare ordered accelerator fallbacks."},
        {"name": "partitionable_device_policy_defined", "passed": any("partitionable" in policy["primary"] for policy in DEVICE_SHARING_POLICIES), "evidence": "Drift backlog review can consume logical accelerator slices instead of whole devices."},
        {"name": "consumable_capacity_budgeted", "passed": any(policy["feature"] == "DRAConsumableCapacity" for policy in DEVICE_SHARING_POLICIES), "evidence": "Backlog diagnostics use bounded GPU memory so incident-critical paths remain live."},
        {"name": "device_binding_conditions_required", "passed": any(policy["feature"] == "DRADeviceBindingConditions" for policy in DEVICE_SHARING_POLICIES), "evidence": "Heavy monitor review waits for prepared devices before trusting diagnostic evidence."},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_observability_dra_advanced_device_sharing_policy",
        "features": {
            "prioritized_list": {"state": "Kubernetes v1.36 stable", "feature_gate": "DRAPrioritizedList"},
            "partitionable_devices": {"state": "Kubernetes v1.36 beta and enabled by default", "feature_gate": "DRAPartitionableDevices"},
            "consumable_capacity": {"state": "feature-gated sharing primitive; validate target-cluster support before enforcement", "feature_gate": "DRAConsumableCapacity"},
            "device_binding_conditions": {
                "state": "Kubernetes v1.36 beta and enabled by default",
                "feature_gate": "DRADeviceBindingConditions",
                "scheduler_phase": "PreBind",
                "default_wait_seconds": 600,
            },
        },
        "policies": DEVICE_SHARING_POLICIES,
        "incident_guardrails": [
            "Never block incident creation or paging on advanced accelerator sharing decisions.",
            "Use prioritized alternatives to attach the best available diagnostic evidence to incidents.",
            "Keep drift backlog review on partitionable or consumable capacity so incident root-cause probes retain CPU headroom.",
            "Treat binding failure conditions as diagnostic limitations and require human review before lifting rollout freezes.",
            "Record selected device alternative in incident metadata and dashboard evidence.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/dra-advanced-device-sharing.yaml"],
        "references": [
            "https://kubernetes.io/blog/2026/05/07/kubernetes-v1-36-dra-136-updates/",
            "https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/",
            "https://kubernetes.io/blog/2025/09/18/kubernetes-v1-34-dra-consumable-capacity/",
        ],
    }
    write_json(root / "reports" / "advanced_device_sharing_plan.json", plan)
    return plan
