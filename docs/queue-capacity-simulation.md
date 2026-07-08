# Queue Capacity Simulation

The local queue simulator writes `.local/reports/queue_simulation.json`. It models Kueue-style admission for incident-critical checks, GPU diagnostics, dashboard refresh, retention maintenance, and Airflow pool slots.

## What It Demonstrates

- Incident-critical root-cause analysis can preempt retention compaction.
- GPU diagnostics are scarce but still lower priority than active incident response.
- Dashboard refresh remains admitted for incident commander context.
- Airflow pool slots reserve capacity for paging workflows.

## Current References

- Kueue ClusterQueue borrowing and cohorts: <https://kueue.sigs.k8s.io/docs/concepts/cluster_queue/>
- Kueue WorkloadPriorityClass: <https://kueue.sigs.k8s.io/docs/concepts/workload_priority_class/>
- Kueue preemption: <https://kueue.sigs.k8s.io/docs/concepts/preemption/>
- Airflow pools: <https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html>
- Kubernetes pod priority and preemption: <https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/>

Run `make queue-simulation` after `make demo` to regenerate only this report.
