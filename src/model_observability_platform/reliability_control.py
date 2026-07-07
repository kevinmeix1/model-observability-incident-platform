from __future__ import annotations

from pathlib import Path

from .io import read_json, write_json


def burn_rate(error_rate: float, *, availability_slo: float = 0.995) -> float:
    return round(error_rate / max(1.0 - availability_slo, 0.0001), 4)


def failed_checks(report: dict) -> list[dict]:
    return [check for check in report.get("checks", []) if not check.get("passed")]


def build_reliability_plan(root: str | Path) -> dict:
    root = Path(root)
    report = read_json(root / "reports" / "observability_report.json")
    incidents = read_json(root / "reports" / "incident_summary.json")
    error_check = next((check for check in report.get("checks", []) if check.get("name") == "error_rate"), {})
    latency_check = next((check for check in report.get("checks", []) if check.get("name") == "latency_slo"), {})
    observed_error_rate = float(error_check.get("observed", 0.0))
    error_burn = burn_rate(observed_error_rate)
    open_incidents = int(incidents.get("open_count", 0))
    severity = incidents.get("severity", "low")
    failed = failed_checks(report)
    impacted_assets = sorted(
        {
            "prediction_logs",
            "model_serving_api" if {"latency_slo", "error_rate"} & {check["name"] for check in failed} else "feature_pipeline",
            "incident_dashboard",
            "rollback_decision",
        }
    )
    if severity in {"critical", "high"} and error_burn >= 4.0:
        action = "page_and_freeze_rollouts"
    elif open_incidents >= 3:
        action = "open_incident_review"
    elif failed:
        action = "watch"
    else:
        action = "healthy"
    plan = {
        "recommended_action": action,
        "severity": severity,
        "open_incidents": open_incidents,
        "error_budget_burn_rate": error_burn,
        "latency_p95": latency_check.get("observed"),
        "failed_checks": [check["name"] for check in failed],
        "impacted_assets": impacted_assets,
        "routing": {
            "page": action == "page_and_freeze_rollouts",
            "slack_channel": "#ml-reliability",
            "owner": "ml-platform-oncall",
        },
        "runbook_steps": [
            "Freeze model promotions while impact is unknown.",
            "Compare current feature distributions against the reference window.",
            "Inspect KServe latency and error-rate dashboards.",
            "Rollback champion alias if serving failures exceed the burn-rate policy.",
        ],
    }
    write_json(root / "reports" / "reliability_control_plan.json", plan)
    return plan
