# Incident Evidence Volumes

Kubernetes image volumes let a diagnostic pod mount an OCI image or artifact as a read-only filesystem. In this project they package the context needed during model reliability incidents: reference windows, policy bundles, golden incident examples, and runbooks.

## Why This Matters

Incident response often fails because the diagnostic job, dashboard, and runbook are each reading mutable context from different places. Packaging incident evidence as digest-pinned OCI artifacts gives the on-call path a reproducible view of what policy, baseline, and runbook were used when a rollback or rollout freeze was recommended.

## Production Contract

- Kubernetes image volumes are stable in Kubernetes v1.36 and require a server at least v1.31 plus runtime support.
- Every evidence bundle is referenced by digest, not by `latest`.
- Bundles are mounted read-only; incident writes go to the incident store.
- Airflow verifies the evidence volumes before KubeRay incident fanout or rollback recommendations.
- The object-store evidence path stays available for clusters that do not yet support image volumes.
- Missing evidence preserves rollout freeze state instead of allowing automated repair.

## Airflow Integration

The reliability DAG pins its worker image and verifies the evidence bundle in the capacity phase:

```bash
kubectl apply -f kubernetes/incident-evidence-volumes.yaml
kubectl wait --for=condition=Complete job/observability-evidence-volume-smoke -n ml-observability --timeout=8m
```

Only after that smoke job passes should the DAG start expensive root-cause fanout, rollback recommendation, or dashboard publication.

## Failure Recovery

| Failure | Detection | Recovery |
| --- | --- | --- |
| Registry auth or pull failure | Diagnostic pod stuck before containers start | Keep rollout freeze and use the object-store evidence path. |
| Runtime lacks image-volume support | Kubelet or admission rejects `spec.volumes[*].image` | Use object-store downloads until nodes are upgraded. |
| Policy/runbook digest mismatch | Mounted digest differs from governance evidence | Block automated repair and rebuild evidence through the attested workflow. |
| High evidence cold-start latency | Diagnostic startup p95 exceeds incident budget | Warm nodes with the evidence CronJob before increasing fanout. |

## Interview Talking Points

- Why incident evidence needs immutability as much as model artifacts do.
- How read-only OCI evidence prevents runbook and policy drift during outages.
- Why a missing evidence bundle should preserve a rollout freeze.
- How this pattern complements object storage rather than replacing it everywhere.
- Why cold-start latency matters in an observability control plane.
