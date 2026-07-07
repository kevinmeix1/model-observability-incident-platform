from __future__ import annotations

from datetime import datetime, timezone
import math

from .telemetry import FEATURES


def mean(rows: list[dict], column: str) -> float:
    values = [float(row[column]) for row in rows if row.get(column) not in {"", None}]
    return sum(values) / max(len(values), 1)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(round((len(ordered) - 1) * pct)), len(ordered) - 1)
    return round(ordered[index], 4)


def psi(reference_values: list[float], current_values: list[float], buckets: int = 10) -> float:
    if not reference_values or not current_values:
        return 0.0
    ordered = sorted(reference_values)
    cuts = [ordered[min(int(len(ordered) * idx / buckets), len(ordered) - 1)] for idx in range(1, buckets)]
    boundaries = [-math.inf, *cuts, math.inf]
    value = 0.0
    for left, right in zip(boundaries, boundaries[1:]):
        ref_count = sum(1 for item in reference_values if left <= item < right)
        cur_count = sum(1 for item in current_values if left <= item < right)
        ref_share = max(ref_count / len(reference_values), 0.0001)
        cur_share = max(cur_count / len(current_values), 0.0001)
        value += (cur_share - ref_share) * math.log(cur_share / ref_share)
    return round(value, 6)


def run_checks(reference: list[dict], current: list[dict]) -> dict:
    checks = []
    ref_means = {feature: round(mean(reference, feature), 4) for feature in FEATURES}
    cur_means = {feature: round(mean(current, feature), 4) for feature in FEATURES}
    deltas = {feature: round(cur_means[feature] - ref_means[feature], 4) for feature in FEATURES}
    drift_thresholds = {"age": 4.0, "income": 12000.0, "debt_ratio": 0.12, "utilization": 0.14, "delinquencies": 0.45}
    drifted = {feature: abs(deltas[feature]) > drift_thresholds[feature] for feature in FEATURES}
    psi_scores = {
        feature: psi([float(row[feature]) for row in reference], [float(row[feature]) for row in current])
        for feature in FEATURES
    }
    psi_failed = {feature: score >= 0.2 for feature, score in psi_scores.items()}
    failed_features = sorted({feature for feature in FEATURES if drifted[feature] or psi_failed[feature]})
    checks.append(
        {
            "name": "feature_drift",
            "passed": not any(drifted.values()) and not any(psi_failed.values()),
            "severity": "high" if sum(drifted.values()) + sum(psi_failed.values()) >= 3 else "medium",
            "observed": {"mean_delta": deltas, "psi": psi_scores},
            "failed_features": failed_features,
        }
    )
    ref_score = mean(reference, "risk_score")
    cur_score = mean(current, "risk_score")
    score_delta = round(cur_score - ref_score, 6)
    checks.append(
        {
            "name": "prediction_drift",
            "passed": abs(score_delta) <= 0.08,
            "severity": "high",
            "observed": score_delta,
            "threshold": 0.08,
        }
    )
    latencies = [float(row["latency_ms"]) for row in current]
    p95 = percentile(latencies, 0.95)
    p99 = percentile(latencies, 0.99)
    checks.append({"name": "latency_slo", "passed": p95 <= 85.0, "severity": "medium", "observed": p95, "p99": p99, "threshold": 85.0})
    error_rate = round(sum(1 for row in current if row.get("status") != "success") / max(len(current), 1), 4)
    checks.append({"name": "error_rate", "passed": error_rate <= 0.02, "severity": "high", "observed": error_rate, "threshold": 0.02})
    null_count = sum(1 for row in current for feature in FEATURES if row.get(feature) in {"", None})
    checks.append({"name": "null_rate", "passed": null_count == 0, "severity": "medium", "observed": null_count, "threshold": 0})
    latest_timestamp = max(datetime.fromisoformat(row["timestamp"]) for row in current)
    freshness_minutes = round((datetime(2026, 7, 7, 13, 30, tzinfo=timezone.utc) - latest_timestamp).total_seconds() / 60, 2)
    checks.append({"name": "freshness", "passed": freshness_minutes <= 20.0, "severity": "medium", "observed": freshness_minutes, "threshold": 20.0})
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "reference_means": ref_means,
        "current_means": cur_means,
        "psi": psi_scores,
    }


def likely_root_cause(failed_checks: list[dict]) -> str:
    names = {check["name"] for check in failed_checks}
    if {"feature_drift", "prediction_drift"} <= names and {"latency_slo", "error_rate"} & names:
        return "compound_population_shift_and_serving_degradation"
    if "feature_drift" in names and "prediction_drift" in names:
        return "upstream_population_shift"
    if "latency_slo" in names and "error_rate" in names:
        return "serving_capacity_or_dependency_failure"
    if "freshness" in names:
        return "telemetry_pipeline_delay"
    if "null_rate" in names:
        return "request_contract_violation"
    return "model_or_data_quality_degradation"
