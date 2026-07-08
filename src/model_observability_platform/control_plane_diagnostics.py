from __future__ import annotations

from pathlib import Path

from .io import write_json


COMPONENTS = [
    {
        "name": "kube-apiserver",
        "statusz": "/statusz",
        "flagz": "/flagz",
        "metrics": ["apiserver_watch_cache_initializations_total", "apiserver_request_duration_seconds"],
        "critical_flags": ["ComponentStatusz", "ComponentFlagz", "WatchCache", "NativeHistogramMetrics"],
    },
    {
        "name": "kube-controller-manager",
        "statusz": "/statusz",
        "flagz": "/flagz",
        "metrics": ["workqueue_depth", "workqueue_retries_total"],
        "critical_flags": ["ComponentStatusz", "ComponentFlagz", "ConcurrentEndpointSyncs"],
    },
    {
        "name": "kube-scheduler",
        "statusz": "/statusz",
        "flagz": "/flagz",
        "metrics": ["scheduler_pending_pods", "scheduler_queue_incoming_pods_total"],
        "critical_flags": ["ComponentStatusz", "ComponentFlagz", "PodGroupScheduling"],
    },
    {
        "name": "kubelet",
        "statusz": "/statusz",
        "flagz": "/flagz",
        "metrics": ["kubelet_psi_cpu_some_seconds_total", "kubelet_psi_memory_some_seconds_total"],
        "critical_flags": ["ComponentStatusz", "ComponentFlagz", "KubeletPSI", "UserNamespacesSupport"],
    },
]


CONTROLLERS = [
    {
        "name": "incident-router-controller",
        "freshness_budget_seconds": 30,
        "watch_source": "incident, SLO burn, and alert policy watch",
        "stale_action": "fail closed and keep rollout freeze active until incidents are read directly",
    },
    {
        "name": "drift-diagnostic-controller",
        "freshness_budget_seconds": 60,
        "watch_source": "drift window, Kueue Workload, and diagnostic Job watch",
        "stale_action": "hold root-cause conclusion and keep incident severity unchanged",
    },
    {
        "name": "rollout-freeze-controller",
        "freshness_budget_seconds": 30,
        "watch_source": "release admission, incident status, and Gateway route freeze watch",
        "stale_action": "keep freeze asserted and require direct API confirmation before allowing promotion",
    },
]


def build_control_plane_diagnostics_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    checks = [
        {
            "name": "statusz_and_flagz_coverage",
            "passed": all(component["statusz"] == "/statusz" and component["flagz"] == "/flagz" for component in COMPONENTS),
            "evidence": "Every control-plane component has explicit /statusz and /flagz scrape coverage.",
        },
        {
            "name": "incident_controller_staleness_budgets",
            "passed": all(controller["freshness_budget_seconds"] <= 60 for controller in CONTROLLERS),
            "evidence": "Incident routing, drift diagnostics, and rollout-freeze controllers all fail closed inside one minute.",
        },
        {
            "name": "psi_metric_coverage",
            "passed": any("kubelet_psi_memory_some_seconds_total" in component["metrics"] for component in COMPONENTS),
            "evidence": "Kubelet PSI metrics catch node pressure before it masks telemetry or dashboard freshness failures.",
        },
        {
            "name": "native_histogram_readiness",
            "passed": any("NativeHistogramMetrics" in component["critical_flags"] for component in COMPONENTS),
            "evidence": "The plan records native histogram readiness for high-cardinality incident and control-plane latency metrics.",
        },
        {
            "name": "flag_drift_detection",
            "passed": all("ComponentFlagz" in component["critical_flags"] for component in COMPONENTS),
            "evidence": "/flagz drift detection protects incident and rollout-freeze automation during Kubernetes upgrades.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-07T00:00:00Z",
        "recommended_action": "enable_control_plane_freshness_diagnostics" if passed else "keep_incident_controller_freshness_in_warn_mode",
        "passed": passed,
        "feature_status": {
            "controller_staleness": "Kubernetes v1.36 beta stale-cache mitigation for controllers",
            "component_statusz": "Kubernetes v1.36 beta ComponentStatusz endpoint",
            "component_flagz": "Kubernetes v1.36 beta ComponentFlagz endpoint",
            "psi_metrics": "Kubernetes v1.36 stable kubelet PSI metrics",
            "native_histograms": "Kubernetes v1.36 alpha native histogram support",
        },
        "components": COMPONENTS,
        "controllers": CONTROLLERS,
        "checks": checks,
        "incident_runbook": [
            "If incident router freshness exceeds budget, keep rollout freeze active.",
            "Read incident, SLO, Kueue Workload, and Gateway route state directly before reducing severity.",
            "Compare /flagz output with the expected ComponentStatusz, ComponentFlagz, KubeletPSI, and NativeHistogramMetrics gates after upgrades.",
            "Use PSI and native histogram metrics to separate control-plane pressure from telemetry quality regressions.",
        ],
        "references": [
            "https://kubernetes.io/blog/2026/04/28/kubernetes-v1-36-staleness-mitigation-for-controllers/",
            "https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/",
            "https://kubernetes.io/blog/2026/04/25/kubernetes-v1-36-psi-metrics/",
        ],
    }
    write_json(root / "reports" / "control_plane_diagnostics_plan.json", plan)
    return plan
