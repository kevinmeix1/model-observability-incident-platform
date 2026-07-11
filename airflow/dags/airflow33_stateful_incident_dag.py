"""Airflow 3.3 stateful model incident orchestration.

CI parses this module against Apache Airflow 3.3. The local dependency-light
demo does not start Airflow services, but this is executable DAG-authoring code.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.sdk import (
    NEVER_EXPIRE,
    Asset,
    DAG,
    ExceptionRetryPolicy,
    FanOutMapper,
    FixedKeyMapper,
    MinimumCount,
    PartitionedAssetTimetable,
    PartitionedAtRuntime,
    RetryAction,
    RetryRule,
    RollupMapper,
    SegmentWindow,
    StartOfWeekMapper,
    WeekWindow,
    asset,
    task,
)


AIRFLOW_33_DAG_IDS = {
    "stateful_incident_evidence_rollup",
    "weekly_telemetry_daily_diagnostic_fanout",
}
INCIDENT_SEGMENTS = ["telemetry-freshness", "drift-analysis", "slo-burn-rate"]

INCIDENT_RETRY_POLICY = ExceptionRetryPolicy(
    rules=[
        RetryRule(
            exception=ConnectionError,
            action=RetryAction.RETRY,
            retry_delay=timedelta(seconds=30),
            reason="Transient warehouse, Prometheus, or Kubernetes API failure",
        ),
        RetryRule(
            exception=PermissionError,
            action=RetryAction.FAIL,
            reason="Rollout-freeze authorization failures require operator intervention",
        ),
    ],
)

INCIDENT_EVIDENCE_SEGMENTS = Asset.ref(name="incident_evidence_segments")
ROOT_CAUSE_DECISION = Asset(
    uri="incident://ml/model-reliability/stateful-root-cause",
    name="stateful_incident_root_cause",
)
WEEKLY_TELEMETRY_SNAPSHOT = Asset(
    uri="warehouse://ml/prediction-telemetry/weekly-snapshot",
    name="weekly_model_telemetry_snapshot",
)


@asset(
    uri="s3://ml-observability/incidents/evidence-segments.json",
    schedule=PartitionedAtRuntime(),
)
def incident_evidence_segments(self, outlet_events) -> None:
    """Emit the evidence partitions discovered for an incident fingerprint."""

    outlet_events[self].add_partitions(INCIDENT_SEGMENTS)


with DAG(
    dag_id="stateful_incident_evidence_rollup",
    schedule=PartitionedAssetTimetable(
        assets=INCIDENT_EVIDENCE_SEGMENTS,
        default_partition_mapper=RollupMapper(
            upstream_mapper=FixedKeyMapper("incident-ready"),
            window=SegmentWindow(INCIDENT_SEGMENTS),
            wait_policy=MinimumCount(len(INCIDENT_SEGMENTS)),
            max_downstream_keys=1,
        ),
    ),
    catchup=False,
    max_active_runs=1,
    params={
        "incident_fingerprint": "replace-at-trigger-time",
        "route_generation": "replace-at-trigger-time",
    },
    tags=["airflow-3.3", "state-store", "incident-response", "observability"],
) as stateful_incident_evidence_rollup:

    @task(
        inlets=[INCIDENT_EVIDENCE_SEGMENTS],
        outlets=[ROOT_CAUSE_DECISION],
        retries=4,
        retry_delay=timedelta(minutes=1),
        retry_policy=INCIDENT_RETRY_POLICY,
    )
    def checkpoint_root_cause_decision(**context) -> dict[str, str]:
        task_store = context["task_state_store"]
        operation_id = task_store.get("incident_operation_id")
        if operation_id is None:
            operation_id = f"incident:{context['run_id']}"
            task_store.set(
                "incident_operation_id", operation_id, retention=NEVER_EXPIRE
            )

        task_store.set(
            "diagnostic_progress",
            {"stage": "evidence_complete", "attempt": context["ti"].try_number},
        )
        decision_store = context["asset_state_store"][ROOT_CAUSE_DECISION]
        decision_store.set(
            "incident_fingerprint", context["params"]["incident_fingerprint"]
        )
        decision_store.set(
            "observed_route_generation", context["params"]["route_generation"]
        )
        return {"operation_id": operation_id, "status": "ready_for_root_cause_policy"}

    checkpoint_root_cause_decision()


with DAG(
    dag_id="weekly_telemetry_daily_diagnostic_fanout",
    schedule=PartitionedAssetTimetable(
        assets=WEEKLY_TELEMETRY_SNAPSHOT,
        default_partition_mapper=FanOutMapper(
            upstream_mapper=StartOfWeekMapper(),
            window=WeekWindow(),
            max_downstream_keys=7,
        ),
    ),
    catchup=False,
    max_active_runs=2,
    tags=["airflow-3.3", "asset-fanout", "incident-response", "drift"],
) as weekly_telemetry_daily_diagnostic_fanout:

    @task(
        inlets=[WEEKLY_TELEMETRY_SNAPSHOT],
        retries=2,
        retry_policy=INCIDENT_RETRY_POLICY,
    )
    def evaluate_daily_diagnostic_partition(dag_run=None) -> dict[str, str | None]:
        return {
            "partition_key": dag_run.partition_key if dag_run else None,
            "telemetry_asset": WEEKLY_TELEMETRY_SNAPSHOT.uri,
            "diagnostic": "bounded_daily_root_cause",
        }

    evaluate_daily_diagnostic_partition()
