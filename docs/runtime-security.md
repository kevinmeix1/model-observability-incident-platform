# Runtime Security

`make runtime-security` writes `.local/reports/runtime_security_plan.json`.

## What It Shows

- Kubernetes v1.36 user namespaces GA readiness with `pod.spec.hostUsers: false`.
- Runtime prerequisites for user namespaces: Linux 6.3+, idmap-capable filesystems, containerd 2.0+ or CRI-O 1.25+, and runc 1.2+ or crun 1.13+.
- Kubernetes v1.36 fine-grained kubelet authorization (`KubeletFineGrainedAuthz`) using `nodes/metrics`, `nodes/stats`, `nodes/healthz`, `nodes/log`, and `nodes/pods`.
- A policy example that blocks new observability telemetry roles from granting broad `nodes/proxy`.
- Reduced blast radius for incident routers, telemetry readers, and rollout-freeze smoke checks.

## Production Notes

User namespaces let incident and diagnostic containers keep container-root compatibility where needed while mapping the process to an unprivileged host UID. That reduces node impact if a diagnostic worker is compromised during a high-pressure incident.

Fine-grained kubelet authorization removes the old pattern where observability agents needed `nodes/proxy` just to read kubelet metrics, health, or logs. The manifest grants only the kubelet subresources required for observability telemetry and leaves privileged kubelet access as an audited break-glass path.

## Senior Review Angle

This shows that incident-response security is part of the reliability control plane. It links incident routing, telemetry, rollout-freeze smoke, RBAC, admission policy, and node-pool readiness instead of treating runtime isolation as a separate platform concern.

References:

- https://kubernetes.io/docs/concepts/workloads/pods/user-namespaces/
- https://kubernetes.io/docs/tasks/configure-pod-container/user-namespaces/
- https://kubernetes.io/blog/2026/04/24/kubernetes-v1-36-fine-grained-kubelet-authorization-ga/
- https://kubernetes.io/blog/2026/04/23/kubernetes-v1-36-userns-ga/
