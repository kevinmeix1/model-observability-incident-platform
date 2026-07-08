# Airflow Asset Partitioning

`make asset-partitioning-plan` writes `.local/reports/asset_partitioning_plan.json` and pairs it with the partition-aware examples inside `airflow/dags/model_reliability_control_plane_dag.py`.

## What It Shows

- Airflow 3.2 asset partitioning for telemetry windows, incident root-cause fanout, evidence bundles, and rollout-freeze decisions.
- `CronPartitionTimetable` for scheduled prediction-log window partitions.
- `PartitionedAssetTimetable` and `StartOfHourMapper` for aligned telemetry, policy, evidence, incident, and route-generation partitions.
- `dag_run.partition_key` captured with incident id, incident fingerprint, policy digest, evidence bundle digest, route generation, dashboard evidence, and OpenLineage facets.
- scheduler-managed partition backfills instead of replaying every reliability-control DAG step.

## Production Notes

Observability systems become risky when one stale telemetry window causes a broad incident replay. Partitioned assets keep the unit of action small: one model window, one incident fingerprint, one evidence bundle digest, and one route generation.

That is useful portfolio signal because incident tooling should be operationally conservative. The project shows how to replay root-cause evidence or rollout-freeze decisions without mutating unrelated incidents, clearing dedupe state, or hiding active alerts.

## References

- Airflow 3.2 release announcement: <https://airflow.apache.org/blog/airflow-3.2.0/>
- Airflow release notes: <https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html>
- Airflow assets: <https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html>
