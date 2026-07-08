# Topology-Aware Scheduling

`make topology-plan` writes `.local/reports/topology_placement_plan.json` and pairs it with `kubernetes/topology-aware-scheduling.yaml`.

## What It Shows

- Kueue `Topology` and topology-backed `ResourceFlavor` resources for diagnostics.
- Zone-spread telemetry collectors so freshness checks survive failure domains.
- Preferred rack-level topology for GPU embedding drift diagnostics.
- Required node spread for incident root-cause probes.
- CPU drift and incident fallbacks when topology-aware GPU diagnostics are pending.

## Production Notes

Observability placement has a different risk profile from training. Topology-aware GPU diagnostics can improve analysis quality, but they must not block paging, rollout freezes, or incident creation. The control plane therefore spreads collectors and root-cause probes while treating compact GPU placement as an optional enrichment.

References: Kueue Topology Aware Scheduling, Kubernetes topology spread constraints, Kueue AdmissionChecks, and Prometheus alerting practices.
