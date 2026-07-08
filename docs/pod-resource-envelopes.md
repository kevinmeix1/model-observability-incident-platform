# Pod Resource Envelopes

`make pod-resource-envelopes` writes `.local/reports/pod_resource_envelope_plan.json` and pairs it with `kubernetes/pod-resource-envelopes.yaml`.

## What It Shows

- Kubernetes `PodLevelResources` with pod-level `spec.resources` for log compaction, root-cause fanout, and dashboard publishing pods.
- Stable Pod Scheduling Readiness through `schedulingGates`.
- Gate removal only after telemetry windows, incident evidence volumes, Kueue admission, policy bundle digests, and rollout-freeze state are verified.
- Scheduler observability with `scheduler_pending_pods{queue="gated"}`.
- Dynamic Resource Allocation guardrails so GPU diagnostic jobs fit inside the pod-level envelope.

## Production Notes

Incident systems should not let diagnostic fanout overwhelm the scheduler while evidence bundles, telemetry windows, or policy digests are still being produced. Scheduling gates keep the pods auditable but out of normal scheduling until prerequisites are real.

Pod-level resources make evidence sidecars and root-cause workers easier to budget as one envelope. Use `PodLevelResourceManagers` when CPUManager, MemoryManager, or TopologyManager alignment matters for latency-sensitive incident probes or GPU diagnostics.

## References

- Kubernetes pod-level resources: <https://kubernetes.io/docs/tasks/configure-pod-container/assign-pod-level-resources/>
- Kubernetes Pod Scheduling Readiness: <https://kubernetes.io/docs/concepts/scheduling-eviction/pod-scheduling-readiness/>
- Kubernetes Dynamic Resource Allocation: <https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/>
