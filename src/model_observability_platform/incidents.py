from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .checks import likely_root_cause
from .io import read_jsonl, write_json


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(check: dict) -> str:
    source = f"{check.get('name')}:{check.get('severity')}:{check.get('failed_features', check.get('observed'))}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def severity_rank(values: list[str]) -> str:
    if "critical" in values:
        return "critical"
    if "high" in values:
        return "high"
    if "medium" in values:
        return "medium"
    return "low"


def create_incidents(root: str | Path, report: dict) -> dict:
    root = Path(root)
    existing = {row["fingerprint"]: row for row in read_jsonl(root / "incidents" / "incidents.jsonl")}
    failed = [check for check in report["checks"] if not check["passed"]]
    created = []
    for check in failed:
        fp = fingerprint(check)
        if fp in existing:
            continue
        incident = {
            "incident_id": f"inc_{fp}",
            "fingerprint": fp,
            "status": "open",
            "check": check["name"],
            "severity": check.get("severity", "medium"),
            "observed": check.get("observed"),
            "created_at": utc_iso(),
            "root_cause": likely_root_cause(failed),
            "next_action": next_action(check["name"]),
        }
        created.append(incident)
    all_incidents = list(existing.values()) + created
    root.joinpath("incidents").mkdir(parents=True, exist_ok=True)
    with (root / "incidents" / "incidents.jsonl").open("w", encoding="utf-8") as handle:
        for incident in all_incidents:
            import json

            handle.write(json.dumps(incident, sort_keys=True) + "\n")
    summary = {
        "created_count": len(created),
        "open_count": sum(1 for incident in all_incidents if incident["status"] == "open"),
        "severity": severity_rank([incident["severity"] for incident in all_incidents if incident["status"] == "open"]),
        "incidents": all_incidents,
    }
    write_json(root / "reports" / "incident_summary.json", summary)
    return summary


def next_action(check_name: str) -> str:
    actions = {
        "feature_drift": "Compare current traffic source mix with reference window and decide whether retraining is needed.",
        "prediction_drift": "Review score distribution by segment and pause promotion until explained.",
        "latency_slo": "Check KServe autoscaling, pod readiness, and upstream dependency latency.",
        "error_rate": "Inspect rejected and failed prediction logs for common exception signatures.",
        "freshness": "Check telemetry ingestion job and alert routing.",
        "null_rate": "Validate upstream request contract and quarantine malformed payloads.",
    }
    return actions.get(check_name, "Assign owner and inspect recent model serving changes.")
