from __future__ import annotations

from pathlib import Path

from .io import write_json


def build_gitops_plan(root: str | Path) -> dict:
    root = Path(root)
    plan = {
        "platform": "model-observability-incident-platform",
        "deployment_controller": "Argo CD",
        "progressive_delivery": "Argo Rollouts controller rollout with telemetry and incident SLO analysis",
        "config_repo_pattern": "separate observability manifests with pinned collector and incident images",
        "sync_waves": [
            {"wave": -3, "name": "security-and-network", "resources": ["NetworkPolicy", "PeerAuthentication", "AuthorizationPolicy"]},
            {"wave": -2, "name": "capacity-and-alerting", "resources": ["HPA", "VPA recommender", "PrometheusRule", "Airflow pools"]},
            {"wave": -1, "name": "pre-sync-observability-gates", "resources": ["schema drift check", "incident dedupe dry-run"]},
            {"wave": 0, "name": "observability-runtime", "resources": ["collector", "drift evaluator", "incident router"]},
            {"wave": 1, "name": "post-sync-reliability-analysis", "resources": ["freshness check", "burn-rate check", "incident smoke test"]},
        ],
        "promotion_stages": [
            {"environment": "dev", "sync": "automated", "self_heal": True, "approval": "pull request"},
            {"environment": "staging", "sync": "automated", "self_heal": True, "approval": "observability owner approval"},
            {"environment": "prod", "sync": "manual", "self_heal": False, "approval": "change ticket plus no active high severity incident"},
        ],
        "gates": [
            "telemetry freshness check passes",
            "incident creation dry-run is idempotent",
            "burn-rate remains below paging threshold",
            "network topology limits collector egress",
            "resource plan reserves incident pool slots",
        ],
        "rollback": {
            "command": "argocd app rollback model-observability-incident-platform <history-id>",
            "runtime": "argo rollouts abort observability-control-plane -n ml-observability",
            "evidence": ".local/reports/incident_summary.json and .local/reports/reliability_control_plan.json",
        },
    }
    write_json(root / "reports" / "gitops_plan.json", plan)
    return plan
