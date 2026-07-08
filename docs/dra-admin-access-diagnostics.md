# Observability DRA AdminAccess Diagnostics

`make admin-access-diagnostics` writes `.local/reports/admin_access_diagnostics_plan.json` and pairs it with `kubernetes/dra-admin-access-diagnostics.yaml`.

## What It Shows

- Kubernetes v1.36 DRA `AdminAccess` ResourceClaims in a namespace labeled `resource.kubernetes.io/admin-access: "true"`.
- Break-glass diagnostics for embedding drift checks, large monitor review, and incident root-cause probes.
- Least-privilege RBAC that separates privileged ResourceClaim creation from read-only observability workload inspection.
- Evidence capture for `ResourceClaim.status.devices`, Pod `allocatedResourcesStatus`, incident id, monitor name, and rollout freeze state.
- Cleanup deadlines and Prometheus alerts when privileged claims outlive their incident window.

## Production Notes

AdminAccess is evidence enrichment, not an incident gate. The incident pipeline should keep paging, incident creation, and rollout-freeze guidance CPU-runnable while GPU diagnostic evidence is gathered. The report deliberately treats AdminAccess output as an evidence quality signal so a degraded GPU monitor can annotate an incident without hiding it.

The diagnostic bundle should be attached to the incident log and dashboard so reviewers can see the exact relationship between monitor limitations, device health, and downstream action.

## References

- Kubernetes Dynamic Resource Allocation: <https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/>
- Kubernetes v1.36 release highlights: <https://github.com/kubernetes/sig-release/discussions/2958>
- KEP-5018 DRA Admin Access: <https://www.kubernetes.dev/resources/keps/5018/>
