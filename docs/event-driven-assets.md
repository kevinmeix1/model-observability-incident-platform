# Event-Driven Assets

`make event-driven-assets` writes `.local/reports/event_driven_assets_plan.json`.

## What It Shows

- Airflow 3 event-driven scheduling for prediction log windows, manual incident replay, and observability policy changes.
- `AssetWatcher` contracts for telemetry queues, incident router webhooks, and policy-as-code updates.
- `BaseEventTrigger` compatibility so reliability checks do not accidentally reschedule in loops.
- `shared_stream_key` planning so diagnostics, repair automation, and dashboard publishers can share upstream polling.
- conditional asset expression: `(PREDICTION_LOGS | MANUAL_INCIDENT_REPLAY) & OBSERVABILITY_POLICY`.
- `AssetAlias` usage for runtime incident evidence bundle URIs and dashboard links.
- Queued asset event inspection and deletion steps for stale telemetry windows and incident replays.

## Production Notes

Prediction logs should trigger diagnostics quickly, but diagnostics should still run under a known policy digest. A manual replay can bypass waiting for a fresh telemetry window, yet it still requires the same policy asset so incident response does not drift from monitoring rules.

Watcher lag is an alerting SLO. If telemetry or incident-router events are delayed, the platform should page before stale signals create or suppress a rollout-freeze recommendation.

## References

- Airflow event-driven scheduling: <https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/event-scheduling.html>
- Airflow asset-aware scheduling: <https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/asset-scheduling.html>
- Airflow asset definitions and AssetAlias: <https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html>
