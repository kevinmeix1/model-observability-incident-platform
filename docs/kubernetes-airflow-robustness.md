# Kubernetes And Airflow Robustness Layer

This repo now models observability as a scheduled reliability control plane.

## Airflow Features

- Model reliability DAG driven by prediction-log assets.
- Dynamic task mapping across models and check types.
- TaskGroups for telemetry preparation, parallel checks, and incident response.
- Branching based on severity.
- KubernetesPodOperator tasks for monitor execution.
- Deferrable KubernetesPodOperator settings for route waits and long-running checks.
- SLO budget and capacity TaskGroup before incident routing.
- Airflow KubernetesExecutor pod template with policy validation init container.

## Kubernetes Features

- Hourly CronJob for observability cycles.
- Kueue ResourceFlavor, ClusterQueue, LocalQueue, and WorkloadPriorityClass for reliability-check admission.
- ResourceQuota and LimitRange for namespace governance.
- PriorityClass for incident creation.
- Gateway API HTTPRoute for dashboard routing.
- ConfigMap-backed monitoring policy.
- RBAC Role/RoleBinding and restricted pod security posture.

## Why It Matters

Observability is more than charts. This repo now shows the production loop: scheduled checks, parallel analysis, incident dedupe, root-cause hints, and runbook-driven action.

The newest pass treats reliability checks as shared production workloads: checks are queue-admitted, prioritized, bounded by quota, and run through an Airflow SLO-budget step before incidents are routed.
