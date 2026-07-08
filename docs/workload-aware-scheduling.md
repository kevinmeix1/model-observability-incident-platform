# Kubernetes Workload-Aware Scheduling

`make workload-aware-scheduling` writes `.local/reports/workload_aware_scheduling_plan.json`.

## What It Shows

- Kubernetes v1.36 `scheduling.k8s.io/v1alpha2` Workload and PodGroup readiness.
- `WorkloadWithJob` fixed-shape Indexed Job integration for incident root-cause fanout and rollout-freeze smoke jobs.
- PodGroup atomic gang scheduling with `schedulingPolicy.gang.minCount`.
- Topology constraints for zone, rack, or host placement.
- Workload-aware preemption using PodGroup `priority` and `disruptionMode: PodGroup`.
- DRA ResourceClaim sharing at PodGroup scope for diagnostic workloads.
- A fresh-incident boundary that keeps ingestion, paging, and rollout-freeze paths outside scarce diagnostic gangs.

## Production Notes

Workload-Aware Scheduling is alpha in Kubernetes v1.36 and should be treated as readiness evidence. This repo uses it for incident root-cause fanout, GPU drift backlog diagnostics, and rollout-freeze smoke checks where all-or-nothing scheduling improves evidence quality.

Fresh incident ingestion, paging, and freeze decisions remain on stable scheduling paths. Heavy diagnostic gangs can wait for quota without blocking alert creation or rollback guidance.

## Senior Review Angle

This demonstrates that incident diagnostics are scheduled as coherent workloads while the urgent response path remains independent. The report connects Airflow incident gates, Kueue priority, PodGroup scheduling, DRA ResourceClaims, rollout-freeze evidence, and recovery guidance.

References:

- https://kubernetes.io/blog/2026/05/13/kubernetes-v1-36-advancing-workload-aware-scheduling/
- https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/
- https://kubernetes.io/blog/2026/05/07/kubernetes-v1-36-dra-136-updates/
