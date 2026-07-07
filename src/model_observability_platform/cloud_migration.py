from __future__ import annotations

from pathlib import Path

from .io import write_json


def build_cloud_migration_plan(root: str | Path) -> dict:
    root = Path(root)
    plan = {
        "platform": "model-observability-incident-platform",
        "primary_target": "AWS EKS Auto Mode",
        "managed_service_mapping": {
            "monitoring": "Amazon Managed Service for Prometheus and Grafana",
            "telemetry_storage": "S3 baseline windows plus warehouse tables for queryable history",
            "incident_store": "DynamoDB or PostgreSQL incident table with dedupe fingerprint key",
            "alerting": "Alertmanager webhook to PagerDuty, Slack, or email",
            "control_plane": "Airflow Helm chart on EKS or MWAA for scheduled checks",
            "rollout_freeze": "GitOps or Airflow variable consumed by model release DAGs",
        },
        "migration_phases": [
            {"phase": "foundation", "tasks": ["provision EKS", "enable IRSA", "create telemetry buckets", "install Prometheus stack"]},
            {"phase": "reliability", "tasks": ["migrate baselines", "create incident table", "wire alert webhook", "apply SLO rules"]},
            {"phase": "operations", "tasks": ["replay broken window", "verify dedupe", "verify rollout freeze signal"]},
        ],
        "portability_controls": [
            "incident fingerprints are stable across storage backends",
            "monitoring thresholds live in contracts/observability_policy.yml",
            "rollout-freeze output is a small provider-neutral JSON policy",
            "cloud-specific IAM and storage live under infra/terraform/aws",
        ],
        "cost_controls": [
            "compact high-cardinality telemetry before long-term retention",
            "store raw windows in S3 with lifecycle policies",
            "scale observability workers separately from serving workers",
            "page only on multi-window burn to reduce alert noise",
        ],
    }
    write_json(root / "reports" / "cloud_migration_plan.json", plan)
    return plan
