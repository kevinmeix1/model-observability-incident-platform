# Airflow Multi-Team Readiness

`make multi-team-readiness` writes `.local/reports/multi_team_readiness_plan.json`.

## What It Shows

- `core.multi_team = True` in the Airflow preview profile.
- DAG Bundle `team_name` ownership for model reliability and incident DAGs.
- Team-scoped pools with `airflow pools set ... --team-name`.
- Team-scoped variables and connections using `AIRFLOW_VAR__ML_OBSERVABILITY___...` and `AIRFLOW_CONN__ML_OBSERVABILITY___...`.
- Team-specific executor routing and `airflow triggerer --team-name ml-observability`.
- `AssetAccessControl` with `producer_teams`, `consumer_teams`, and `allow_global=False` for cross-team incident assets.

## Production Notes

Airflow multi-team support is still preview/experimental, so this project treats it as readiness evidence rather than a required local runtime. In production, create `ml-observability` before DAG bundle sync, run a team triggerer for deferrable telemetry freshness and incident sensors, and keep alert routing, incident fanout, and dashboard publication scoped to the observability team.

This is logical/resource isolation inside one Airflow deployment. For strict incident-data boundaries, use separate Airflow deployments, separate metadata databases, and explicit cross-team incident-summary APIs.

## Example Bootstrap

```bash
airflow teams create ml-observability
airflow pools set observability_pool 10 "Incident detection and root-cause pool" --team-name ml-observability
airflow pools set incident_publish_pool 4 "Dashboard and alert publish pool" --team-name ml-observability
airflow triggerer --team-name ml-observability
```

## Asset Filtering Contract

```python
from airflow.sdk import Asset
from airflow.sdk.definitions.asset import AssetAccessControl

incident_window_asset = Asset(
    "incident://model-observability/root-cause/window",
    access_control=AssetAccessControl(
        producer_teams={"ml-observability"},
        consumer_teams={"ml-platform", "ml-serving"},
        allow_global=False,
    ),
)
```

## Senior Review Angle

The report shows how telemetry windows, drift checks, incident root cause, and dashboard publication can be owned by an observability team without sending raw incident events to every Airflow team. It keeps the feature-status caveat explicit so the repo reads like production planning rather than brochureware.

References:

- https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/multi-team.html
- https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html
- https://airflow.apache.org/blog/airflow-3.2.0/
