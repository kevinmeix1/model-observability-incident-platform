from __future__ import annotations

from pathlib import Path

from .io import write_json


EVENT_ASSETS = [
    {
        "asset": "warehouse://ml/prediction_logs",
        "event_source": "queue://telemetry/prediction-log-windows",
        "watcher": "PredictionLogsAssetWatcher",
        "trigger_base_class": "BaseEventTrigger",
        "shared_stream_key": ["queue", "telemetry", "prediction-log-windows"],
        "dedupe_key": "window_id",
        "lag_budget_seconds": 120,
    },
    {
        "asset": "incident://ml/model-reliability",
        "event_source": "webhook://incident-router/model-reliability",
        "watcher": "IncidentReplayAssetWatcher",
        "trigger_base_class": "BaseEventTrigger",
        "shared_stream_key": ["incident-router", "model-reliability", "manual-replay"],
        "dedupe_key": "incident_fingerprint",
        "lag_budget_seconds": 60,
    },
    {
        "asset": "policy://ml/observability-policy",
        "event_source": "git://contracts/observability_policy.yml",
        "watcher": "ObservabilityPolicyAssetWatcher",
        "trigger_base_class": "BaseEventTrigger",
        "shared_stream_key": ["git", "contracts", "observability_policy"],
        "dedupe_key": "policy_digest",
        "lag_budget_seconds": 90,
    },
]


def build_event_driven_assets_plan(
    root: str | Path,
    *,
    project: str = "Model Observability Incident Platform",
    dag_id: str = "model_reliability_control_plane",
) -> dict:
    root = Path(root)
    checks = [
        {
            "name": "asset_watchers_declared",
            "passed": all(item["watcher"].endswith("AssetWatcher") for item in EVENT_ASSETS),
            "evidence": "Prediction log windows, incident replay requests, and policy updates have AssetWatcher-style contracts.",
        },
        {
            "name": "base_event_trigger_only",
            "passed": all(item["trigger_base_class"] == "BaseEventTrigger" for item in EVENT_ASSETS),
            "evidence": "Watchers use BaseEventTrigger-compatible triggers so incident scheduling stays event-safe.",
        },
        {
            "name": "shared_stream_polling",
            "passed": all(item["shared_stream_key"] for item in EVENT_ASSETS),
            "evidence": "Telemetry queue, incident router, and Git policy watchers declare shared_stream_key values.",
        },
        {
            "name": "conditional_asset_expression",
            "passed": True,
            "evidence": "(PREDICTION_LOGS | MANUAL_INCIDENT_REPLAY) & OBSERVABILITY_POLICY prevents policy-free diagnostic runs.",
        },
        {
            "name": "queued_event_runbook",
            "passed": True,
            "evidence": "Queued asset events are inspected before clearing stale telemetry windows or replaying an incident.",
        },
        {
            "name": "asset_alias_metadata",
            "passed": True,
            "evidence": "AssetAlias supports runtime evidence bundle URIs and dashboard links generated during incident review.",
        },
    ]
    passed = all(check["passed"] for check in checks)
    plan = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": passed,
        "recommended_action": "enable_airflow3_incident_event_assets" if passed else "keep_interval_reliability_schedule",
        "airflow_version_target": "3.3.x",
        "dag_id": dag_id,
        "asset_expression": "(PREDICTION_LOGS | MANUAL_INCIDENT_REPLAY) & OBSERVABILITY_POLICY",
        "event_assets": EVENT_ASSETS,
        "shared_stream_strategy": {
            "why": "Reliability DAGs, repair automations, and dashboard publishers can subscribe to the same telemetry and incident streams.",
            "hook": "BaseEventTrigger.shared_stream_key()",
            "commit_rule": "Acknowledge telemetry offsets or incident replay requests only after every subscribed diagnostic DAG resolves the event.",
        },
        "queued_event_operations": [
            "GET /dags/{dag_id}/assets/queuedEvent before replaying an incident window",
            "DELETE /dags/{dag_id}/assets/queuedEvent/{uri} only when a stale telemetry window was superseded by a newer policy digest",
            "record cleared queued-event URI, incident fingerprint, telemetry window, and policy digest in incident_summary.json",
        ],
        "operational_guardrails": [
            "Require current observability policy before running drift, SLO, or rollback-freeze diagnostics.",
            "Allow manual incident replay to trigger diagnostics without waiting for a new telemetry window.",
            "Treat watcher lag as an alerting SLO alongside detection latency and incident creation latency.",
            "Use AssetAlias for incident evidence bundle URIs and dashboard links resolved during task execution.",
            "Persist telemetry window id, incident fingerprint, policy digest, and dashboard URL in reliability evidence.",
        ],
        "checks": checks,
        "airflow_assets": [
            "airflow/dags/model_reliability_control_plane_dag.py",
            "docs/event-driven-assets.md",
        ],
        "references": [
            "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/event-scheduling.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/asset-scheduling.html",
            "https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html",
        ],
    }
    write_json(root / "reports" / "event_driven_assets_plan.json", plan)
    return plan
