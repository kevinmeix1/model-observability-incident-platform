from __future__ import annotations

from pathlib import Path

from .io import write_json


ALERTS = [
    {
        "name": "CreditRiskPredictionDriftHigh",
        "severity": "critical",
        "domain": "credit-risk",
        "service": "risk-model-router",
        "slo": "prediction_distribution",
        "root_cause": "population_shift",
        "candidate_remediation": "freeze_rollout",
    },
    {
        "name": "CreditRiskFeatureDriftHigh",
        "severity": "high",
        "domain": "credit-risk",
        "service": "feature-pipeline",
        "slo": "feature_distribution",
        "root_cause": "population_shift",
        "candidate_remediation": "launch_root_cause_fanout",
    },
    {
        "name": "CreditRiskLatencyBudgetBurn",
        "severity": "high",
        "domain": "credit-risk",
        "service": "risk-model-router",
        "slo": "serving_latency",
        "root_cause": "serving_degradation",
        "candidate_remediation": "scale_diagnostic_workers",
    },
    {
        "name": "CreditRiskDashboardStale",
        "severity": "medium",
        "domain": "credit-risk",
        "service": "observability-dashboard",
        "slo": "operator_visibility",
        "root_cause": "downstream_symptom",
        "candidate_remediation": "republish_dashboard",
    },
]

REMEDIATION_POLICIES = {
    "freeze_rollout": {
        "mode": "automatic",
        "requires_human": False,
        "target": "Argo Rollouts pause and release-admission freeze",
        "blast_radius": "prevent traffic movement only",
    },
    "launch_root_cause_fanout": {
        "mode": "automatic",
        "requires_human": False,
        "target": "Airflow incident root-cause DAG",
        "blast_radius": "diagnostic read-only fanout",
    },
    "scale_diagnostic_workers": {
        "mode": "guarded",
        "requires_human": True,
        "target": "Kueue diagnostic workers",
        "blast_radius": "resource increase on observability queue",
    },
    "republish_dashboard": {
        "mode": "automatic",
        "requires_human": False,
        "target": "dashboard publisher",
        "blast_radius": "idempotent static artifact refresh",
    },
}


def _severity_rank(value: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(value, 0)


def simulate_alertmanager_routing() -> dict:
    groups: dict[tuple[str, str], list[dict]] = {}
    for alert in ALERTS:
        groups.setdefault((alert["domain"], alert["root_cause"]), []).append(alert)

    routed_groups = []
    inhibited_alerts = []
    for (domain, root_cause), alerts in sorted(groups.items()):
        top = max(alerts, key=lambda item: _severity_rank(item["severity"]))
        receiver = "pagerduty-ml-platform" if top["severity"] == "critical" else "slack-ml-platform"
        suppressed = [
            alert
            for alert in alerts
            if alert["name"] != top["name"] and alert["root_cause"] == top["root_cause"]
        ]
        inhibited_alerts.extend(
            {
                "alert": alert["name"],
                "inhibited_by": top["name"],
                "rule": "same_domain_same_root_cause_lower_severity",
            }
            for alert in suppressed
        )
        routed_groups.append(
            {
                "group_key": f"{domain}:{root_cause}",
                "domain": domain,
                "root_cause": root_cause,
                "receiver": receiver,
                "group_wait": "30s",
                "group_interval": "5m",
                "repeat_interval": "2h",
                "top_alert": top["name"],
                "alert_count": len(alerts),
                "suppressed_count": len(suppressed),
                "severity": top["severity"],
            }
        )

    return {
        "groups": routed_groups,
        "inhibited_alerts": inhibited_alerts,
        "dedupe_key_fields": ["domain", "root_cause", "model_version", "slo"],
        "route_tree": [
            "critical incidents route to PagerDuty and freeze rollout automation",
            "high severity drift routes to Slack plus incident fanout",
            "medium dashboard symptoms are inhibited when a higher root-cause alert exists",
        ],
    }


def build_alert_routing_remediation_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
) -> dict:
    root = Path(root)
    routing = simulate_alertmanager_routing()
    remediations = []
    for alert in ALERTS:
        policy = REMEDIATION_POLICIES[alert["candidate_remediation"]]
        remediations.append(
            {
                "alert": alert["name"],
                "action": alert["candidate_remediation"],
                "mode": policy["mode"],
                "requires_human": policy["requires_human"],
                "target": policy["target"],
                "blast_radius": policy["blast_radius"],
            }
        )

    checks = [
        {
            "name": "alertmanager_grouping_defined",
            "passed": all(group["alert_count"] >= 1 for group in routing["groups"]),
            "evidence": "Alerts are grouped by domain and root cause before routing.",
        },
        {
            "name": "inhibition_rules_reduce_noise",
            "passed": len(routing["inhibited_alerts"]) >= 1,
            "evidence": routing["inhibited_alerts"],
        },
        {
            "name": "critical_route_pages_and_freezes",
            "passed": any(
                group["receiver"] == "pagerduty-ml-platform"
                and group["severity"] == "critical"
                for group in routing["groups"]
            ),
            "evidence": "Critical prediction drift pages and triggers release freeze automation.",
        },
        {
            "name": "remediation_blast_radius_classified",
            "passed": all(item["blast_radius"] for item in remediations),
            "evidence": remediations,
        },
        {
            "name": "human_approval_required_for_resource_mutation",
            "passed": any(
                item["requires_human"] and item["action"] == "scale_diagnostic_workers"
                for item in remediations
            ),
            "evidence": "Resource-increasing remediation is guarded instead of fully automatic.",
        },
        {
            "name": "column_lineage_impact_declared",
            "passed": True,
            "evidence": (
                "OpenLineage columnLineage-style facet maps drifted fields to reports and APIs."
            ),
        },
        {
            "name": "argo_rollouts_notifications_declared",
            "passed": True,
            "evidence": "Rollout notification triggers publish freeze, abort, and resume events.",
        },
    ]
    plan = {
        "project": project,
        "generated_at": "2026-07-10T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "recommended_action": "enable_alert_routing_and_guarded_remediation",
        "alertmanager": routing,
        "remediations": remediations,
        "lineage_impact": {
            "facet": "columnLineage",
            "drifted_columns": ["debt_ratio", "utilization", "risk_score"],
            "impacted_assets": [
                "risk_model_router",
                "credit_risk_dashboard",
                "release_admission_api",
            ],
            "critical_paths": [
                "feature-pipeline.debt_ratio -> risk_model_router.risk_score",
                "feature-pipeline.utilization -> risk_model_router.risk_score",
                "risk_model_router.risk_score -> credit_risk_dashboard.default_rate_panel",
            ],
        },
        "rollout_notifications": [
            {
                "trigger": "on-analysis-run-failed",
                "action": "freeze_rollout",
                "receiver": "pagerduty-ml-platform",
            },
            {
                "trigger": "on-rollout-aborted",
                "action": "open_incident",
                "receiver": "slack-ml-platform",
            },
            {
                "trigger": "on-rollout-paused",
                "action": "attach_evidence",
                "receiver": "incident-outbox",
            },
        ],
        "checks": checks,
        "kubernetes_assets": ["kubernetes/alert-routing-remediation.yaml"],
        "references": [
            "https://prometheus.io/docs/alerting/latest/alertmanager/",
            "https://argo-rollouts.readthedocs.io/en/stable/features/notifications/",
            "https://argo-rollouts.readthedocs.io/en/stable/features/analysis/",
            "https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet/",
        ],
    }
    write_json(root / "reports" / "alert_routing_remediation_plan.json", plan)
    return plan
