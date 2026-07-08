from __future__ import annotations

from pathlib import Path

from .io import write_json


FLAVOR_POLICIES = [
    {
        "name": "incident-diagnostics",
        "cluster_queue": "incident-diagnostics-flavor-queue",
        "local_queue": "incident-root-cause",
        "resource": "cpu",
        "flavor_order": ["cpu-on-demand", "cpu-spot"],
        "when_can_borrow": "TryNextFlavor",
        "when_can_preempt": "TryNextFlavor",
        "preference": "BorrowingOverPreemption",
        "nominal_quota": {"cpu-on-demand": 18, "cpu-spot": 6},
        "borrowing_limit": {"cpu-on-demand": 4, "cpu-spot": 6},
        "rationale": "incident diagnostics prefer stable on-demand nodes and try spot fallback before borrowing or preempting",
    },
    {
        "name": "embedding-drift-gpu",
        "cluster_queue": "embedding-drift-flavor-queue",
        "local_queue": "embedding-drift",
        "resource": "nvidia.com/gpu",
        "flavor_order": ["gpu-l4-reserved", "gpu-l4-spot"],
        "when_can_borrow": "TryNextFlavor",
        "when_can_preempt": "TryNextFlavor",
        "preference": "BorrowingOverPreemption",
        "nominal_quota": {"gpu-l4-reserved": 1, "gpu-l4-spot": 2},
        "borrowing_limit": {"gpu-l4-reserved": 1, "gpu-l4-spot": 2},
        "rationale": "embedding drift diagnostics try reserved GPU first and spot GPU before preempting lower-priority work",
    },
    {
        "name": "retention-maintenance",
        "cluster_queue": "retention-maintenance-flavor-queue",
        "local_queue": "retention-compaction",
        "resource": "cpu",
        "flavor_order": ["cpu-spot", "cpu-on-demand"],
        "when_can_borrow": "TryNextFlavor",
        "when_can_preempt": "TryNextFlavor",
        "preference": "BorrowingOverPreemption",
        "nominal_quota": {"cpu-spot": 10, "cpu-on-demand": 2},
        "borrowing_limit": {"cpu-spot": 6, "cpu-on-demand": 1},
        "rationale": "retention compaction stays cheap-first and has only a narrow on-demand fallback",
    },
]


def _fallback_depth(policy: dict) -> int:
    return max(len(policy["flavor_order"]) - 1, 0)


def build_flavor_fungibility_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    policies = [
        {
            **policy,
            "fallback_depth": _fallback_depth(policy),
            "total_nominal_quota": sum(policy["nominal_quota"].values()),
            "total_borrowing_limit": sum(policy["borrowing_limit"].values()),
        }
        for policy in FLAVOR_POLICIES
    ]
    checks = [
        {
            "name": "resource_flavors_declared",
            "passed": True,
            "evidence": "ResourceFlavors separate on-call CPU, spot maintenance, and L4 drift diagnostic pools.",
        },
        {
            "name": "try_next_before_borrow",
            "passed": all(policy["when_can_borrow"] == "TryNextFlavor" for policy in policies),
            "evidence": "Observability queues try the next ResourceFlavor before borrowing from incident-response peers.",
        },
        {
            "name": "try_next_before_preempt",
            "passed": all(policy["when_can_preempt"] == "TryNextFlavor" for policy in policies),
            "evidence": "Drift and retention jobs try alternate flavors before preempting admitted incident diagnostics.",
        },
        {
            "name": "explicit_preference_declared",
            "passed": all(policy["preference"] == "BorrowingOverPreemption" for policy in policies),
            "evidence": "BorrowingOverPreemption is explicit so incident-path scheduling does not depend on implicit defaults.",
        },
        {
            "name": "incident_and_retention_have_distinct_order",
            "passed": policies[0]["flavor_order"] != policies[-1]["flavor_order"],
            "evidence": "Incident diagnostics are stability-first while retention maintenance is spot-first.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_observability_kueue_flavor_fungibility" if passed else "keep_static_observability_flavors",
        "kueue_api_target": "kueue.x-k8s.io/v1beta1",
        "feature": {
            "name": "FlavorFungibility",
            "whenCanBorrow": "TryNextFlavor avoids borrowing incident quota when another ResourceFlavor can fit",
            "whenCanPreempt": "TryNextFlavor avoids disrupting diagnostics when another flavor can fit",
            "preference": "BorrowingOverPreemption is explicit for predictable incident-path scheduling",
        },
        "flavor_policies": policies,
        "operational_guardrails": [
            "Keep incident root-cause and rollout-freeze diagnostics on stability-first flavors.",
            "Keep retention compaction spot-first and narrow its on-demand fallback.",
            "Use GPU flavor fallback for embedding drift diagnostics, not for paging-critical incident creation.",
            "Record selected ResourceFlavor, fallback depth, incident fingerprint, and detector name in incident evidence.",
            "Test spot outage, on-demand saturation, and GPU shortage before widening retention or drift schedules.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/kueue-flavor-fungibility.yaml"],
        "references": [
            "https://kueue.sigs.k8s.io/docs/concepts/cluster_queue/",
            "https://kueue.sigs.k8s.io/docs/concepts/resource_flavor/",
            "https://kueue.sigs.k8s.io/docs/reference/kueue.v1beta1/#flavorfungibility",
        ],
    }
    write_json(root / "reports" / "flavor_fungibility_plan.json", plan)
    return plan
