from __future__ import annotations

from pathlib import Path

from .io import read_json, write_json


def burn_rate(error_ratio: float, target: float) -> float:
    return round(error_ratio / max(1.0 - target, 0.0001), 4)


def remaining_budget_pct(error_ratio: float, target: float) -> float:
    budget = max(1.0 - target, 0.0001)
    return round(max(0.0, 100.0 * (1.0 - error_ratio / budget)), 2)


def _check(report: dict, name: str) -> dict:
    return next((check for check in report.get("checks", []) if check.get("name") == name), {})


def _slo(name: str, *, target: float, error_ratio: float, owner: str) -> dict:
    burn = burn_rate(error_ratio, target)
    if burn >= 14.4:
        status = "page"
    elif burn >= 6.0:
        status = "hold_rollout"
    elif burn >= 1.0:
        status = "ticket"
    else:
        status = "healthy"
    return {
        "name": name,
        "target": target,
        "error_ratio": round(error_ratio, 6),
        "burn_rate": burn,
        "remaining_error_budget_pct": remaining_budget_pct(error_ratio, target),
        "status": status,
        "owner": owner,
    }


def build_slo_report(root: str | Path) -> dict:
    root = Path(root)
    report = read_json(root / "reports" / "observability_report.json")
    reliability = read_json(root / "reports" / "reliability_control_plan.json")
    error_rate = float(_check(report, "error_rate").get("observed", 1.0))
    latency_ok = bool(_check(report, "latency_slo").get("passed", False))
    freshness_ok = bool(_check(report, "freshness").get("passed", False))
    drift_ok = bool(_check(report, "feature_drift").get("passed", False)) and bool(_check(report, "prediction_drift").get("passed", False))
    slos = [
        _slo("observed_serving_availability", target=0.995, error_ratio=error_rate, owner="ml-reliability"),
        _slo("latency_slo_health", target=0.99, error_ratio=0.0 if latency_ok else 1.0, owner="serving"),
        _slo("telemetry_freshness", target=0.99, error_ratio=0.0 if freshness_ok else 1.0, owner="data-platform"),
        _slo("drift_signal_health", target=0.95, error_ratio=0.0 if drift_ok else 1.0, owner="ml-reliability"),
    ]
    max_burn = max(item["burn_rate"] for item in slos)
    if max_burn >= 14.4 or reliability.get("recommended_action") == "page_and_freeze_rollouts":
        action = "freeze_rollouts_and_page"
    elif max_burn >= 6.0:
        action = "hold_rollouts"
    elif max_burn >= 1.0:
        action = "open_reliability_ticket"
    else:
        action = "healthy"
    slo_report = {
        "platform": "model-observability-incident-platform",
        "policy": {
            "window": "30d",
            "multiwindow_burn_rates": [
                {"name": "fast_page", "short_window": "5m", "long_window": "1h", "burn_rate": 14.4, "budget_consumed": "2%"},
                {"name": "slow_page", "short_window": "30m", "long_window": "6h", "burn_rate": 6.0, "budget_consumed": "5%"},
                {"name": "ticket", "short_window": "6h", "long_window": "3d", "burn_rate": 1.0, "budget_consumed": "10%"},
            ],
        },
        "slos": slos,
        "max_burn_rate": max_burn,
        "recommended_action": action,
        "release_freeze": action in {"freeze_rollouts_and_page", "hold_rollouts"},
        "reliability_action": reliability.get("recommended_action"),
    }
    write_json(root / "reports" / "slo_error_budget.json", slo_report)
    return slo_report
