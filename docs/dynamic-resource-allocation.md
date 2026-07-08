# Dynamic Resource Allocation

`make device-plan` writes `.local/reports/device_allocation_plan.json` and pairs it with `kubernetes/dynamic-resource-allocation.yaml`.

## What It Shows

- Kubernetes `DeviceClass` and `ResourceClaimTemplate` resources for GPU-backed diagnostics.
- Kueue admission coupling for drift checks and incident-critical root-cause probes.
- Time-sliced L4 claims for embedding drift checks.
- MIG claims for large monitor review windows.
- CPU fallback for incident creation, paging, and rollback recommendations.

## Production Notes

Observability workloads are unusual because they protect production systems but can also consume the same scarce accelerators as training and serving. This project keeps incident routing CPU-runnable, uses DRA only for richer diagnostics, and treats pending `ResourceClaim` status as a signal to degrade gracefully instead of suppressing an incident.

Use time-slicing for low-risk embedding comparisons. Use MIG for monitor jobs where memory isolation matters. Keep the root-cause path on CPU so a bad accelerator pool cannot blind the incident workflow.

References: Kubernetes DRA docs, Kueue workload admission docs, NVIDIA GPU Operator sharing docs, and Prometheus alerting practices.
