# Airflow Deadline Alerts

`make deadline-alerts-plan` writes `.local/reports/deadline_alert_plan.json` and documents the Airflow 3 Deadline Alerts used by the observability incident control plane.

## What It Shows

- Deadline Alerts for telemetry freshness, incident creation latency, root-cause fanout, and dashboard publishing.
- Page-grade deadlines for freshness and incident creation, because stale checks or slow incident records can delay rollback decisions.
- Ticket-grade deadlines for diagnostic fanout and dashboard publishing, where the system should keep operating from last-known-good evidence while recovery continues.
- Bounded callback execution with `AIRFLOW__CALLBACKS__CALLBACK_EXECUTION_TIMEOUT=300`.
- Idempotent incident dedupe with a `dag_id:run_id:deadline_policy` key.
- Explicit callback contracts with receiver, owner, retry policy, bounded payload fields, and allowed side effects.

## Callback Contract

Deadline callbacks are intentionally small and auditable. The generated plan records the receiver, owner, dedupe key, retry policy, payload fields, and allowed side effect for each callback. A callback may page, notify, open or update an incident, or request a last-known-good publish task. It must not directly mutate rollout freeze state, run remediation, or include raw telemetry and prediction bodies.

## Production Notes

Airflow 3 Deadline Alerts replace the legacy Airflow 2 SLA callback pattern. The portfolio pattern here keeps the alert callback small: it opens or updates an incident, records the deadline policy, and points the operator at the next action. Remediation still runs through normal idempotent tasks, Airflow pools, and Kueue-admitted Kubernetes workloads.

Custom references matter for observability because the interesting clocks are not always the DAG run start time. Failed-check detection, incident creation, root-cause fanout, and dashboard publish timestamps each describe a different reliability promise. Treating those as separate deadlines makes the runbook sharper during serving incidents.
