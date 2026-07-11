from __future__ import annotations

from pathlib import Path

from .io import write_json


def build_ai_workload_telemetry_plan(root: str | Path) -> dict:
    root = Path(root)
    workloads = [
        {
            "name": "drift-evaluation-window",
            "kind": "Airflow Asset DAG",
            "queue": "observability-checks-queue",
            "asset": "asset://observability/current-window",
            "resource_signals": ["pod.resources.requests.cpu", "pod.resources.limits.memory", "pod.scheduling.gate"],
            "otel_attributes": ["airflow.dag_id", "airflow.asset.uri", "eval.window.id", "gen_ai.request.model"],
            "slo": {"evaluation_seconds": 60, "freshness_minutes": 30, "failed_check_coverage": 1.0},
            "remediation": "open a deduped incident, freeze risky rollouts, and attach failed check evidence to the incident timeline",
        },
        {
            "name": "incident-root-cause-worker",
            "kind": "Kueue Workload",
            "queue": "incident-critical",
            "asset": "incident://root-cause/high-severity",
            "resource_signals": ["pod.resources.requests.cpu", "pod.resources.limits.memory", "dra.resourceclaim.status"],
            "otel_attributes": ["incident.id", "incident.severity", "root_cause.category", "kueue.workload.name"],
            "slo": {"triage_seconds": 180, "notification_seconds": 45, "freshness_minutes": 5},
            "remediation": "preempt noncritical dashboard refreshes, claim notification outbox events once, and publish impacted assets",
        },
        {
            "name": "dashboard-publisher",
            "kind": "Runtime Service",
            "queue": "observability-ui",
            "asset": "dashboard://model-observability",
            "resource_signals": ["pod.resources.requests.cpu", "pod.resources.limits.memory", "pod.resize.policy"],
            "otel_attributes": ["dashboard.version", "incident.open_count", "release.freeze", "http.route"],
            "slo": {"render_seconds": 2, "staleness_minutes": 10, "availability": 0.995},
            "remediation": "serve last-known-good incident state, shrink warm publishers after recovery, and require fresh evidence before unfreezing",
        },
    ]
    required_resource_fields = {field for workload in workloads for field in workload["resource_signals"]}
    required_otel_fields = {field for workload in workloads for field in workload["otel_attributes"]}
    plan = {
        "generated_at": "2026-07-11T00:00:00Z",
        "standard_alignment": {
            "airflow": "Asset events drive drift evaluation windows and downstream incident workflows.",
            "kubernetes": "Pod-level resource pressure, Kueue priority, and DRA health explain incident-worker scheduling.",
            "opentelemetry": "Incident, root-cause, and model attributes are allow-listed for dashboards and notification workers.",
        },
        "workloads": workloads,
        "required_resource_fields": sorted(required_resource_fields),
        "required_otel_fields": sorted(required_otel_fields),
        "checks": [
            {"name": "incident_identity_mapped", "passed": "incident.id" in required_otel_fields},
            {"name": "asset_lineage_mapped", "passed": "airflow.asset.uri" in required_otel_fields},
            {"name": "dra_health_mapped", "passed": any("dra." in field for field in required_resource_fields)},
            {"name": "dashboard_recovery_declared", "passed": any("last-known-good" in workload["remediation"] for workload in workloads)},
        ],
        "runbook": [
            "Correlate drift windows, incident ids, and Kueue priority before paging or freezing releases.",
            "Use transactional outbox status as notification truth, not dashboard refresh state.",
            "Publish last-known-good dashboards when telemetry is stale, then annotate recovery after two healthy windows.",
        ],
    }
    plan["passed"] = all(check["passed"] for check in plan["checks"])
    write_json(root / "reports" / "ai_workload_telemetry_plan.json", plan)
    return plan
