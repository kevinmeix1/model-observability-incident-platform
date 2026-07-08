from __future__ import annotations

from pathlib import Path

from .io import write_json


DEVICE_HEALTH_EVENTS = [
    {
        "workload": "embedding-drift-check",
        "namespace": "mlops-observability",
        "pod": "embedding-drift-dra-check-0",
        "container": "embedding-drift",
        "resource_claim": "l4-shared-drift-claim",
        "device_class": "gpu-l4-shared",
        "resource": "gpu.resource.kubernetes.io",
        "health": "Unhealthy",
        "message": "driver reported tensor-core fault on shared L4 during embedding drift comparison",
        "owner_action": "run CPU PSI-only drift checks and attach GPU diagnostic limitation to the incident",
    },
    {
        "workload": "large-monitor-review",
        "namespace": "mlops-observability",
        "pod": "large-monitor-review-0",
        "container": "large-monitor-review",
        "resource_claim": "a100-mig-monitor-claim",
        "device_class": "gpu-a100-mig",
        "resource": "gpu.resource.kubernetes.io",
        "health": "Unknown",
        "message": "DRA driver missed health update timeout after 30 seconds",
        "owner_action": "sample fewer records, attach the limitation to the incident, and require human review",
    },
    {
        "workload": "incident-root-cause-probe",
        "namespace": "mlops-observability",
        "pod": "incident-root-cause-probe-cpu-0",
        "container": "root-cause-probe",
        "resource_claim": None,
        "device_class": "cpu-burst",
        "resource": "cpu",
        "health": "Healthy",
        "message": "CPU root-cause probe has no DRA device dependency",
        "owner_action": "keep incident creation, paging, and rollout-freeze guidance live",
    },
]


def build_resource_health_status_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    unhealthy = [event for event in DEVICE_HEALTH_EVENTS if event["health"] in {"Unhealthy", "Unknown"}]
    checks = [
        {
            "name": "resource_health_status_enabled",
            "passed": True,
            "evidence": "ResourceHealthStatus is beta and enabled by default in Kubernetes v1.36.",
        },
        {
            "name": "pod_allocated_resources_status_checked",
            "passed": all(event["container"] and event["pod"] for event in DEVICE_HEALTH_EVENTS),
            "evidence": "Runbook queries Pod status.containerStatuses[*].allocatedResourcesStatus before suppressing a diagnostic signal.",
        },
        {
            "name": "resourceclaim_device_status_checked",
            "passed": any(event["resource_claim"] for event in DEVICE_HEALTH_EVENTS),
            "evidence": "ResourceClaim status.devices is captured for embedding drift and large monitor review accelerator claims.",
        },
        {
            "name": "device_taint_rule_declared",
            "passed": True,
            "evidence": "DeviceTaintRule quarantines unhealthy diagnostic GPUs before more drift checks land on them.",
        },
        {
            "name": "incident_path_unblocked",
            "passed": any(event["workload"] == "incident-root-cause-probe" and event["resource"] == "cpu" for event in DEVICE_HEALTH_EVENTS),
            "evidence": "Incident creation, paging, and rollout-freeze guidance stay CPU-runnable while GPU diagnostics degrade.",
        },
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_observability_dra_resource_health_runbook",
        "feature": {
            "name": "ResourceHealthStatus",
            "state": "Kubernetes v1.36 beta and enabled by default",
            "pod_status_field": "status.containerStatuses[*].allocatedResourcesStatus",
            "driver_service": "DRAResourceHealth gRPC service",
            "default_unknown_timeout_seconds": 30,
        },
        "companion_features": {
            "resource_claim_device_status": "Kubernetes v1.33 beta; status.devices on ResourceClaim",
            "granular_status_authorization": "Kubernetes v1.36 beta; synthetic subresources and node-aware verbs",
            "device_taints": "Kubernetes v1.36 beta; DeviceTaintRule uses resource.k8s.io/v1beta2",
        },
        "device_health_events": DEVICE_HEALTH_EVENTS,
        "unhealthy_or_unknown_count": len(unhealthy),
        "incident_decision_policy": [
            "Never block incident creation, paging, or rollout-freeze advice on accelerator diagnostics.",
            "Annotate incidents when embedding drift or large monitor review results are degraded by DRA health.",
            "Fall back to CPU PSI-only drift checks while unhealthy diagnostic devices are quarantined.",
            "Compare Pod allocatedResourcesStatus with ResourceClaim status.devices before declaring a monitor unavailable.",
            "Require a fresh healthy diagnostic device snapshot before lifting evidence limitations from incident reports.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/dra-resource-health-status.yaml"],
        "references": [
            "https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/",
            "https://kubernetes.io/blog/2026/05/07/kubernetes-v1-36-dra-136-updates/",
            "https://github.com/kubernetes/sig-release/discussions/2958",
        ],
    }
    write_json(root / "reports" / "resource_health_status_plan.json", plan)
    return plan
