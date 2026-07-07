from __future__ import annotations

from math import ceil
from pathlib import Path

from .io import write_json


CPU_MONTHLY_USD = 28.0
MEMORY_GIB_MONTHLY_USD = 3.5


WORKLOAD_PROFILES = [
    {
        "name": "telemetry-collector",
        "class": "observability_ingestion",
        "current_cpu_m": 800,
        "current_memory_mib": 1024,
        "current_replicas": 3,
        "cpu_p95_m": 450,
        "memory_p99_mib": 580,
        "forecast_units": 900,
        "target_units_per_replica": 300,
        "min_replicas": 2,
        "max_replicas": 8,
        "min_cpu_m": 350,
        "min_memory_mib": 512,
    },
    {
        "name": "incident-router",
        "class": "incident_response",
        "current_cpu_m": 500,
        "current_memory_mib": 512,
        "current_replicas": 2,
        "cpu_p95_m": 180,
        "memory_p99_mib": 250,
        "forecast_units": 80,
        "target_units_per_replica": 80,
        "min_replicas": 2,
        "max_replicas": 4,
        "min_cpu_m": 200,
        "min_memory_mib": 256,
    },
    {
        "name": "drift-evaluator",
        "class": "scheduled_analysis",
        "current_cpu_m": 1500,
        "current_memory_mib": 2048,
        "current_replicas": 1,
        "cpu_p95_m": 640,
        "memory_p99_mib": 1100,
        "forecast_units": 2,
        "target_units_per_replica": 1,
        "min_replicas": 1,
        "max_replicas": 3,
        "min_cpu_m": 500,
        "min_memory_mib": 768,
    },
]


def _round_up(value: float, step: int) -> int:
    return int(ceil(value / step) * step)


def _resource_cost(cpu_m: int, memory_mib: int, replicas: int) -> float:
    cpu_cost = (cpu_m / 1000) * replicas * CPU_MONTHLY_USD
    memory_cost = (memory_mib / 1024) * replicas * MEMORY_GIB_MONTHLY_USD
    return round(cpu_cost + memory_cost, 2)


def _action(current: int, recommended: int, resource: str) -> str:
    if recommended < current * 0.85:
        return f"lower_{resource}_request"
    if recommended > current * 1.15:
        return f"raise_{resource}_request"
    return f"keep_{resource}_request"


def _recommend(profile: dict) -> dict:
    cpu_request_m = _round_up(max(profile["min_cpu_m"], profile["cpu_p95_m"] * 1.35), 25)
    memory_request_mib = _round_up(max(profile["min_memory_mib"], profile["memory_p99_mib"] * 1.20), 32)
    memory_limit_mib = _round_up(memory_request_mib * 1.25, 32)
    replicas = max(profile["min_replicas"], ceil(profile["forecast_units"] / profile["target_units_per_replica"]))
    replicas = min(profile["max_replicas"], replicas)
    current_cost = _resource_cost(profile["current_cpu_m"], profile["current_memory_mib"], profile["current_replicas"])
    recommended_cost = _resource_cost(cpu_request_m, memory_request_mib, replicas)
    return {
        "workload": profile["name"],
        "class": profile["class"],
        "current": {
            "cpu_m": profile["current_cpu_m"],
            "memory_mib": profile["current_memory_mib"],
            "replicas": profile["current_replicas"],
            "monthly_cost_usd": current_cost,
        },
        "observed": {
            "cpu_p95_m": profile["cpu_p95_m"],
            "memory_p99_mib": profile["memory_p99_mib"],
            "forecast_units": profile["forecast_units"],
        },
        "recommended": {
            "cpu_request_m": cpu_request_m,
            "memory_request_mib": memory_request_mib,
            "memory_limit_mib": memory_limit_mib,
            "replicas": replicas,
            "monthly_cost_usd": recommended_cost,
        },
        "monthly_cost_delta_usd": round(recommended_cost - current_cost, 2),
        "actions": [
            _action(profile["current_cpu_m"], cpu_request_m, "cpu"),
            _action(profile["current_memory_mib"], memory_request_mib, "memory"),
            "prewarm_replicas" if replicas > profile["current_replicas"] else "keep_replica_floor",
        ],
    }


def build_resource_optimization_report(root: str | Path) -> dict:
    root = Path(root)
    recommendations = [_recommend(profile) for profile in WORKLOAD_PROFILES]
    report = {
        "platform": "model-observability-incident-platform",
        "method": {
            "cpu_request": "ceil(max(min_cpu, cpu_p95 * 1.35), 25m)",
            "memory_request": "ceil(max(min_memory, memory_p99 * 1.20), 32Mi)",
            "memory_limit": "ceil(memory_request * 1.25, 32Mi)",
            "replicas": "ceil(forecast_units / target_units_per_replica) bounded by min/max replicas",
        },
        "guardrails": [
            "run VPA in Off mode so observability capacity changes cannot hide incidents",
            "reserve Airflow pool slots for incident creation before drift reports",
            "scale collectors on ingestion throughput and memory pressure, not only CPU",
            "keep alert thresholds stable while right-sizing resources",
        ],
        "recommendations": recommendations,
        "summary": {
            "workload_count": len(recommendations),
            "estimated_monthly_delta_usd": round(sum(item["monthly_cost_delta_usd"] for item in recommendations), 2),
            "needs_human_review": any("raise_memory_request" in item["actions"] for item in recommendations),
        },
    }
    write_json(root / "reports" / "resource_optimization.json", report)
    return report
