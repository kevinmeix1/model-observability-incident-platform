# KubeRay and Kueue

`make kuberay-plan` writes `.local/reports/kuberay_capacity_plan.json` and pairs it with `kubernetes/kuberay-kueue-workloads.yaml`.

## What It Shows

- Kueue-admitted `RayJob` fanout for root-cause analysis across models and checks.
- Optional GPU diagnostics for embedding drift that can be preempted.
- Retention/audit capacity kept outside the hot incident path.
- Airflow control-plane tasks that submit incident fanout and wait deferrably.
- Rollout freeze behavior when distributed diagnostics cannot run during high severity.

## Production Notes

Incident response needs speed, but it should not let diagnostics starve serving rollback or alert routing. This project models Ray as the distributed incident fanout layer, Kueue as the priority and quota gate, and Airflow as the control plane that records the decision trail.

References: Kueue RayJob integration, Ray KubeRay with Kueue, and RayJob gang-scheduling examples.
