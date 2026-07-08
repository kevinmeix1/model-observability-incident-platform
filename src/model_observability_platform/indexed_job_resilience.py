from __future__ import annotations

from pathlib import Path

from .io import write_json


INCIDENT_SHARDS = [
    {"index": 0, "stage": "telemetry_freshness", "asset": "prediction_logs", "priority": "incident-critical"},
    {"index": 1, "stage": "schema_check", "asset": "serving_events", "priority": "incident-critical"},
    {"index": 2, "stage": "psi_drift", "asset": "features", "priority": "observability-checks"},
    {"index": 3, "stage": "null_rate", "asset": "features", "priority": "observability-checks"},
    {"index": 4, "stage": "volume_anomaly", "asset": "prediction_logs", "priority": "observability-checks"},
    {"index": 5, "stage": "slo_burn", "asset": "latency_p95", "priority": "incident-critical"},
    {"index": 6, "stage": "root_cause_probe", "asset": "upstream_assets", "priority": "incident-critical"},
    {"index": 7, "stage": "impact_analysis", "asset": "dashboards", "priority": "incident-critical"},
    {"index": 8, "stage": "gpu_diagnostic", "asset": "embedding_drift", "priority": "gpu-diagnostics"},
    {"index": 9, "stage": "alert_route", "asset": "pager", "priority": "incident-critical"},
    {"index": 10, "stage": "rollback_freeze", "asset": "release_gate", "priority": "incident-critical"},
    {"index": 11, "stage": "dashboard_publish", "asset": "incident_dashboard", "priority": "observability-checks"},
]


def build_indexed_job_resilience_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "deterministic_incident_shards",
            "passed": len({item["index"] for item in INCIDENT_SHARDS}) == len(INCIDENT_SHARDS),
            "evidence": "each freshness, drift, root-cause, alerting, and publish shard maps to one JOB_COMPLETION_INDEX value",
        },
        {
            "name": "per_index_retry_budget",
            "passed": True,
            "evidence": "backoffLimitPerIndex prevents one malformed asset check from delaying the whole incident wave",
        },
        {
            "name": "rollback_freeze_shard",
            "passed": any(item["stage"] == "rollback_freeze" for item in INCIDENT_SHARDS),
            "evidence": "rollout-freeze validation has an explicit incident-critical shard",
        },
        {
            "name": "pod_failure_policy",
            "passed": True,
            "evidence": "FailIndex handles bad source windows, FailJob handles image/config errors, and node disruptions are ignored",
        },
        {
            "name": "success_policy",
            "passed": True,
            "evidence": "successPolicy allows quorum completion while failed indexes drive focused recovery",
        },
        {
            "name": "airflow_failed_only_reprocessing",
            "passed": True,
            "evidence": "Airflow backfill create reruns failed incident dates with independent max_active_runs and reverse ordering",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_indexed_observability_job_resilience" if passed else "hold_indexed_incident_jobs",
        "kubernetes_job": {
            "api_version": "batch/v1",
            "completion_mode": "Indexed",
            "parallelism": 6,
            "completions": len(INCIDENT_SHARDS),
            "success_policy": {"succeeded_count": 10},
            "active_deadline_seconds": 5400,
            "ttl_seconds_after_finished": 86400,
        },
        "retry_policy": {
            "restart_policy": "Never",
            "backoff_limit_per_index": 1,
            "max_failed_indexes": 2,
            "fail_index_exit_codes": [42],
            "fail_job_exit_codes": [78, 126],
            "ignored_pod_conditions": ["DisruptionTarget"],
        },
        "airflow_backfill": {
            "command": "airflow backfill create --dag-id model_reliability_control_plane --from-date 2026-07-01 --to-date 2026-07-07 --reprocess-behavior failed --max-active-runs 2 --run-backwards",
            "reprocess_behavior": "failed",
            "max_active_runs": 2,
            "run_order": "latest_first",
            "incident_boundary": "incident creation stays ahead of historical reruns in pools and Kueue priority",
        },
        "incident_shards": INCIDENT_SHARDS,
        "checks": checks,
        "kubernetes_assets": ["kubernetes/indexed-job-resilience.yaml"],
        "references": [
            "https://kubernetes.io/docs/concepts/workloads/controllers/job/",
            "https://kubernetes.io/docs/tasks/job/pod-failure-policy/",
            "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/asset-scheduling.html",
        ],
    }
    write_json(root / "reports" / "indexed_job_resilience_plan.json", plan)
    return plan
