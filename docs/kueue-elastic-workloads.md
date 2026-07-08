# Kueue Elastic Workloads

This observability platform uses Elastic Workloads for incident-adjacent fanout, not for the first alert or incident creation path. The fast path still runs through scheduled checks, freshness gates, and alert routing. Kueue Workload Slices are used for expensive work that can scale up with spare quota and scale down when high-severity incidents need capacity.

## Workload Slices

- `incident-fanout-slice-a` expands root-cause analysis across affected models, cohorts, and upstream data assets.
- `drift-check-slice-b` replaces lower-priority drift backlog work so incident response and rollback freeze checks can reclaim quota.
- `gpu-diagnostic-slice-a` bursts expensive GPU diagnostics for embedding drift, segment attribution, and incident retrospectives.

Each slice carries `kueue.x-k8s.io/workload-slice-name`. The drift backlog replacement slice also carries `kueue.x-k8s.io/workload-slice-replacement-for` so operators can see which admitted slice is being contracted.

## JobSet Integration

Root-cause analysis and GPU diagnostics are modeled as JobSet workloads because incident fanout naturally breaks into many independent probes. Airflow owns the incident lifecycle and freeze decision, while Kueue owns quota admission and preemption behavior.

## Rollback Freeze Behavior

When a high-severity incident is detected, the platform should freeze risky rollouts before it spends quota on lower-priority checks. Replacement Workload Slices reclaim drift backlog capacity first, then keep incident root-cause analysis and dashboard publishing inside deadline windows.

## Production Notes

Enable `ElasticJobsViaWorkloadSlices` behind a progressive rollout. Alert on pending slices, replacement lag, and JobSet replica lag. In cloud deployments, place GPU diagnostic slices on separate node pools with cost labels so OpenCost reports can separate incident response from routine drift monitoring.
