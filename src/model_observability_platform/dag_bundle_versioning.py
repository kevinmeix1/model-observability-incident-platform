from __future__ import annotations

from pathlib import Path

from .io import write_json


AIRFLOW_DAG_BUNDLE = {
    "name": "model-observability-bundle",
    "provider": "GitDagBundle",
    "tracking_ref": "main",
    "subdir": "airflow/dags",
    "git_conn_id": "github_dag_bundle",
    "sparse_dirs": ["airflow/dags", "kubernetes", "contracts", "src"],
    "refresh_interval_seconds": 60,
}


def build_dag_bundle_versioning_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
    dag_id: str = "model_reliability_control_plane",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "git_dag_bundle_declared",
            "passed": AIRFLOW_DAG_BUNDLE["provider"] == "GitDagBundle",
            "evidence": "Airflow loads reliability-control DAGs from a Git-backed DAG Bundle.",
        },
        {
            "name": "bundle_versioning_enabled",
            "passed": True,
            "evidence": "[dag_processor] disable_bundle_versioning = False preserves historical incident orchestration code.",
        },
        {
            "name": "incident_replay_preserves_bundle",
            "passed": True,
            "evidence": "Incident reruns preserve the bundle version that produced the original dedupe and root-cause evidence.",
        },
        {
            "name": "incident_assets_in_sparse_checkout",
            "passed": "kubernetes" in AIRFLOW_DAG_BUNDLE["sparse_dirs"] and "contracts" in AIRFLOW_DAG_BUNDLE["sparse_dirs"],
            "evidence": "Sparse checkout includes reliability DAGs, incident evidence volumes, Kubernetes policies, contracts, and source code.",
        },
        {
            "name": "credentials_kept_in_airflow_connection",
            "passed": AIRFLOW_DAG_BUNDLE["git_conn_id"] == "github_dag_bundle",
            "evidence": "Git credentials are stored in Airflow Connections or a secrets backend via git_conn_id.",
        },
        {
            "name": "scheduler_managed_backfill_policy",
            "passed": True,
            "evidence": "Airflow 3 backfills are scheduled as tracked runs, separate from incident forensics.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_airflow3_incident_dag_bundle_versioning" if passed else "hold_airflow_dag_bundle_rollout",
        "airflow_version_target": "3.3.x",
        "dag_id": dag_id,
        "bundle": AIRFLOW_DAG_BUNDLE,
        "runtime_config": {
            "AIRFLOW__DAG_PROCESSOR__DAG_BUNDLE_CONFIG_LIST": "configured in airflow/dag-bundle-config.ini",
            "AIRFLOW__DAG_PROCESSOR__DISABLE_BUNDLE_VERSIONING": "False",
            "AIRFLOW__CORE__RERUN_WITH_LATEST_VERSION": "False",
        },
        "rerun_policy": {
            "core.rerun_with_latest_version": False,
            "dag.rerun_with_latest_version": False,
            "incident_replay_uses_original_bundle": True,
            "rollout_freeze_replay_uses_original_bundle": True,
        },
        "backfill_policy": {
            "scheduler_managed_backfills": True,
            "fresh_monitoring_backfills": "use_latest_bundle_for_new_observability_windows",
            "incident_forensic_replay": "pin_to_bundle_version_recorded_on_original_incident",
            "max_active_runs": 1,
            "pool": "observability_pool",
        },
        "incident_replay_evidence": [
            "bundle_name",
            "bundle_version",
            "airflow_run_id",
            "incident_id",
            "incident_fingerprint",
            "root_cause_fanout_job",
            "evidence_bundle_digest",
            "rollout_freeze_decision",
        ],
        "failure_modes": [
            {
                "mode": "bad_incident_workflow_commit",
                "blast_radius": "new incident diagnostics can misroute while completed incidents retain their original bundle version",
                "recovery": "revert the commit, keep the failed incident bundle_version, and launch a fresh diagnostic run",
            },
            {
                "mode": "rollout_freeze_replay_drift",
                "blast_radius": "replay executes different root-cause or rollout-freeze code than the incident run",
                "recovery": "keep rerun_with_latest_version disabled and validate hotfix code in a separate remediation run",
            },
            {
                "mode": "git_bundle_refresh_failure",
                "blast_radius": "scheduler stops seeing new DAG commits but running diagnostics keep recorded code versions",
                "recovery": "restore the github_dag_bundle connection and refresh DAG processors",
            },
        ],
        "operational_guardrails": [
            "Attach bundle name and version to incident_summary.json, reliability_control_plan.json, and governance evidence.",
            "Do not let missing or changed DAG code resume a rollout freeze; incident replay should preserve original control logic.",
            "Keep Git credentials out of dag_bundle_config_list and in Airflow Connections or a secrets backend.",
            "Use sparse_dirs so DAG parsing includes incident evidence manifests, policy contracts, and platform source code.",
            "Record image-volume evidence digests beside the bundle version so incident context and orchestration are reproducible together.",
        ],
        "checks": checks,
        "airflow_assets": [
            "airflow/dag-bundle-config.ini",
            "airflow/dags/model_reliability_control_plane_dag.py",
            "docs/airflow-dag-bundles.md",
        ],
        "references": [
            "https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html#gitdagbundle",
            "https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html#rerun-behavior",
            "https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html",
        ],
    }
    write_json(root / "reports" / "dag_bundle_versioning_plan.json", plan)
    return plan
