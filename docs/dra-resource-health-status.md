# DRA Resource Health Status For Observability

`make resource-health-status` writes `.local/reports/resource_health_status_plan.json` and pairs it with `kubernetes/dra-resource-health-status.yaml`.

## What It Shows

- Kubernetes v1.36 `ResourceHealthStatus` for DRA device health in Pod status.
- `ResourceClaim` `status.devices` as companion evidence for embedding drift and large monitor review claims.
- Kubelet `PodResourcesLister` and `DynamicResource` telemetry as the runtime cross-check.
- `DeviceTaintRule` quarantine for unhealthy diagnostic GPUs.
- Incident behavior when GPU-backed diagnostics are `Unhealthy` or `Unknown`.

## Production Notes

Model reliability systems should not make incident creation depend on optional accelerator diagnostics. This runbook inspects `status.containerStatuses[*].allocatedResourcesStatus`, compares it with `ResourceClaim.status.devices`, and correlates the claim with kubelet PodResourcesLister telemetry before deciding whether a GPU-backed monitor result is trustworthy.

If diagnostic devices degrade, the platform keeps CPU root-cause probes, paging, and rollout-freeze guidance live. The incident is annotated with the diagnostic limitation, CPU PSI-only drift checks continue, and the unhealthy device is quarantined before another drift workload lands on it.

## References

- Kubernetes Dynamic Resource Allocation: <https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/>
- Kubernetes v1.36 DRA update: <https://kubernetes.io/blog/2026/05/07/kubernetes-v1-36-dra-136-updates/>
- Kubernetes v1.36 release highlights: <https://github.com/kubernetes/sig-release/discussions/2958>
