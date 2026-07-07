from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .io import read_json, read_jsonl, write_json


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_optional_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return read_json(path)


def _sha256(path: Path) -> dict:
    if not path.exists() or not path.is_file():
        return {"path": str(path), "exists": False, "sha256": None}
    return {"path": str(path), "exists": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_governance_bundle(root: str | Path) -> dict:
    root = Path(root)
    report = _read_optional_json(root / "reports" / "observability_report.json", {"passed": False, "checks": []})
    incident_summary = _read_optional_json(root / "reports" / "incident_summary.json", {"open_count": 0, "severity": "low", "incidents": []})
    reliability_plan = _read_optional_json(root / "reports" / "reliability_control_plan.json", {})
    incidents = read_jsonl(root / "incidents" / "incidents.jsonl")
    failed_checks = [check for check in report.get("checks", []) if not check.get("passed")]
    decision = "approved_reliability_policy" if report.get("passed") else "incident_review_required"

    artifact_paths = [
        root / "data" / "reference.csv",
        root / "data" / "current.csv",
        root / "reports" / "observability_report.json",
        root / "reports" / "incident_summary.json",
        root / "reports" / "reliability_control_plan.json",
        root / "incidents" / "incidents.jsonl",
    ]
    reproducibility_manifest = {
        "generated_at": _utc_iso(),
        "platform": "model-observability-incident-platform",
        "decision": decision,
        "open_incidents": incident_summary.get("open_count", 0),
        "artifact_hashes": [_sha256(path) for path in artifact_paths],
        "environment": {
            "monitoring": "custom drift, latency, error-rate, freshness, and null-rate checks",
            "incident_management": "idempotent incidents with stable fingerprints",
            "control_plane": "burn-rate based reliability plan and rollout freeze decision",
        },
    }

    model_card = {
        "name": "model-observability-policy",
        "version": "2026.07",
        "intended_use": "Detect model reliability degradation and create actionable incidents.",
        "out_of_scope_use": "Do not page humans without severity routing and deduplication controls.",
        "monitored_signals": [check.get("name") for check in report.get("checks", [])],
        "failed_signals": [check.get("name") for check in failed_checks],
        "reliability_action": reliability_plan.get("recommended_action"),
        "limitations": [
            "Synthetic telemetry is used for local repeatability.",
            "Thresholds should be calibrated from production baseline windows.",
            "Incident routing placeholders need integration with the real paging system.",
        ],
    }

    data_card = {
        "dataset": "model_serving_telemetry_windows",
        "owner": "ml-reliability",
        "source": "deterministic telemetry generator in src/model_observability_platform/telemetry.py",
        "reference_window": "data/reference.csv",
        "current_window": "data/current.csv",
        "psi": report.get("psi", {}),
        "reference_means": report.get("reference_means", {}),
        "current_means": report.get("current_means", {}),
        "schema_contract": "contracts/observability_policy.yml",
        "retention": "Reference windows, incident fingerprints, and reports should be retained for audit and threshold tuning.",
    }

    risk_register = [
        {
            "risk": "alert fatigue from repeated failures",
            "impact": "operators ignore real model reliability incidents",
            "control": "idempotent incident fingerprints and severity routing",
            "evidence": "incidents/incidents.jsonl",
            "status": "controlled",
        },
        {
            "risk": "hidden drift affects predictions",
            "impact": "model quality silently degrades while serving stays healthy",
            "control": "feature drift, PSI, prediction drift, and baseline comparison",
            "evidence": "reports/observability_report.json",
            "status": "controlled" if report else "missing_report",
        },
        {
            "risk": "rollouts continue during high burn-rate incidents",
            "impact": "a bad model release compounds an active reliability problem",
            "control": "burn-rate reliability plan recommends rollout freeze and paging",
            "evidence": "reports/reliability_control_plan.json",
            "status": "controlled" if reliability_plan else "needs_plan",
        },
        {
            "risk": "root cause is unclear",
            "impact": "incident response spends too long on the wrong system",
            "control": "failed checks are grouped into likely root-cause categories",
            "evidence": "reports/incident_summary.json",
            "status": "controlled" if incidents else "needs_incident_data",
        },
    ]

    approval_record = {
        "approval_id": "model-observability-policy-2026.07",
        "decision": decision,
        "generated_at": _utc_iso(),
        "approvers": ["ml-reliability-owner", "incident-commander"],
        "required_evidence": [
            "observability report generated",
            "incident dedupe evidence generated",
            "reliability control plan generated",
            "drift and SLO signals captured",
            "reproducibility hashes captured",
        ],
        "open_incidents": incident_summary.get("open_count", 0),
        "severity": incident_summary.get("severity", "low"),
    }

    bundle = {
        "platform": "model-observability-incident-platform",
        "framework_alignment": {
            "nist_ai_rmf": ["Govern", "Map", "Measure", "Manage"],
            "mlflow_registry": "observability evidence can gate model alias promotion and rollback",
            "model_transparency": "system card plus telemetry data card and incident risk register",
        },
        "release": {
            "system_name": model_card["name"],
            "decision": approval_record["decision"],
            "open_incidents": incident_summary.get("open_count", 0),
            "recommended_action": reliability_plan.get("recommended_action"),
        },
        "evidence_files": {
            "model_card": "governance/model_card.json",
            "data_card": "governance/data_card.json",
            "risk_register": "governance/risk_register.json",
            "approval_record": "governance/approval_record.json",
            "reproducibility_manifest": "governance/reproducibility_manifest.json",
        },
    }

    write_json(root / "governance" / "model_card.json", model_card)
    write_json(root / "governance" / "data_card.json", data_card)
    write_json(root / "governance" / "risk_register.json", risk_register)
    write_json(root / "governance" / "approval_record.json", approval_record)
    write_json(root / "governance" / "reproducibility_manifest.json", reproducibility_manifest)
    write_json(root / "reports" / "governance_evidence_bundle.json", bundle)
    return bundle
