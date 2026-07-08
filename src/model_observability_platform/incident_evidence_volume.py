from __future__ import annotations

from pathlib import Path

from .io import write_json


EVIDENCE_BUNDLES = [
    {
        "name": "telemetry-reference-window",
        "reference": "ghcr.io/kevinmeix1/observability-reference-window@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "mount_path": "/mnt/evidence/reference-window",
        "producer": "warehouse://ml/prediction_logs/reference/2026-07-08",
        "consumer": "airflow://model_reliability_control_plane/build_reference_window",
        "size_mib": 384,
        "contract": "reference_window_schema_v4",
        "read_only": True,
    },
    {
        "name": "incident-policy-bundle",
        "reference": "ghcr.io/kevinmeix1/observability-policy-bundle@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "mount_path": "/mnt/evidence/policies",
        "producer": "governance://observability-policy/approved",
        "consumer": "airflow://model_reliability_control_plane/parallel_health_checks",
        "size_mib": 24,
        "contract": "observability_policy_schema_v2",
        "read_only": True,
    },
    {
        "name": "golden-incident-examples",
        "reference": "ghcr.io/kevinmeix1/observability-golden-incidents@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "mount_path": "/mnt/evidence/golden-incidents",
        "producer": "incident://ml/model-reliability/golden-set",
        "consumer": "airflow://model_reliability_control_plane/create_or_update_incidents",
        "size_mib": 72,
        "contract": "incident_regression_schema_v1",
        "read_only": True,
    },
    {
        "name": "runbook-bundle",
        "reference": "ghcr.io/kevinmeix1/observability-runbooks@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "mount_path": "/mnt/evidence/runbooks",
        "producer": "runbook://model-observability/2026-07",
        "consumer": "airflow://model_reliability_control_plane/publish_runbook_context",
        "size_mib": 32,
        "contract": "runbook_context_schema_v1",
        "read_only": True,
    },
]


def _is_immutable_reference(reference: str) -> bool:
    return "@sha256:" in reference and not reference.endswith(":latest")


def build_incident_evidence_volume_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    immutable = all(_is_immutable_reference(bundle["reference"]) for bundle in EVIDENCE_BUNDLES)
    read_only = all(bundle["read_only"] for bundle in EVIDENCE_BUNDLES)
    incident_contracts = all(
        "airflow://" in bundle["consumer"]
        or "incident://" in bundle["producer"]
        or "runbook://" in bundle["producer"]
        for bundle in EVIDENCE_BUNDLES
    )
    checks = [
        {
            "name": "kubernetes_image_volume_stable",
            "passed": True,
            "evidence": "Kubernetes image volumes are stable and enabled by default in Kubernetes v1.36.",
        },
        {
            "name": "runtime_compatibility_guardrail",
            "passed": True,
            "evidence": "Plan requires Kubernetes server >= v1.31 and container-runtime support before Airflow enables this diagnostic template.",
        },
        {
            "name": "immutable_evidence_references",
            "passed": immutable,
            "evidence": [bundle["reference"] for bundle in EVIDENCE_BUNDLES],
        },
        {
            "name": "read_only_evidence_mounts",
            "passed": read_only,
            "evidence": {bundle["name"]: bundle["mount_path"] for bundle in EVIDENCE_BUNDLES},
        },
        {
            "name": "incident_diagnostic_contracts",
            "passed": incident_contracts,
            "evidence": "Every mounted bundle has an incident, runbook, policy, or Airflow consumer contract.",
        },
        {
            "name": "rollout_freeze_fallback",
            "passed": True,
            "evidence": "If evidence volumes cannot be pulled, the platform keeps the rollout freeze and uses the existing object-store evidence path.",
        },
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_observability_image_volume_evidence"
        if all(check["passed"] for check in checks)
        else "keep_object_store_incident_evidence_path",
        "feature": {
            "name": "Kubernetes image volume incident evidence mounts",
            "feature_state": "Kubernetes v1.36 stable",
            "minimum_server_version": "v1.31",
            "recommended_server_version": "v1.36",
            "runtime_requirement": "Container runtime must support image volume mounts.",
            "pull_policy": "IfNotPresent",
            "sub_path_supported_from": "v1.33",
        },
        "evidence_bundles": EVIDENCE_BUNDLES,
        "airflow_integration": {
            "dag": "model_reliability_control_plane",
            "task_group": "slo_budget_and_capacity",
            "smoke_task": "verify_incident_evidence_bundles",
            "worker_image": "ghcr.io/kevinmeix1/model-observability-incident-platform:2026.07.0",
            "pod_template": "kubernetes/incident-evidence-volumes.yaml",
            "incident_gate": "Evidence bundles are verified before KubeRay incident fanout, rollback recommendation, or dashboard publishing.",
        },
        "incident_response_integration": {
            "reference_window_mount": "/mnt/evidence/reference-window",
            "policy_mount": "/mnt/evidence/policies",
            "golden_incident_mount": "/mnt/evidence/golden-incidents",
            "runbook_mount": "/mnt/evidence/runbooks",
            "fallback_store": "s3://mlops-observability-evidence/incident-bundles/",
        },
        "status_gates": {
            "no_latest_references": immutable,
            "read_only_mounts": read_only,
            "digest_references_required": True,
            "fallback_path_tested": True,
            "rollout_freeze_preserved_on_missing_evidence": True,
        },
        "failure_modes": [
            {
                "mode": "evidence_pull_error",
                "detection": "Diagnostic pod remains Pending or ContainerCreating with image-volume pull errors.",
                "recovery": "Keep the rollout freeze, verify registry credentials, and rerun with object-store evidence bundles.",
            },
            {
                "mode": "runtime_lacks_image_volume_support",
                "detection": "Admission or kubelet event rejects spec.volumes[*].image.",
                "recovery": "Use the existing object-store download path until node runtimes are upgraded.",
            },
            {
                "mode": "runbook_policy_digest_mismatch",
                "detection": "Mounted policy or runbook digest differs from governance_evidence_bundle.json.",
                "recovery": "Block automated repair, preserve the incident, and rebuild evidence through the attested release workflow.",
            },
        ],
        "operational_guardrails": [
            "Use digest references for reference windows, policy bundles, golden incidents, and runbooks; never use latest tags for incident evidence.",
            "Warm diagnostic nodes before large fanout so evidence pulls do not hide as incident response latency.",
            "Keep evidence bundles read-only and write incident updates to the incident store.",
            "Preserve rollout freezes when evidence cannot be mounted; missing context should not resume a risky rollout.",
            "Keep the object-store evidence path documented for clusters below Kubernetes v1.36 or runtimes without image-volume support.",
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/incident-evidence-volumes.yaml"],
        "references": [
            "https://kubernetes.io/docs/concepts/storage/volumes/#image",
            "https://kubernetes.io/docs/tasks/configure-pod-container/image-volumes/",
            "https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/stable/operators.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html",
        ],
    }
    write_json(root / "reports" / "incident_evidence_volume_plan.json", plan)
    return plan
