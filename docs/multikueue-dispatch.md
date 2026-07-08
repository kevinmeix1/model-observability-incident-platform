# MultiKueue Incident Dispatch

`make multikueue-dispatch` writes `.local/reports/multikueue_dispatch_plan.json` and pairs it with `kubernetes/multikueue-dispatch.yaml`.

This project uses Kueue MultiKueue for cross-cluster incident diagnostics. The manager cluster keeps the incident control plane local, while worker clusters run fresh root-cause probes, lineage impact expansion, repair backfills, and optional GPU drift investigations.

## Operating Model

- Airflow submits finite incident diagnostic Jobs to the manager cluster.
- The manager reserves Kueue quota, then delegates the Workload through the `kueue.x-k8s.io/multikueue` admission check.
- Worker clusters mirror the namespace, LocalQueue, incident service accounts, alert-routing secrets, and image policy.
- `status.nominatedClusterNames` is watched while a Workload is still being considered by worker clusters.
- `status.clusterName` becomes the required evidence that a worker actually admitted the diagnostic.
- Remote Jobs are linked back to the selected Workload with `kueue.x-k8s.io/prebuilt-workload-name`.
- Repair automation and rollout unfreeze decisions stay frozen until the incident diagnostics have dispatch evidence.

## Incident Priority

The fresh incident diagnostics path has priority over historical repair and lineage backfills. Backfills are useful, but they should never consume the only worker capacity while a customer-visible freshness, drift, or serving incident is waiting for root-cause evidence.

GPU drift investigations are best-effort. If the GPU worker is unavailable, the platform publishes a CPU root-cause summary, marks GPU evidence incomplete, and keeps the incident open for follow-up.

## Failure Recovery

If dispatch stalls, page the reliability owner, inspect Kueue Workload status, and keep rollouts frozen. For high-severity incidents, use the faster AllAtOnce dispatch mode. For routine repair backfills, use Incremental dispatch to avoid over-dispatching work that worker clusters are unlikely to admit.

If a backfill starves the incident path, preempt the backfill and rerun the fresh diagnostic wave. If no worker writes `status.clusterName` inside the triage SLO, repair automation must remain frozen because the platform lacks evidence that the diagnostic actually ran.

## References

- Kueue MultiKueue concept: <https://kueue.sigs.k8s.io/docs/concepts/multikueue/>
- MultiKueue setup: <https://kueue.sigs.k8s.io/docs/tasks/manage/setup_multikueue/>
- Kubernetes Job in Multi-Cluster: <https://kueue.sigs.k8s.io/docs/tasks/run/multikueue/job/>
- Kueue metrics: <https://kueue.sigs.k8s.io/docs/reference/metrics/>
