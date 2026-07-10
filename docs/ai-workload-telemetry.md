# AI Workload Telemetry Readiness

`make demo` emits `reports/ai_workload_telemetry_plan.json`, a reliability
contract that maps drift evaluation, incident root-cause workers, and dashboard
publishing to resource signals, telemetry fields, SLOs, and recovery actions.

This makes the observability project feel less like a passive dashboard and
more like a control plane: incidents, release freezes, notifications, and
last-known-good dashboard publishing are all tied to explicit evidence.

Current practice reflected here:
- Airflow asset events trigger drift windows and downstream incident workflows.
- Kubernetes pod-level resource pressure, Kueue priority, and DRA health explain incident scheduling.
- OpenTelemetry attributes are allow-listed for model, incident, and root-cause context.
- Dashboard publishing is treated as an SLO-protected runtime workload.
