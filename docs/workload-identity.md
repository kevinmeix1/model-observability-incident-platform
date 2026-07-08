# Workload Identity and Secretless Access

This observability platform models production access without static telemetry, pager, or incident-store keys in pods. The telemetry collector, drift evaluator, and incident router each get a dedicated Kubernetes `ServiceAccount`, namespace-scoped RBAC, projected one-hour tokens, and a federated cloud role.

## Controls

- `kubernetes/workload-identity.yaml` disables default service account token automounting and documents projected token expectations.
- `SecretStore` and `ExternalSecret` examples synchronize pager and incident-store material with a 30 minute refresh window.
- Airflow diagnostic tasks pin evaluator service accounts rather than inheriting broad scheduler permissions.
- SPIFFE IDs document identities for collector, evaluator, and incident-router workloads.
- `.local/reports/identity_access_report.json` proves that token TTL, ExternalSecret refresh, RBAC scope, SPIFFE IDs, and static-key avoidance pass.

## Production Notes

Observability credentials are high blast-radius because they often touch logs, alerting, and incident state. Keep telemetry-read, drift-eval, and incident-write roles separate, and page if a workload mounts a static provider key or an ExternalSecret falls stale.

References: Kubernetes service account token projection, External Secrets Operator, SPIFFE/SPIRE, and Airflow KubernetesPodOperator service-account configuration.
