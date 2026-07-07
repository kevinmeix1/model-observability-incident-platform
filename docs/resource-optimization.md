# Resource Optimization

This layer right-sizes the observability and incident-response plane. The key constraint is reliability: capacity changes must not hide incidents or delay freshness checks.

Run:

```bash
make optimize-resources
```

The report is written to `.local/reports/resource_optimization.json`.

## Decisions

- Keep VPA in `Off` mode so observability changes are reviewed before rollout.
- Reserve Airflow pool slots for incident creation before expensive drift reports.
- Scale collectors with memory and throughput pressure, not CPU alone.
- Keep alert thresholds stable while right-sizing to avoid confusing signal changes with system changes.

## References

Kubernetes requests and limits control scheduling and runtime enforcement. VPA provides recommendation bounds without automatic changes in `Off` mode. HPA behavior stabilization reduces replica flapping, while Airflow pools protect incident workflows from less urgent jobs.
