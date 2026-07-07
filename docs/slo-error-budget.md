# SLO And Error Budget Automation

The observability platform writes `reports/slo_error_budget.json` from reliability and drift checks.

It tracks:

- observed serving availability
- latency SLO health
- telemetry freshness
- drift signal health
- multi-window burn-rate policy
- rollout freeze and paging recommendations

Run it locally:

```bash
make demo
make slo-report
```

`kubernetes/slo-alerts.yaml` contains PrometheusRule examples for serving burn and telemetry freshness, plus a scheduled freeze-sync job that can feed release automation.
