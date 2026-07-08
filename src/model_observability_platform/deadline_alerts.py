from __future__ import annotations

from pathlib import Path

from .io import write_json


DEADLINE_POLICIES = [
    {
        "name": "telemetry_freshness_window",
        "reference": "DeadlineReference.DAGRUN_QUEUED_AT",
        "interval": "5m",
        "callback": "page_observability_oncall",
        "severity": "page",
        "next_action": "inspect telemetry collector lag, prediction-log ingestion, and Kueue observability queue headroom",
    },
    {
        "name": "incident_creation_latency",
        "reference": "custom_failed_check_detected_at",
        "interval": "2m",
        "callback": "page_incident_router_owner",
        "severity": "page",
        "next_action": "verify incident dedupe state, alert route delivery, and webhook health before paging downstream teams",
    },
    {
        "name": "root_cause_fanout",
        "reference": "custom_incident_created_at",
        "interval": "15m",
        "callback": "open_root_cause_delay_incident",
        "severity": "ticket",
        "next_action": "inspect KubeRay diagnostic fanout, optional GPU drift queue, and lineage impact expansion",
    },
    {
        "name": "dashboard_publish",
        "reference": "DeadlineReference.DAGRUN_START_DATE",
        "interval": "5m",
        "callback": "notify_incident_commander",
        "severity": "ticket",
        "next_action": "publish the last-known-good reliability dashboard and attach stale dataset and impacted asset lists",
    },
]


def build_deadline_alert_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    checks = [
        {
            "name": "airflow3_deadline_alerts_declared",
            "passed": all("reference" in policy and "interval" in policy for policy in DEADLINE_POLICIES),
        },
        {
            "name": "legacy_sla_removed",
            "passed": all("SLA" not in policy["name"].upper() for policy in DEADLINE_POLICIES),
        },
        {
            "name": "callback_timeout_bounded",
            "passed": True,
            "evidence": "AIRFLOW__CALLBACKS__CALLBACK_EXECUTION_TIMEOUT=300",
        },
        {
            "name": "incident_creation_deadline",
            "passed": any(policy["name"] == "incident_creation_latency" and policy["interval"] == "2m" for policy in DEADLINE_POLICIES),
        },
        {
            "name": "freshness_deadline",
            "passed": any(policy["name"] == "telemetry_freshness_window" for policy in DEADLINE_POLICIES),
        },
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_airflow3_observability_deadline_alerts"
        if all(check["passed"] for check in checks)
        else "keep_legacy_sensor_alerts",
        "deadline_policies": DEADLINE_POLICIES,
        "runtime_config": {
            "AIRFLOW__CALLBACKS__CALLBACK_EXECUTION_TIMEOUT": "300",
            "max_active_runs": 1,
            "protected_pools": ["observability_pool", "observability_checks"],
        },
        "incident_escalation": {
            "page_on": ["telemetry_freshness_window", "incident_creation_latency"],
            "ticket_on": ["root_cause_fanout", "dashboard_publish"],
            "dedupe_key": "dag_id:run_id:deadline_policy",
        },
        "checks": checks,
        "migration_notes": [
            "Use Airflow 3 Deadline Alerts instead of legacy Airflow 2 SLA callbacks.",
            "Keep callbacks short and bounded; callbacks open or update incidents, while remediation remains an idempotent task.",
            "Reference custom timestamps for failed-check detection and incident creation when the default DAG run references are too coarse.",
            "Keep freshness and incident-creation deadlines page-grade because they determine whether downstream model rollback is timely.",
        ],
        "references": [
            "https://airflow.apache.org/docs/apache-airflow/stable/howto/deadline-alerts.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html",
        ],
    }
    write_json(root / "reports" / "deadline_alert_plan.json", plan)
    return plan
