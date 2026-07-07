from __future__ import annotations

from pathlib import Path

from .io import write_json


def build_disaster_recovery_plan(root: str | Path) -> dict:
    root = Path(root)
    plan = {
        "platform": "model-observability-incident-platform",
        "rpo_minutes": 15,
        "rto_minutes": 60,
        "backup_policy": {
            "cluster_objects": "Velero observability namespace backup every 15 minutes",
            "persistent_volumes": "CSI VolumeSnapshot with Retain deletion policy",
            "incident_records": "append-only incident export with dedupe fingerprints",
            "drift_baselines": "versioned reference windows and eval reports",
        },
        "restore_sequence": [
            {"order": 1, "asset": "namespace and observability CRDs", "validation": "PrometheusRule and collectors accepted"},
            {"order": 2, "asset": "telemetry baselines", "validation": "reference window hashes match"},
            {"order": 3, "asset": "incident records", "validation": "dedupe fingerprints restored"},
            {"order": 4, "asset": "alert routing", "validation": "webhook dry-run succeeds"},
            {"order": 5, "asset": "freshness and burn-rate checks", "validation": "reliability plan produces expected action"},
        ],
        "drills": [
            "restore into ml-observability-restore namespace monthly",
            "replay one telemetry window and verify incident dedupe",
            "run reliability plan before re-enabling alert webhook sends",
        ],
    }
    write_json(root / "reports" / "disaster_recovery_plan.json", plan)
    return plan
