# Disaster Recovery

This project includes a DR plan for observability state: telemetry baselines, incident records, dedupe fingerprints, alert routing, and burn-rate checks.

Run:

```bash
make dr-plan
```

The report is written to `.local/reports/disaster_recovery_plan.json`.

## Restore Order

1. Namespace and observability CRDs.
2. Telemetry baselines.
3. Incident records.
4. Alert routing.
5. Freshness and burn-rate checks.

Velero and snapshots restore infrastructure state, while incident exports preserve operational history and dedupe behavior.
