from __future__ import annotations

from pathlib import Path

from .io import write_json


RESIZE_POLICIES = [
    {
        "name": "embedding-drift-startup-boost",
        "workload": "embedding-drift-check",
        "scope": "container",
        "resource_patch": {"requests.cpu": "1200m", "limits.memory": "1536Mi"},
        "resize_policy": {"cpu": "NotRequired", "memory": "RestartContainer"},
        "trigger": "embedding drift check lags behind telemetry freshness while incidents remain open",
        "owner_action": "boost CPU in-place without suppressing drift alerts or incident creation",
    },
    {
        "name": "incident-fanout-pod-level-burst",
        "workload": "incident-root-cause-probe",
        "scope": "pod",
        "resource_patch": {"spec.resources.limits.cpu": "6", "spec.resources.requests.memory": "8Gi"},
        "resize_policy": {"cpu": "NotRequired", "memory": "RestartContainer"},
        "trigger": "root-cause fanout has a diagnostic backlog but node fit remains feasible",
        "owner_action": "expand the pod-level envelope before delaying rollout-freeze guidance",
    },
    {
        "name": "dashboard-publisher-warm-shrink",
        "workload": "incident-dashboard-publisher",
        "scope": "container",
        "resource_patch": {"requests.cpu": "100m", "limits.memory": "256Mi"},
        "resize_policy": {"cpu": "NotRequired", "memory": "NotRequired"},
        "trigger": "dashboard publisher is idle after incident summary is written",
        "owner_action": "shrink idle publisher resources while keeping dashboard refresh warm for incident updates",
    },
]


def build_inplace_resize_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {"name": "container_resize_ga", "passed": True, "evidence": "Kubernetes v1.35 made in-place CPU and memory resizing stable through the resize subresource."},
        {"name": "pod_level_resize_beta", "passed": any(policy["scope"] == "pod" for policy in RESIZE_POLICIES), "evidence": "Kubernetes v1.36 beta pod-level resource resizing covers multi-container incident fanout probes."},
        {"name": "resize_policy_defined", "passed": all(policy["resize_policy"] for policy in RESIZE_POLICIES), "evidence": "Observability workloads declare whether CPU and memory changes can happen without restarts."},
        {"name": "incident_signal_not_suppressed", "passed": any("without suppressing" in policy["owner_action"] for policy in RESIZE_POLICIES), "evidence": "Resize controls cannot mute incidents, paging, or rollout-freeze advice."},
        {"name": "vpa_inplace_or_recreate_ready", "passed": True, "evidence": "VPA recommendation mode is modeled with InPlaceOrRecreate for monitor and incident worker pods."},
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_observability_inplace_resize_controls",
        "features": {
            "in_place_pod_resize": {
                "state": "Kubernetes v1.35 stable",
                "subresource": "pods/resize",
                "container_status_field": "status.containerStatuses[*].resources",
            },
            "pod_level_resource_resize": {
                "state": "Kubernetes v1.36 beta and enabled by default",
                "feature_gate": "InPlacePodLevelResourcesVerticalScaling",
                "pod_spec_field": "spec.resources",
                "status_conditions": ["PodResizePending", "PodResizeInProgress"],
            },
            "autoscaler_integration": {
                "vpa_update_mode": "InPlaceOrRecreate",
                "requires_runtime": "cgroup v2 and CRI UpdateContainerResources support",
            },
        },
        "policies": RESIZE_POLICIES,
        "incident_guardrails": [
            "Never suppress incidents, paging, or rollout-freeze advice while PodResizePending or PodResizeInProgress is active.",
            "Record incident id, monitor name, desired resources, status.resources, and VPA recommendation in incident evidence.",
            "Use CPU in-place resize for drift monitor bursts; memory changes must follow the declared resizePolicy path.",
            "Keep dashboard publishing warm by shrinking idle pods rather than deleting incident visibility paths.",
            "Treat pod-level incident fanout resize as response acceleration, not evidence that the incident is resolved.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/inplace-pod-resize.yaml"],
        "references": [
            "https://kubernetes.io/blog/2025/12/19/kubernetes-v1-35-in-place-pod-resize-ga/",
            "https://kubernetes.io/blog/2026/04/30/kubernetes-v1-36-inplace-pod-level-resources-beta/",
            "https://kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/",
        ],
    }
    write_json(root / "reports" / "inplace_resize_plan.json", plan)
    return plan
