# Suspended Job Resource Mutation

`make suspended-job-resources` writes `.local/reports/suspended_job_resources_plan.json`.

## What It Shows

- Kubernetes v1.36 `MutablePodResourcesForSuspendedJobs` beta behavior.
- Incident diagnostic resource patching before a Job is unsuspended.
- CPU, memory, GPU, and extended resource request changes on suspended Jobs.
- A hard boundary that active incident routers and rollout-freeze checks use in-place resize or replacement instead.
- Admission and alert guardrails around `spec.suspend: true`.

## Production Notes

This pattern fits an observability control plane that creates root-cause, drift,
or retention replay Jobs in a suspended state while it gathers incident priority,
evidence bundle digests, Kueue quota snapshots, and Airflow pool capacity. The
queue controller can right-size the Job before starting Pods, which avoids
wasting scarce CPU or GPU quota during incidents.

This is intentionally not an active-Pod resize feature. Once a Job is running,
use in-place resize where appropriate or create a replacement Job with a new
template.

## Senior Review Angle

This shows the distinction between queued diagnostic work and active incident
response. The control plane can mutate resource requests while work is still
suspended, but it protects active routing and rollout-freeze Jobs from unsafe
template rewrites.

References:

- https://kubernetes.io/blog/2026/04/27/kubernetes-v1-36-mutable-pod-resources-for-suspended-jobs/
- https://kubernetes.io/docs/concepts/workloads/controllers/job/
