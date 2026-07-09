# Memory QoS Tiered Protection

`make memory-qos` writes `.local/reports/memory_qos_plan.json`.

## What It Shows

- Kubernetes v1.36 Memory QoS with `memoryReservationPolicy: TieredReservation`.
- cgroup v2 and kernel guardrails for observability node pools.
- `memory.min` hard protection for incident routing and rollout-freeze controllers.
- `memory.low` soft protection for drift diagnostics and evidence rendering.
- PSI and `memory.high` throttling alerts before resolving incidents or lifting freezes.

## Production Notes

Observability systems are dangerous when they fail silently under pressure. This plan protects incident routing and freeze enforcement first, then lets drift fanout and evidence rendering yield predictably when nodes are constrained.

The v1.36 update separates throttling from reservation. Enabling `MemoryQoS` turns on `memory.high` throttling, while `TieredReservation` opts into `memory.min` and `memory.low` protection.

## Senior Review Angle

This shows reliability judgment beyond dashboards: incident automation needs explicit node-level memory protection, PSI signals, cgroup v2 awareness, and criticality-based QoS rather than blanket resource inflation.

References:

- https://kubernetes.io/blog/2026/04/29/kubernetes-v1-36-memory-qos-tiered-protection/
- https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/
