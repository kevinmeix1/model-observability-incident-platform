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
        deferrable=True,
        logging_interval=30,
        reattach_on_restart=True,
        on_finish_action="delete_pod",
        on_kill_action="delete_pod",
        startup_timeout_seconds=180,
        execution_timeout=timedelta(minutes=45),
        pod_template_file="/opt/airflow/dags/repo/kubernetes/airflow-kubernetes-executor-pod-template.yaml",
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

        @task_group(group_id="slo_budget_and_capacity")
        def slo_budget_group():
            reserve_observability_quota = monitor_pod(
                "reserve_kueue_observability_quota",
                "kubectl get localqueue observability-checks-queue -n ml-observability",
                priority_weight=4,
            )
            submit_ray_incident_fanout = monitor_pod(
                "submit_kuberay_incident_fanout",
                "kubectl apply -f kubernetes/kuberay-kueue-workloads.yaml",
                priority_weight=6,
            )
            wait_for_ray_incident_fanout = monitor_pod(
                "wait_for_kuberay_incident_fanout_deferrable",
                "kubectl wait --for=condition=Complete rayjob/incident-root-cause-fanout -n ml-observability --timeout=20m",
                priority_weight=6,
            )
            check_alert_budget = monitor_pod(
                "check_alert_budget_burn_rate",
                "python -m model_observability_platform demo",
                priority_weight=5,
            )
            wait_for_dashboard_route = monitor_pod(
                "wait_for_dashboard_route_deferrable",
                "kubectl wait --for=condition=Accepted httproute/model-observability-dashboard-route -n ml-observability --timeout=5m",
                priority_weight=3,
            )
            reserve_observability_quota >> submit_ray_incident_fanout >> wait_for_ray_incident_fanout >> check_alert_budget >> wait_for_dashboard_route
            return wait_for_dashboard_route

        branch = BranchPythonOperator(task_id="branch_on_top_severity", python_callable=lambda: "rollback_recommendation")
        rollback_recommendation = monitor_pod("rollback_recommendation", "make demo", priority_weight=10)
        observe_only = EmptyOperator(task_id="observe_only")
        publish_dashboard = monitor_pod("publish_observability_dashboard", "make demo", priority_weight=2)
        publish_dashboard.trigger_rule = TriggerRule.ALL_DONE
        end = EmptyOperator(task_id="reliability_cycle_complete", outlets=[INCIDENTS, DASHBOARD])

        matrix = monitoring_matrix()
        start >> telemetry_group() >> health_check_group(matrix) >> slo_budget_group() >> incident_group() >> branch
        branch >> rollback_recommendation >> publish_dashboard >> end
        branch >> observe_only >> publish_dashboard

    model_reliability_control_plane()
