from __future__ import annotations

from pathlib import Path

from .io import read_json, write_json


def _load(path: Path, default: dict) -> dict:
    return read_json(path) if path.exists() else default


def _check(name: str, passed: bool, observed: object, *, owner: str, action: str) -> dict:
    return {
        "name": name,
        "passed": passed,
        "observed": observed,
        "owner": owner,
        "action": action if not passed else "none",
    }


def evaluate_release_admission(
    *,
    slo: dict,
    performance: dict,
    queue: dict,
    governance: dict,
    supply_chain: dict,
    reliability_plan: dict,
    incidents: dict,
) -> dict:
    max_burn = float(slo.get("max_burn_rate", 0.0))
    release_freeze = bool(slo.get("release_freeze", False))
    performance_passed = bool(performance.get("passed", False))
    queue_passed = bool(queue.get("passed", False))
    incident_pending = [
        item["name"]
        for item in queue.get("simulation", {}).get("pending", [])
        if int(item.get("priority", 0)) >= 900
    ]
    governance_decision = governance.get("release", {}).get("decision", "unknown")
    attestation_ready = (
        int(supply_chain.get("artifact_count", 0)) > 0
        and supply_chain.get("subject", {}).get("attestation_action") == "actions/attest@v4"
    )
    reliability_action = reliability_plan.get("recommended_action", "unknown")
    open_incidents = int(incidents.get("open_count", 0))
    severity = incidents.get("severity", "low")
    checks = [
        _check(
            "incident_severity",
            severity not in {"high", "critical"} and open_incidents == 0,
            {"severity": severity, "open_incidents": open_incidents},
            owner="oncall",
            action="freeze_rollouts_and_page",
        ),
        _check(
            "slo_error_budget",
            not release_freeze and max_burn < 6.0,
            {"max_burn_rate": max_burn, "recommended_action": slo.get("recommended_action")},
            owner="sre",
            action="freeze_rollouts_and_page",
        ),
        _check(
            "performance_budget",
            performance_passed,
            {"failed": [check["name"] for check in performance.get("checks", []) if not check.get("passed")]},
            owner="observability",
            action="hold_monitor_changes",
        ),
        _check(
            "incident_diagnostic_capacity",
            queue_passed and not incident_pending,
            {"pending_count": queue.get("pending_count", 0), "critical_pending": incident_pending},
            owner="orchestration",
            action="reserve_incident_diagnostics",
        ),
        _check(
            "governance_and_provenance",
            governance_decision in {"incident_review_required", "healthy"} and attestation_ready,
            {"governance": governance_decision, "attestation_ready": attestation_ready},
            owner="risk",
            action="require_signed_incident_record",
        ),
    ]
    if reliability_action == "page_and_freeze_rollouts" or release_freeze or max_burn >= 14.4 or severity in {"high", "critical"}:
        action = "freeze_rollouts_and_page"
    elif not queue_passed or incident_pending:
        action = "reserve_incident_diagnostics"
    elif all(check["passed"] for check in checks):
        action = "admit_observability_change"
    else:
        action = "hold_observability_change"
    return {
        "recommended_action": action,
        "admitted": action == "admit_observability_change",
        "unsafe_allow": action == "admit_observability_change" and not all(check["passed"] for check in checks),
        "checks": checks,
        "reliability_action": reliability_action,
        "failure_policy": "fail_closed",
    }


def build_release_admission_decision(root: str | Path) -> dict:
    root = Path(root)
    decision = evaluate_release_admission(
        slo=_load(root / "reports" / "slo_error_budget.json", {}),
        performance=_load(root / "reports" / "performance_budget.json", {}),
        queue=_load(root / "reports" / "queue_simulation.json", {}),
        governance=_load(root / "reports" / "governance_evidence_bundle.json", {}),
        supply_chain=_load(root / "reports" / "supply_chain_evidence.json", {}),
        reliability_plan=_load(root / "reports" / "reliability_control_plan.json", {}),
        incidents=_load(root / "reports" / "incident_summary.json", {}),
    )
    record = {
        "project": "Model Observability Incident Platform",
        "target": "airflow://ml-observability/model-reliability-control-plane",
        "evaluated_at": "2026-07-08T00:00:00Z",
        "decision": decision,
        "policy_inputs": {
            "slo": "reports/slo_error_budget.json",
            "performance": "reports/performance_budget.json",
            "queue": "reports/queue_simulation.json",
            "governance": "reports/governance_evidence_bundle.json",
            "supply_chain": "reports/supply_chain_evidence.json",
            "reliability_plan": "reports/reliability_control_plan.json",
            "incidents": "reports/incident_summary.json",
        },
        "enforcement_points": [
            "Airflow incident DAG freezes downstream model promotions when the decision is freeze_rollouts_and_page.",
            "Kubernetes ValidatingAdmissionPolicy requires observability control-plane changes to carry release evidence.",
            "Argo Rollouts analysis gates collector and incident-router changes on alerting SLOs.",
            "Kueue priority reserves diagnostic capacity for incident root-cause jobs.",
        ],
        "references": [
            "https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/",
            "https://argo-rollouts.readthedocs.io/en/stable/features/analysis/",
            "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html",
            "https://kueue.sigs.k8s.io/docs/concepts/preemption/",
        ],
    }
    write_json(root / "reports" / "release_admission_decision.json", record)
    return record
