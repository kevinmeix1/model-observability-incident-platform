# Accelerator Scheduling

`make accelerator-plan` writes `.local/reports/accelerator_capacity_plan.json` and pairs it with `kubernetes/accelerator-scheduling.yaml`.

The design separates CPU burst capacity, shared L4 GPU capacity, and isolated A100 MIG capacity. Kueue ResourceFlavors model the quota boundary, while the ResourceClaimTemplate sketches the newer Kubernetes Dynamic Resource Allocation path for device-specific claims.

## Production Notes

- Keep Airflow incident pools below Kueue GPU quota so urgent monitor work remains schedulable.
- Use NVIDIA GPU Operator time-slicing only for low-risk non-isolated diagnostics.
- Use MIG when memory and fault isolation matter more than raw utilization.
- Keep most incident workflows CPU-first; reserve GPUs for drift probes or large-model monitor jobs that need them.

## Research Basis

- Kubernetes Dynamic Resource Allocation: https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/
- Kueue ResourceFlavors: https://kueue.sigs.k8s.io/docs/concepts/resource_flavor/
- KServe multi-node and multi-GPU inference: https://kserve.github.io/website/docs/model-serving/generative-inference/multi-node
- NVIDIA GPU Operator sharing: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html
