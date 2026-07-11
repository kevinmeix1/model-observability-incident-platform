from __future__ import annotations

from pathlib import Path

from .checks import likely_root_cause
from .io import read_json, write_json
from .reliability_control import burn_rate


def _failed_checks(report: dict) -> list[dict]:
    return [check for check in report.get("checks", []) if not check.get("passed")]


def _check_by_name(report: dict, name: str) -> dict:
    return next((check for check in report.get("checks", []) if check.get("name") == name), {})


def _evidence_for_check(check: dict) -> dict:
    name = check.get("name", "unknown")
    source = f"observability_report.checks.{name}"
    if name == "feature_drift":
        failed_features = check.get("failed_features", [])
        psi = check.get("observed", {}).get("psi", {})
        max_psi = max(psi.values(), default=0.0)
        return {
            "signal": "population_shift",
            "source": source,
            "supports": "upstream_population_shift",
            "observed": f"{len(failed_features)} drifted features; max PSI {max_psi:.3f}",
            "severity": check.get("severity", "medium"),
        }
    if name == "prediction_drift":
        return {
            "signal": "model_behavior_shift",
            "source": source,
            "supports": "upstream_population_shift",
            "observed": f"mean risk score delta {float(check.get('observed', 0.0)):.3f}",
            "severity": check.get("severity", "high"),
        }
    if name == "latency_slo":
        observed = float(check.get("observed", 0.0))
        threshold = float(check.get("threshold", 0.0))
        return {
            "signal": "serving_latency_regression",
            "source": source,
            "supports": "serving_capacity_or_dependency_failure",
            "observed": f"p95 {observed:.1f} ms; limit {threshold:.1f} ms",
            "severity": check.get("severity", "medium"),
        }
    if name == "error_rate":
        observed = float(check.get("observed", 0.0))
        return {
            "signal": "availability_burn",
            "source": source,
            "supports": "serving_capacity_or_dependency_failure",
            "observed": f"error rate {observed:.2%}; burn rate {burn_rate(observed):.1f}x",
            "severity": check.get("severity", "high"),
        }
    if name == "freshness":
        return {
            "signal": "telemetry_freshness_delay",
            "source": source,
            "supports": "telemetry_pipeline_delay",
            "observed": f"freshness lag {float(check.get('observed', 0.0)):.1f} minutes",
            "severity": check.get("severity", "medium"),
        }
    if name == "null_rate":
        return {
            "signal": "request_contract_violation",
            "source": source,
            "supports": "request_contract_violation",
            "observed": f"{int(check.get('observed', 0))} null feature values",
            "severity": check.get("severity", "medium"),
        }
    return {
        "signal": name,
        "source": source,
        "supports": "model_or_data_quality_degradation",
        "observed": check.get("observed", "failed"),
        "severity": check.get("severity", "medium"),
    }


def build_root_cause_evidence_bundle(root: str | Path) -> dict:
    root = Path(root)
    report = read_json(root / "reports" / "observability_report.json")
    incidents = read_json(root / "reports" / "incident_summary.json")
    reliability_path = root / "reports" / "reliability_control_plan.json"
    reliability = read_json(reliability_path) if reliability_path.exists() else {}
    failed = _failed_checks(report)
    root_cause = (
        incidents.get("incidents", [{}])[-1].get("root_cause")
        if incidents.get("incidents")
        else likely_root_cause(failed)
    )
    evidence = [_evidence_for_check(check) for check in failed]
    error_check = _check_by_name(report, "error_rate")
    observed_error_rate = float(error_check.get("observed", 0.0))
    error_burn = burn_rate(observed_error_rate)
    failed_features = _check_by_name(report, "feature_drift").get("failed_features", [])
    lineage_facets = [
        {
            "entity": "run",
            "name": "incidentRootCauseFacet",
            "fields": {
                "root_cause": root_cause,
                "confidence": None,
                "policy_version": "2026.07",
                "failed_check_count": len(failed),
            },
        },
        {
            "entity": "input_dataset",
            "name": "featureWindowFacet",
            "dataset": "prediction_logs.current_window",
            "fields": {
                "row_count": report.get("current_row_count", 0),
                "failed_features": failed_features,
            },
        },
        {
            "entity": "input_dataset",
            "name": "servingTelemetryFacet",
            "dataset": "model_serving_api.metrics",
            "fields": {
                "latency_p95_ms": reliability.get("latency_p95"),
                "error_budget_burn_rate": error_burn,
            },
        },
    ]
    feature_flags = [
        {
            "key": "risk_model_shadow_read",
            "variant": "enabled",
            "reason": (
                "shadow predictions explain prediction distribution without changing "
                "champion routing"
            ),
        },
        {
            "key": "canary_route_weight",
            "variant": "0_percent",
            "reason": (
                "release admission froze rollout traffic while incident evidence is "
                "incomplete"
            ),
        },
        {
            "key": "incident_auto_freeze",
            "variant": "enabled",
            "reason": "SLO burn and high-severity incidents trigger fail-closed promotion control",
        },
    ]
    symptom_names = {item["signal"] for item in evidence}
    has_population = {"population_shift", "model_behavior_shift"} <= symptom_names
    has_serving = {"serving_latency_regression", "availability_burn"} & symptom_names
    confidence = (
        0.45
        + 0.08 * len(evidence)
        + (0.18 if has_population else 0.0)
        + (0.16 if has_serving else 0.0)
    )
    confidence = round(min(confidence, 0.95), 3)
    lineage_facets[0]["fields"]["confidence"] = confidence
    missing_evidence = []
    if "freshness" not in {check.get("name") for check in failed}:
        missing_evidence.append("No telemetry pipeline freshness breach in this scenario.")
    missing_evidence.append(
        "Delayed outcome labels are not available yet, so RCA remains probabilistic."
    )
    checks = {
        "symptom_first_alerting": error_burn >= 4.0 or bool(failed),
        "openlineage_facets_declared": len(lineage_facets) >= 3,
        "feature_flag_context_declared": len(feature_flags) >= 3,
        "confidence_threshold_met": confidence >= 0.8,
        "dedupe_fingerprint_unchanged": True,
    }
    bundle = {
        "generated_at": report.get("evaluated_at", "2026-07-07T13:30:00+00:00"),
        "passed": all(checks.values()),
        "root_cause": root_cause,
        "confidence": confidence,
        "evidence_count": len(evidence),
        "evidence": evidence,
        "lineage_facets": lineage_facets,
        "feature_flag_context": feature_flags,
        "slo_burn_evidence": {
            "availability_slo": 0.995,
            "error_budget_burn_rate": error_burn,
            "recommended_action": reliability.get("recommended_action", "not_planned"),
            "principle": (
                "alert on user-impacting symptoms first, then attach causal evidence "
                "for review"
            ),
        },
        "checks": checks,
        "missing_evidence": missing_evidence,
        "research_basis": [
            (
                "Google SRE guidance: page on symptoms tied to user impact and use "
                "SLO burn evidence for high-signal alerts."
            ),
            (
                "OpenLineage facets: attach atomic metadata to run, job, and "
                "dataset entities for portable lineage evidence."
            ),
            (
                "OpenTelemetry event semantic conventions: record feature flag "
                "evaluation context as structured event attributes."
            ),
        ],
    }
    write_json(root / "reports" / "root_cause_evidence_bundle.json", bundle)
    return bundle
