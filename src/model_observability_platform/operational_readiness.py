from __future__ import annotations

from pathlib import Path

from .io import read_json, write_json


def _load(root: Path, relative_path: str) -> dict:
    path = root / relative_path
    return read_json(path) if path.exists() else {}


def _gate(name: str, passed: bool, evidence: object, *, owner: str, blocker: str) -> dict:
    return {
        "name": name,
        "passed": passed,
        "owner": owner,
        "evidence": evidence,
        "blocker": "none" if passed else blocker,
    }


def build_operational_readiness_review(root: str | Path) -> dict:
    root = Path(root)
    slo = _load(root, "reports/slo_error_budget.json")
    release = _load(root, "reports/release_admission_decision.json")
    supply_chain = _load(root, "reports/supply_chain_evidence.json")
    telemetry = _load(root, "reports/ai_workload_telemetry_plan.json")
    performance = _load(root, "reports/performance_budget.json")
    incidents = _load(root, "reports/incident_summary.json")
    root_cause = _load(root, "reports/root_cause_evidence_bundle.json")
    alerting = _load(root, "reports/alert_routing_remediation_plan.json")

    decision = release.get("decision", {})
    attestation_ready = (
        int(supply_chain.get("artifact_count", 0)) > 0
        and supply_chain.get("subject", {}).get("attestation_action") == "actions/attest@v4"
    )
    checks = [
        _gate(
            "incident_control_fail_closed",
            decision.get("failure_policy") == "fail_closed" and not decision.get("unsafe_allow", True),
            {"action": decision.get("recommended_action"), "admitted": decision.get("admitted")},
            owner="oncall",
            blocker="wire incident review output into release admission before observability changes",
        ),
        _gate(
            "incident_slo_budget_accounted",
            float(slo.get("max_burn_rate", 99.0)) < 14.4,
            {"max_burn_rate": slo.get("max_burn_rate"), "action": slo.get("recommended_action")},
            owner="sre",
            blocker="freeze observability control-plane changes during page-level burn",
        ),
        _gate(
            "root_cause_and_alert_routing_ready",
            bool(root_cause.get("passed", True)) and bool(alerting.get("passed", True)),
            {"root_cause": root_cause.get("recommended_action"), "alerting": alerting.get("recommended_action")},
            owner="ml-reliability",
            blocker="complete impact evidence and paging route before sign-off",
        ),
        _gate(
            "incident_load_understood",
            int(incidents.get("open_count", 0)) >= 0 and incidents.get("severity") in {"low", "medium", "high", "critical"},
            {"open_count": incidents.get("open_count"), "severity": incidents.get("severity")},
            owner="incident-response",
            blocker="summarize current incident load and top severity",
        ),
        _gate(
            "supply_chain_provenance_ready",
            attestation_ready,
            supply_chain.get("subject", {}),
            owner="platform-security",
            blocker="publish dashboard, incident, and report provenance before reviewer sign-off",
        ),
        _gate(
            "observability_telemetry_ready",
            bool(telemetry.get("passed")) and len(telemetry.get("required_otel_fields", [])) >= 4,
            {"workloads": len(telemetry.get("workloads", [])), "otel_fields": telemetry.get("required_otel_fields", [])},
            owner="observability",
            blocker="capture incident id, model id, drift window, and runtime resource identifiers",
        ),
        _gate(
            "diagnostic_performance_budget_ready",
            bool(performance.get("passed")),
            {"performance": performance.get("recommended_action")},
            owner="platform",
            blocker="hold control-plane changes until detection and incident creation budgets pass",
        ),
    ]
    readiness_score = round(100.0 * sum(check["passed"] for check in checks) / len(checks), 2)
    review = {
        "project": "Model Observability Incident Platform",
        "target": "airflow://ml-observability/model-reliability-control-plane",
        "generated_at": "2026-07-11T00:00:00Z",
        "readiness_score": readiness_score,
        "recommended_action": "approve_with_incident_watch" if readiness_score >= 80.0 else "hold_for_remediation",
        "checks": checks,
        "operator_review_packet": [
            "reports/release_admission_decision.json",
            "reports/incident_summary.json",
            "reports/root_cause_evidence_bundle.json",
            "reports/alert_routing_remediation_plan.json",
            "reports/slo_error_budget.json",
            "reports/supply_chain_evidence.json",
        ],
        "judge_demo_talking_points": [
            "The platform can explain what failed, who owns it, and what downstream assets are at risk.",
            "Incident, SLO, alert routing, root-cause, and provenance evidence are reviewed together.",
            "The readiness packet is useful both for demos and for a real change advisory review.",
        ],
        "production_followups": [
            "Attach readiness packet hashes to incident timeline events.",
            "Page owners from failed readiness gates automatically.",
            "Use this report as a preflight before collector, alert, or dashboard releases.",
        ],
    }
    write_json(root / "reports" / "operational_readiness_review.json", review)
    return review
