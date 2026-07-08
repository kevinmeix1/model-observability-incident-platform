# Control Plane Diagnostics

`make control-plane-diagnostics` writes `.local/reports/control_plane_diagnostics_plan.json`.

## What It Shows

- Kubernetes v1.36 controller staleness mitigation for incident routing and rollout-freeze automation.
- Component `/statusz` and `/flagz` readiness for API server, controller manager, scheduler, and kubelet.
- PSI metrics for CPU, memory, and IO stall detection on observability nodes.
- native histogram readiness for high-resolution control-plane, incident, and telemetry latency metrics.
- Fail-closed behavior when incident, drift-diagnostic, or rollout-freeze controllers read stale cache state.

## Production Notes

Reliability automation can silently lower severity or lift a rollout freeze if it reconciles against stale Kubernetes state. This plan gives incident routing, drift diagnostics, and freeze controllers strict freshness budgets and requires direct API reads before resolving an incident or allowing promotion.

`/statusz` shows the component build and health. `/flagz` shows the effective flags after an upgrade. Together they make Kubernetes feature-gate drift visible before incident automation trusts new scheduling, routing, security, or metrics behavior.

## Senior Review Angle

This is the operator layer for model observability: it shows how the platform detects stale watches, feature-gate drift, node pressure, and metrics-cardinality risk before those issues corrupt root-cause analysis or rollout-freeze decisions.

References:

- https://kubernetes.io/blog/2026/04/28/kubernetes-v1-36-staleness-mitigation-for-controllers/
- https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/
- https://kubernetes.io/blog/2026/04/25/kubernetes-v1-36-psi-metrics/
