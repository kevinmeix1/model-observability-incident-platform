# Model Observability + Incident Response Platform

A production-style model reliability project that detects feature drift, prediction drift, serving SLO failures, freshness issues, and data quality problems, then creates idempotent incidents with severity, likely root cause, and next action guidance.

The default demo is local-first and dependency-light. The design maps cleanly to Evidently, Prometheus, OpenTelemetry, Grafana, PagerDuty, and warehouse-backed model monitoring.

![Model observability dashboard](docs/screenshots/dashboard.png)

## What This Demonstrates

- Reference and current telemetry windows
- Feature drift checks
- Prediction distribution drift checks
- Latency p95 and p99 tracking
- Error rate monitoring
- Freshness checks
- Data quality checks
- Idempotent incident creation
- Severity classification
- Likely root-cause hints
- Runbook-oriented next actions
- Dashboard for health checks, incidents, and feature shifts

## Architecture

```mermaid
flowchart LR
    A["Prediction logs"] --> B["Telemetry windows"]
    B --> C["Health checks"]
    C --> D["Observability report"]
    D --> E["Incident dedupe"]
    E --> F["Incident store"]
    F --> G["Root cause hints"]
    F --> H["Dashboard"]
    G --> I["Runbook action"]
```

## Quick Start

```bash
make demo
make test
```

Open the generated dashboard:

```bash
open .local/reports/model_observability_dashboard.html
```

## Checks

- `feature_drift`: compares current feature means to reference means
- `feature_drift PSI`: compares distribution shift across reference quantile buckets
- `prediction_drift`: compares current and reference score means
- `latency_slo`: validates p95 latency
- `error_rate`: validates serving failure rate
- `null_rate`: checks malformed telemetry
- `freshness`: checks telemetry recency

## Production-Grade Refinements

See [production-grade refinements](docs/production-grade-refinements.md) for the PSI drift, SLO, incident dedupe, root-cause, and runbook improvements.

For the latest reliability control-plane pass, see [advanced orchestration assessment](docs/advanced-orchestration-assessment.md).

For the Kubernetes/Airflow robustness layer, see [Kubernetes and Airflow robustness](docs/kubernetes-airflow-robustness.md).

For the operator-facing reliability planner, see [advanced reliability control plane](docs/control-plane-depth.md).

For the policy-as-code audit layer, see [security and governance](docs/security-governance.md).

For OpenTelemetry-style runtime traces, see [observability and tracing](docs/observability-tracing.md).

For controlled failure injection and recovery objectives, see [resilience and chaos drills](docs/resilience-chaos.md).

For workload right-sizing, HPA/VPA guardrails, and Airflow pool sizing, see [resource optimization](docs/resource-optimization.md).

For runtime network boundaries, mTLS, and allow-listed service flows, see [network security](docs/network-security.md).

For auditable environment promotion with Argo CD and Argo Rollouts, see [GitOps promotion](docs/gitops-promotion.md).

For backup schedules, restore order, and RPO/RTO evidence, see [disaster recovery](docs/disaster-recovery.md).

For reliability system cards, telemetry data cards, incident approval records, risk controls, and reproducibility hashes, see [governance evidence](docs/governance-evidence.md).

For model reliability SLOs, burn-rate alerts, and rollout-freeze automation, see [SLO and error budget automation](docs/slo-error-budget.md).

For EKS Auto Mode, Terraform, managed-service mappings, and portability notes, see [cloud migration](docs/cloud-migration.md).

For GitHub artifact attestations, SLSA provenance, Sigstore policy-controller admission, and checksum evidence, see [supply chain provenance](docs/supply-chain-provenance.md).

For an automated scan of advanced Airflow, Kubernetes, lineage, scaling, GitOps, and security controls, see [orchestration scorecard](docs/orchestration-scorecard.md).

For GPU ResourceFlavors, Dynamic Resource Allocation notes, MIG/time-slicing trade-offs, and accelerator quota planning, see [accelerator scheduling](docs/accelerator-scheduling.md).

## Incident Semantics

Incidents are deduplicated by a stable fingerprint derived from the failed check and observed signature. Running the same report repeatedly does not create duplicates. Each incident includes:

- incident ID
- severity
- check name
- observed value
- root cause hint
- next action
- status

## Production Mapping

| Local artifact | Production analogue |
| --- | --- |
| `.local/data/reference.csv` | warehouse baseline window |
| `.local/data/current.csv` | live serving telemetry window |
| `.local/reports/observability_report.json` | Evidently or custom monitoring report |
| `.local/incidents/incidents.jsonl` | incident management table |
| `contracts/observability_policy.yml` | monitoring policy as code |

## Interview Talking Points

- Why drift and latency need separate root-cause paths.
- How to avoid duplicate alerts during repeated monitor runs.
- How to choose thresholds for early warning versus paging.
- Why prediction drift without feature drift suggests model or calibration issues.
- How to connect model incidents to serving traces and upstream data changes.
