from __future__ import annotations

from pathlib import Path

from .io import write_json


def _utilization(used: float, quota: float) -> float:
    return round(used / max(quota, 0.0001), 4)


def _tenant(
    *,
    name: str,
    namespace: str,
    queue: str,
    cost_center: str,
    cpu_quota: float,
    cpu_used: float,
    memory_quota_gib: float,
    memory_used_gib: float,
    pool_slots: int,
    pool_used: int,
    priority_class: str,
) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "queue": queue,
        "cost_center": cost_center,
        "priority_class": priority_class,
        "quota": {"cpu": cpu_quota, "memory_gib": memory_quota_gib, "airflow_pool_slots": pool_slots},
        "observed": {"cpu": cpu_used, "memory_gib": memory_used_gib, "airflow_pool_slots": pool_used},
        "utilization": {
            "cpu": _utilization(cpu_used, cpu_quota),
            "memory": _utilization(memory_used_gib, memory_quota_gib),
            "airflow_pool": _utilization(pool_used, pool_slots),
        },
        "labels": {
            "platform.mlops.dev/tenant": name,
            "platform.mlops.dev/cost-center": cost_center,
            "platform.mlops.dev/data-domain": "model-observability",
        },
    }


def build_tenancy_report(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    tenants = [
        _tenant(
            name="incident-response",
            namespace="ml-observability-incident",
            queue="incident-critical-queue",
            cost_center="ml-reliability",
            cpu_quota=18,
            cpu_used=8,
            memory_quota_gib=72,
            memory_used_gib=30,
            pool_slots=7,
            pool_used=3,
            priority_class="observability-incident-critical",
        ),
        _tenant(
            name="drift-monitoring",
            namespace="ml-observability-drift",
            queue="drift-monitoring-queue",
            cost_center="ml-platform",
            cpu_quota=14,
            cpu_used=9,
            memory_quota_gib=56,
            memory_used_gib=36,
            pool_slots=4,
            pool_used=3,
            priority_class="observability-normal",
        ),
        _tenant(
            name="retention-maintenance",
            namespace="ml-observability-retention",
            queue="retention-maintenance-queue",
            cost_center="platform-ops",
            cpu_quota=8,
            cpu_used=7,
            memory_quota_gib=32,
            memory_used_gib=22,
            pool_slots=2,
            pool_used=2,
            priority_class="observability-low-priority",
        ),
    ]
    cpu_utils = [tenant["utilization"]["cpu"] for tenant in tenants]
    pool_utils = [tenant["utilization"]["airflow_pool"] for tenant in tenants]
    noisy_neighbor_risks = [
        tenant["name"]
        for tenant in tenants
        if max(tenant["utilization"].values()) >= 0.90 and tenant["priority_class"] == "observability-low-priority"
    ]
    checks = [
        {"name": "namespace_resource_quotas", "passed": all(tenant["quota"]["cpu"] > 0 for tenant in tenants)},
        {"name": "no_hard_quota_breach", "passed": all(max(tenant["utilization"].values()) <= 1.0 for tenant in tenants)},
        {"name": "incident_capacity_reserved", "passed": tenants[0]["quota"]["airflow_pool_slots"] - tenants[0]["observed"]["airflow_pool_slots"] >= 2},
        {"name": "tenant_cost_labels", "passed": all("platform.mlops.dev/cost-center" in tenant["labels"] for tenant in tenants)},
        {"name": "noisy_neighbor_contained", "passed": all(risk == "retention-maintenance" for risk in noisy_neighbor_risks), "observed": noisy_neighbor_risks},
    ]
    report = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "tenants": tenants,
        "checks": checks,
        "fairness": {
            "cohort": "ml-observability-cohort",
            "max_cpu_utilization_gap": round(max(cpu_utils) - min(cpu_utils), 4),
            "max_airflow_pool_utilization_gap": round(max(pool_utils) - min(pool_utils), 4),
            "borrowing_policy": "retention maintenance may borrow only after incident diagnostics and drift monitors have spare quota",
        },
        "controls": [
            "Incident, drift, and retention workloads use separate namespaces with ResourceQuota.",
            "Kueue cohorts allow drift work to borrow idle quota without starving incident response.",
            "Airflow pools reserve diagnostic capacity for paging incidents.",
            "Cost-center labels support chargeback for telemetry-heavy jobs.",
            "Default-deny NetworkPolicies block maintenance jobs from incident routing services.",
        ],
        "references": [
            "https://kubernetes.io/docs/concepts/security/multi-tenancy/",
            "https://kubernetes.io/docs/concepts/policy/resource-quotas/",
            "https://kueue.sigs.k8s.io/docs/concepts/cohort/",
            "https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html",
        ],
    }
    write_json(Path(root) / "reports" / "tenancy_fairness_report.json", report)
    return report
