# DRA Advanced Device Sharing For Observability

`make advanced-device-sharing` writes `.local/reports/advanced_device_sharing_plan.json` and pairs it with `kubernetes/dra-advanced-device-sharing.yaml`.

## What It Shows

- DRA prioritized device alternatives for embedding drift diagnostics.
- Partitionable devices for drift backlog review instead of whole-device reservations.
- Consumable capacity examples for bounded GPU memory during diagnostic bursts.
- Device binding conditions that delay scheduler binding until heavy monitor review devices are prepared.

## Production Notes

Observability should degrade gracefully. Prioritized alternatives attach the best available diagnostic evidence to an incident, but incident creation, paging, and rollout-freeze guidance remain CPU-runnable.

Partitionable devices and consumable capacity keep drift backlog review from starving fresh incidents. Binding conditions make diagnostic accelerator preparation explicit; a preparation failure becomes an incident evidence limitation instead of a silent monitor gap.

## References

- Kubernetes v1.36 DRA update: <https://kubernetes.io/blog/2026/05/07/kubernetes-v1-36-dra-136-updates/>
- Kubernetes Dynamic Resource Allocation: <https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/>
- Kubernetes DRA consumable capacity: <https://kubernetes.io/blog/2025/09/18/kubernetes-v1-34-dra-consumable-capacity/>
