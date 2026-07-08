# Multi-Tenant Fairness

The demo writes `reports/tenancy_fairness_report.json`, which models incident response, drift monitoring, and retention maintenance tenants. The goal is to protect on-call diagnostics from lower-priority telemetry maintenance work.

## Controls

- `ResourceQuota` and `LimitRange` keep observability jobs within namespace budgets.
- Kueue `Cohort` and `ClusterQueue` resources let drift monitors borrow spare capacity while incident diagnostics keep priority.
- Airflow pools reserve incident-response slots before retention compaction runs.
- Cost-center labels support chargeback for telemetry-heavy workloads.
- Default-deny `NetworkPolicy` blocks maintenance jobs from incident routing services.

## References

- Kubernetes multi-tenancy: https://kubernetes.io/docs/concepts/security/multi-tenancy/
- Kubernetes ResourceQuota: https://kubernetes.io/docs/concepts/policy/resource-quotas/
- Kueue Cohorts: https://kueue.sigs.k8s.io/docs/concepts/cohort/
- Airflow Pools: https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html
