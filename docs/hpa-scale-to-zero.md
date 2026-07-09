# HPA Scale To Zero

`make hpa-scale-zero` writes `.local/reports/hpa_scale_to_zero_plan.json`.

## What It Shows

- Kubernetes v1.36 `HPAScaleToZero` as an alpha, disabled-by-default feature gate.
- `autoscaling/v2` HorizontalPodAutoscaler objects with `minReplicas: 0`.
- Object and External wake metrics for drift diagnostics, incident evidence rendering, and retention replay.
- Protected replica floors for incident routing, rollout freezes, and alert dispatch.
- Cold-start guardrails that keep incident-control paths separate from elastic diagnostic workers.

## Production Notes

Observability platforms can waste capacity on idle diagnostic workers, but the incident-control path must stay warm. This project scales only backlog-driven evidence and drift workers to zero, while incident routing and rollout-freeze controllers remain available during high-burn events.

The dependency is the metrics adapter. If backlog metrics are missing while workers sit at zero replicas, the platform may look healthy while evidence generation is stalled. The manifest adds wakeup, missing-metric, and cold-start alerts.

## Senior Review Angle

This is a reliability-aware cost control. It demonstrates that scale-to-zero is appropriate for diagnostic fanout but not for safety controllers, and it documents the HPA feature-gate and Object/External metric constraints explicitly.

References:

- https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/
- https://kubernetes.io/docs/reference/kubernetes-api/autoscaling/horizontal-pod-autoscaler-v2/
- https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/
