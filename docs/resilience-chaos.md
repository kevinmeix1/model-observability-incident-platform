# Resilience and Chaos Drills

The observability platform includes Chaos Mesh examples for the monitoring plane itself. These drills check whether incidents, freshness checks, deduplication, and escalation still work when telemetry infrastructure degrades.

## Drills

- `collector_pod_kill`: kills one collector and expects scheduled checks plus incident dedupe to prevent alert storms.
- `prediction_log_delay`: injects telemetry ingestion latency and expects freshness checks to classify the issue as pipeline delay.
- `incident_worker_cpu_pressure`: adds CPU pressure to incident routing jobs and expects Kueue priority to preserve critical incident creation.

Run the local evidence generator:

```bash
make chaos-drill
```

Apply the cluster experiments after installing Chaos Mesh:

```bash
kubectl apply -f kubernetes/chaos-experiments.yaml
```

## Production Notes

- Chaos-test the observability plane separately from model serving so outages in monitoring do not hide serving regressions.
- Keep incident creation idempotent before running repeated scheduled drills.
- Assert both symptom classification and downstream impact analysis after each run.
- Use `concurrencyPolicy: Forbid` on recurring chaos schedules to keep incident timelines readable.

References: Chaos Mesh supports pod, network, stress, and scheduled experiments; Kubernetes disruption controls protect critical observability workloads during maintenance and drills.
