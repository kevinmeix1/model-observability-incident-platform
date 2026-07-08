# Cost Observability and FinOps

`make cost-observability` writes `.local/reports/cost_observability_report.json` and validates the incident-platform cost-allocation contract.

## What It Shows

- OpenCost exporter metrics scraped by Prometheus every minute.
- Cost allocation by detector, check, incident route, severity, tenant, and dashboard.
- Separate budgets for telemetry ingestion, drift and quality checks, KubeRay root-cause fanout, dashboard publishing, and telemetry retention.
- Cost per high-severity incident detected as a unit-economics guardrail.
- Prometheus alerts for telemetry spend, incident fanout cost, idle diagnostic GPUs, retention growth, and missing allocation labels.
- The split between OpenCost allocation evidence and Kubernetes `ResourceQuota` or `LimitRange` admission controls.

## Production Notes

Observability platforms can become expensive while still looking reliable. The usual culprits are verbose traces, repeated drift checks, GPU root-cause diagnostics left on after an incident, stale dashboard publishers, and raw telemetry retention that outlives the operational need. Cost evidence should sit next to freshness, incident-creation latency, root-cause fanout, SLO burn, and provenance.

The label contract is intentionally incident-shaped. Every collector, checker, dashboard publisher, and diagnostic worker should carry detector, severity, tenant, and incident-route metadata so an operator can explain what the reliability system costs during normal windows and during pages.

## Current Research Basis

- OpenCost can run as a Prometheus metric exporter and expose allocation metrics without requiring the full UI.
- OpenCost requires Prometheus for metric scraping and storage.
- OpenCost generated metrics include CPU, RAM, GPU, node, PVC, and load balancer cost signals.
- Kubernetes `ResourceQuota` constrains namespace consumption, and `LimitRange` can supply default requests or limits that make quota enforcement practical.
