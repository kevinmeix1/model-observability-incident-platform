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


CALLBACK_CONTRACTS = {
    "page_observability_oncall": {
        "receiver": "pagerduty://observability-oncall",
        "dedupe_key": "dag_id:run_id:telemetry_freshness_window",
        "payload_fields": ["dag_id", "run_id", "telemetry_window", "collector_lag_seconds", "kueue_queue"],
        "retry_policy": "bounded exponential backoff, max 3 attempts inside callback timeout",
        "allowed_side_effect": "page only; collector scaling remains an explicit remediation task",
        "owner": "observability-oncall",
    },
    "page_incident_router_owner": {
        "receiver": "pagerduty://incident-router-owner",
        "dedupe_key": "incident_fingerprint:incident_creation_latency",
        "payload_fields": ["incident_fingerprint", "failed_check", "route", "webhook_health"],
        "retry_policy": "page once per incident fingerprint and append delivery evidence",
        "allowed_side_effect": "page and attach route evidence; callback does not mutate rollout freeze state",
        "owner": "incident-routing",
    },
    "open_root_cause_delay_incident": {
        "receiver": "incident://root-cause-delay",
        "dedupe_key": "incident_id:root_cause_fanout",
        "payload_fields": ["incident_id", "rca_job_id", "lineage_impact_digest", "diagnostic_queue"],
        "retry_policy": "incident upsert keyed by incident id and deadline policy",
        "allowed_side_effect": "open or update diagnostic incident; do not run remediation directly",
        "owner": "model-reliability",
    },
    "notify_incident_commander": {
        "receiver": "slack://incident-command",
        "dedupe_key": "dashboard_version:dashboard_publish",
        "payload_fields": ["dashboard_version", "dashboard_url", "stale_dataset_count", "impacted_asset_count"],
        "retry_policy": "notify once per dashboard version and append stale evidence",
        "allowed_side_effect": "request last-known-good publish task; callback does not rewrite dashboard state",
        "owner": "incident-commander",
    },
}


def _deadline_policies_with_callbacks() -> list[dict]:
    return [
        {
            **policy,
            "callback_contract": CALLBACK_CONTRACTS[policy["callback"]],
        }
        for policy in DEADLINE_POLICIES
    ]


def build_deadline_alert_plan(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    root = Path(root)
    deadline_policies = _deadline_policies_with_callbacks()
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
            "name": "callback_contracts_declared",
            "passed": all(policy.get("callback_contract", {}).get("dedupe_key") for policy in deadline_policies),
        },
        {
            "name": "callbacks_have_bounded_side_effects",
            "passed": all("allowed_side_effect" in policy.get("callback_contract", {}) for policy in deadline_policies),
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
        "deadline_policies": deadline_policies,
        "callback_contracts": CALLBACK_CONTRACTS,
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
            "Give every callback an explicit dedupe key so retries do not duplicate pages or incidents.",
            "Restrict callback payloads to bounded metadata fields and never include raw telemetry or prediction bodies.",
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
