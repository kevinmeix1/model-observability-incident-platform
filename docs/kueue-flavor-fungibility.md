# Kueue Flavor Fungibility

`make flavor-fungibility` writes `.local/reports/flavor_fungibility_plan.json` and pairs it with `kubernetes/kueue-flavor-fungibility.yaml`.

## What It Shows

- `ResourceFlavor` objects for on-demand incident CPU, spot maintenance CPU, reserved L4 GPU, and spot L4 GPU pools.
- `ClusterQueue.spec.flavorFungibility.whenCanBorrow: TryNextFlavor`.
- `ClusterQueue.spec.flavorFungibility.whenCanPreempt: TryNextFlavor`.
- Explicit `flavorFungibility.preference: BorrowingOverPreemption`.
- Different flavor order for incident diagnostics, embedding drift, and retention maintenance.

## Production Notes

Observability systems need spare capacity, but on-call diagnostics should not be preempted by retention or drift backlog. Flavor fungibility lets Kueue try another ResourceFlavor before it borrows quota or preempts admitted work.

This repo keeps incident diagnostics stability-first, lets embedding drift use GPU fallback, and keeps retention compaction spot-first. The result is more production-like than a static queue because it explains what should happen when one node pool is saturated or temporarily unavailable.

## References

- Kueue ClusterQueue: <https://kueue.sigs.k8s.io/docs/concepts/cluster_queue/>
- Kueue ResourceFlavor: <https://kueue.sigs.k8s.io/docs/concepts/resource_flavor/>
- Kueue FlavorFungibility API: <https://kueue.sigs.k8s.io/docs/reference/kueue.v1beta1/#flavorfungibility>
