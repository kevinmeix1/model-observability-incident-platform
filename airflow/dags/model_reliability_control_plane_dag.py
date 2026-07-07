from __future__ import annotations

from datetime import datetime, timedelta

AIRFLOW_AVAILABLE = True

try:
    from airflow.decorators import dag, task, task_group
    from airflow.operators.empty import EmptyOperator
    from airflow.operators.python import BranchPythonOperator
    from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
    from airflow.sdk import Asset
    from airflow.utils.trigger_rule import TriggerRule
except Exception:
    AIRFLOW_AVAILABLE = False


MODELS = ["credit-risk", "churn-risk", "demand-forecast"]
CHECKS = ["feature_drift", "prediction_drift", "latency_slo", "error_rate", "freshness"]


def monitor_pod(task_id: str, command: str, *, priority_weight: int = 1):
    return KubernetesPodOperator(
        task_id=task_id,
        namespace="ml-observability",
        image="ghcr.io/kevinmeix1/model-observability-incident-platform:latest",
        cmds=["bash", "-lc"],
        arguments=[command],
        service_account_name="model-observability-runner",
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
        pool="observability_pool",
        priority_weight=priority_weight,
        retries=2,
        retry_delay=timedelta(minutes=2),
        labels={"platform": "model-observability", "task": task_id},
    )


if AIRFLOW_AVAILABLE:
    PREDICTION_LOGS = Asset("warehouse://ml/prediction_logs")
    INCIDENTS = Asset("incident://ml/model-reliability")
    DASHBOARD = Asset("dashboard://ml/model-observability")

    @dag(
        dag_id="model_reliability_control_plane",
        start_date=datetime(2026, 1, 1),
        schedule=[PREDICTION_LOGS],
        catchup=False,
        max_active_runs=1,
        default_args={
            "owner": "ml-observability",
            "retries": 2,
            "retry_delay": timedelta(minutes=2),
        },
        tags=["observability", "incident-response", "drift", "slo", "kubernetes"],
    )
    def model_reliability_control_plane():
        start = EmptyOperator(task_id="start_reliability_cycle")

        @task
        def monitoring_matrix() -> list[dict]:
            return [{"model": model, "check": check} for model in MODELS for check in CHECKS]

        @task_group(group_id="telemetry_preparation")
        def telemetry_group():
            compact_logs = monitor_pod("compact_prediction_logs", "make demo", priority_weight=5)
            build_reference = monitor_pod("build_reference_window", "make demo", priority_weight=4)
            build_current = monitor_pod("build_current_window", "make demo", priority_weight=4)
            compact_logs >> [build_reference, build_current]
            return build_current

        @task_group(group_id="parallel_health_checks")
        def health_check_group(matrix: list[dict]):
            @task(pool="observability_checks")
            def run_single_check(spec: dict) -> dict:
                return {**spec, "status": "evaluated", "incident_policy": "dedupe_by_fingerprint"}

            @task(pool="observability_checks")
            def enrich_check_result(result: dict) -> dict:
                return {**result, "lineage": f"{result['model']}->{result['check']}", "severity": "high"}

            raw = run_single_check.expand(spec=matrix)
            return enrich_check_result.expand(result=raw)

        @task_group(group_id="incident_response")
        def incident_group():
            create_incidents = monitor_pod("create_or_update_incidents", "make demo", priority_weight=10)
            route_alerts = monitor_pod("route_alerts_to_placeholders", "make demo", priority_weight=7)
            publish_runbook = monitor_pod("publish_runbook_context", "make demo", priority_weight=4)
            create_incidents >> route_alerts >> publish_runbook
            return publish_runbook

        branch = BranchPythonOperator(task_id="branch_on_top_severity", python_callable=lambda: "rollback_recommendation")
        rollback_recommendation = monitor_pod("rollback_recommendation", "make demo", priority_weight=10)
        observe_only = EmptyOperator(task_id="observe_only")
        publish_dashboard = monitor_pod("publish_observability_dashboard", "make demo", priority_weight=2)
        publish_dashboard.trigger_rule = TriggerRule.ALL_DONE
        end = EmptyOperator(task_id="reliability_cycle_complete", outlets=[INCIDENTS, DASHBOARD])

        matrix = monitoring_matrix()
        start >> telemetry_group() >> health_check_group(matrix) >> incident_group() >> branch
        branch >> rollback_recommendation >> publish_dashboard >> end
        branch >> observe_only >> publish_dashboard

    model_reliability_control_plane()
