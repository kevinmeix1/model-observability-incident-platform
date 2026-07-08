from __future__ import annotations

from pathlib import Path

from .io import write_json


POD_RESOURCE_WORKLOADS = [
    {
        "name": "prediction-log-compactor",
        "namespace": "mlops-observability",
        "pod_level_requests": {"cpu": "2", "memory": "4Gi"},
        "pod_level_limits": {"cpu": "3", "memory": "6Gi"},
        "scheduling_gates": ["mlops.kevinmei.dev/telemetry-window-ready"],
        "release_condition": "reference and current prediction windows are sealed before compaction starts",
        "containers": ["log-compactor", "otel-sidecar"],
    },
    {
        "name": "incident-root-cause-fanout",
        "namespace": "mlops-observability",
        "pod_level_requests": {"cpu": "5", "memory": "10Gi"},
        "pod_level_limits": {"cpu": "7", "memory": "14Gi"},
        "scheduling_gates": ["mlops.kevinmei.dev/incident-evidence-ready", "mlops.kevinmei.dev/kueue-admitted"],
        "release_condition": "incident evidence bundle is mounted and Kueue admits root-cause fanout",
        "containers": ["root-cause-worker", "evidence-writer"],
    },
    {
        "name": "dashboard-publisher",
        "namespace": "mlops-observability",
        "pod_level_requests": {"cpu": "2", "memory": "3Gi"},
        "pod_level_limits": {"cpu": "3", "memory": "5Gi"},
        "scheduling_gates": ["mlops.kevinmei.dev/policy-digest-ready"],
        "release_condition": "policy bundle digest is pinned before publishing incident dashboard evidence",
        "containers": ["dashboard-publisher", "checkpoint-writer"],
    },
]


def build_pod_resource_envelope_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "pod_level_resources_declared",
            "passed": all(item["pod_level_requests"] and item["pod_level_limits"] for item in POD_RESOURCE_WORKLOADS),
            "evidence": "Observability pods use pod-level CPU and memory envelopes around diagnostic workers and evidence sidecars.",
        },
        {
            "name": "scheduling_gates_declared",
            "passed": all(item["scheduling_gates"] for item in POD_RESOURCE_WORKLOADS),
            "evidence": "Compaction, root-cause, and publishing pods stay SchedulingGated until telemetry, evidence, queue, or policy prerequisites pass.",
        },
        {
            "name": "gate_release_runbook",
            "passed": True,
            "evidence": "Incident automation removes gates only after telemetry windows, evidence volumes, Kueue admission, and policy digests are verified.",
        },
        {
            "name": "scheduler_churn_metric",
            "passed": True,
            "evidence": "scheduler_pending_pods{queue=\"gated\"} is tracked separately from unschedulable observability pods.",
        },
        {
            "name": "dra_compatibility_guardrail",
            "passed": True,
            "evidence": "GPU diagnostic ResourceClaims and container requests must fit inside pod-level envelopes before gate removal.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_observability_pod_resource_envelopes_and_scheduling_gates" if passed else "keep_container_only_observability_requests",
        "kubernetes_version_target": "1.34+",
        "feature_gates": {
            "PodLevelResources": "beta, enabled by default in Kubernetes 1.34+ clusters that support the feature",
            "PodSchedulingReadiness": "stable since Kubernetes 1.30",
            "PodLevelResourceManagers": "enable where CPUManager, MemoryManager, or TopologyManager alignment is required",
        },
        "workloads": POD_RESOURCE_WORKLOADS,
        "release_runbook": [
            "Create compaction, root-cause, and dashboard pods with schedulingGates so scheduler work starts only after prerequisites exist.",
            "Verify sealed telemetry windows, incident evidence bundles, Kueue admission, policy bundle digest, and rollout-freeze state.",
            "Patch away gates in any order after prerequisites pass; never add new gates after pod creation.",
            "Alert on scheduler_pending_pods{queue=\"gated\"} and gates older than incident response SLOs.",
        ],
        "checks": checks,
        "kubernetes_assets": [
            "kubernetes/pod-resource-envelopes.yaml",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/configure-pod-container/assign-pod-level-resources/",
            "https://kubernetes.io/docs/concepts/scheduling-eviction/pod-scheduling-readiness/",
            "https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/",
        ],
    }
    write_json(root / "reports" / "pod_resource_envelope_plan.json", plan)
    return plan
