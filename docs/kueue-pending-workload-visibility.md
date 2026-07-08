# Kueue Pending Workload Visibility

`make pending-workload-visibility` writes `.local/reports/pending_workload_visibility_plan.json` and pairs it with `kubernetes/kueue-pending-workload-visibility.yaml`.

## What It Shows

- Kueue `VisibilityOnDemand` for ClusterQueue and LocalQueue pending workload queries.
- RBAC for `visibility.kueue.x-k8s.io` `clusterqueues/pendingworkloads` and `localqueues/pendingworkloads`.
- API Priority and Fairness setup via the Kueue release `visibility-apf.yaml`.
- Prometheus signals for admission wait time and pending requested resources.
- Queue triage actions for incident diagnostics, embedding drift, retention compaction, and rollout-freeze evidence.

## Production Notes

Observability control planes need to explain why incident diagnostics are delayed without turning every delay into a noisy "queue full" page. Pending-workload visibility gives the on-call a precise view: incident root-cause is first but waiting on on-demand CPU, drift GPU diagnostics are delayed, and retention compaction must stay queued instead of borrowing incident quota.

The demo attaches that queue snapshot to incident evidence so operators can decide whether to keep the rollout freeze, run a CPU drift fallback, or split low-priority retention work.

## References

- Kueue monitor pending workloads: <https://kueue.sigs.k8s.io/docs/tasks/manage/monitor_pending_workloads/>
- Kueue pending workloads on demand: <https://kueue.sigs.k8s.io/docs/tasks/manage/monitor_pending_workloads/pending_workloads_on_demand/>
- Kueue Prometheus metrics: <https://kueue.sigs.k8s.io/docs/reference/metrics/>
