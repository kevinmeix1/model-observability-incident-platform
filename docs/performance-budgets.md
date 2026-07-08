# Performance Budgets

The observability platform writes `.local/reports/performance_budget.json` to prove the reliability control plane can detect, deduplicate, route, and display incidents quickly. The demo may intentionally detect unhealthy model behavior; this budget checks whether the observability system itself is healthy.

## What Is Gated

- Diagnostic runtime for drift, latency, error, null-rate, and freshness checks.
- Incident creation latency.
- Failed-check to incident coverage.
- Alert routing latency.
- Incident dashboard render time.
- Presence of a reliability action.

## Production Mapping

- Kueue priority classes reserve capacity for incident-critical checks.
- KEDA ScaledJobs react to telemetry backlog while admission control protects the cluster.
- Prometheus histograms support p95 detection, incident creation, and notification latency.
- CI fails if the reliability platform cannot produce a clear action and evidence report.

## Current References

- Prometheus histogram practices: <https://prometheus.io/docs/practices/histograms/>
- KEDA Prometheus scaler: <https://keda.sh/docs/2.20/scalers/prometheus/>
- Airflow dynamic task mapping: <https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html>
- Kubernetes resource management: <https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/>

Run `make performance-budget` after `make demo` to regenerate only this evidence.
