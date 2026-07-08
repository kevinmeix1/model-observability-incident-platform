# Observability In-Place Pod Resize Controls

`make inplace-resize-plan` writes `.local/reports/inplace_resize_plan.json` and pairs it with `kubernetes/inplace-pod-resize.yaml`.

## What It Shows

- Kubernetes v1.35 stable in-place CPU and memory resizing through the `pods/resize` subresource.
- Kubernetes v1.36 beta in-place vertical scaling for pod-level resources through `spec.resources`.
- Incident-safe resize policies for embedding drift checks, root-cause fanout, and dashboard publishing.
- VPA `InPlaceOrRecreate` wiring for monitor resource recommendations.
- Alerts for `PodResizePending` and `PodResizeInProgress` so incident automation does not confuse resource transition with recovery.

## Production Notes

Observability workloads should resize without muting incident signals. CPU boosts can keep drift monitors fresh during incident spikes, and pod-level resource resizing can accelerate root-cause fanout, but both states must be visible in the incident log. `PodResizePending` means capacity is not yet admitted; `PodResizeInProgress` means the node accepted the resize but cgroups have not fully converged.

The demo treats resize as response acceleration, not incident resolution. It keeps paging, incident creation, and rollout-freeze guidance live while resources change.

## References

- Kubernetes v1.35 in-place Pod Resize GA: <https://kubernetes.io/blog/2025/12/19/kubernetes-v1-35-in-place-pod-resize-ga/>
- Kubernetes v1.36 pod-level resource resize beta: <https://kubernetes.io/blog/2026/04/30/kubernetes-v1-36-inplace-pod-level-resources-beta/>
- Kubernetes resize container resources task: <https://kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/>
