# Release Admission Control

This project writes `reports/release_admission_decision.json`, a fail-closed rollout-freeze record for model observability and incident response. It combines open incidents, reliability action, SLO burn, performance budgets, Kueue and Airflow queue safety, governance approval, and supply-chain provenance.

The controller is intentionally conservative. Active high-severity incidents or paging burn rates produce `freeze_rollouts_and_page`; queue pressure can produce `reserve_incident_diagnostics`; only a clean incident window admits observability control-plane changes.

## Production Shape

- Airflow freezes model promotion DAGs while the admission decision says `freeze_rollouts_and_page`.
- Kubernetes `ValidatingAdmissionPolicy` requires release-decision and evidence-sha annotations on collector, incident-router, and diagnostic workloads.
- Argo Rollouts analysis gates observability control-plane rollouts on incident coverage and telemetry freshness.
- Kueue priority reserves diagnostic capacity for root-cause jobs before low-risk retention or compaction work.

## Why This Is Senior-Level

Observability systems are part of the model release control plane. If they are unhealthy, the platform should not keep shipping models blindly. This artifact makes that relationship explicit and auditable: incidents can freeze rollouts, and the freeze is backed by the same evidence that operators see in the dashboard.

## Current References

- Kubernetes `ValidatingAdmissionPolicy`: https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
- Argo Rollouts analysis: https://argo-rollouts.readthedocs.io/en/stable/features/analysis/
- Airflow assets: https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html
- Kueue preemption: https://kueue.sigs.k8s.io/docs/concepts/preemption/
