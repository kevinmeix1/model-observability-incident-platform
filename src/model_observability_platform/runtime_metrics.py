from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from .telemetry import FEATURES

CHECKS = (
    "feature_drift",
    "prediction_drift",
    "latency_slo",
    "error_rate",
    "null_rate",
    "freshness",
)
SEVERITIES = ("low", "medium", "high", "critical")
NOTIFICATION_STATES = ("pending", "in_flight", "delivered", "dead_letter")
NOTIFICATION_OUTCOMES = (
    "in_flight",
    "lease_expired",
    "retry_scheduled",
    "delivered",
    "dead_letter",
)


class RuntimeMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.http_requests = Counter(
            "model_observability_http_requests_total",
            "HTTP requests by bounded route and response class.",
            ("method", "route", "status_class"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "model_observability_http_request_duration_seconds",
            "End-to-end HTTP request duration by bounded route.",
            ("method", "route"),
            buckets=(0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
            registry=self.registry,
        )
        self.evaluations = Counter(
            "model_observability_evaluations_total",
            "Accepted telemetry evaluations by outcome.",
            ("outcome",),
            registry=self.registry,
        )
        self.evaluation_duration = Histogram(
            "model_observability_evaluation_duration_seconds",
            "Telemetry evaluation and durable incident update duration.",
            ("outcome",),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
            registry=self.registry,
        )
        self.check_failures = Counter(
            "model_observability_check_failures_total",
            "Failed monitoring checks by bounded check name.",
            ("check",),
            registry=self.registry,
        )
        self.check_status = Gauge(
            "model_observability_check_status",
            "Latest check result, where one is passing and zero is failing.",
            ("check",),
            registry=self.registry,
        )
        self.feature_psi = Gauge(
            "model_observability_feature_psi_ratio",
            "Latest population stability index by bounded feature name.",
            ("feature",),
            registry=self.registry,
        )
        self.open_incidents = Gauge(
            "model_observability_open_incidents",
            "Current non-resolved incidents by severity.",
            ("severity",),
            registry=self.registry,
        )
        self.incident_transitions = Counter(
            "model_observability_incident_transitions_total",
            "Durable incident lifecycle transitions.",
            ("transition", "severity"),
            registry=self.registry,
        )
        self.notification_depth = Gauge(
            "model_observability_notification_outbox_events",
            "Current transactional outbox events by bounded delivery state.",
            ("status",),
            registry=self.registry,
        )
        self.notification_attempts = Gauge(
            "model_observability_notification_delivery_attempts",
            "Persisted notification delivery attempts by bounded outcome.",
            ("outcome",),
            registry=self.registry,
        )
        self.last_evaluation = Gauge(
            "model_observability_last_evaluation_timestamp_seconds",
            "Unix timestamp of the latest accepted telemetry evaluation.",
            registry=self.registry,
        )
        for check in CHECKS:
            self.check_status.labels(check).set(0)
            self.check_failures.labels(check)
        for feature in FEATURES:
            self.feature_psi.labels(feature).set(0)
        for severity in SEVERITIES:
            self.open_incidents.labels(severity).set(0)
        for status in NOTIFICATION_STATES:
            self.notification_depth.labels(status).set(0)
        for outcome in NOTIFICATION_OUTCOMES:
            self.notification_attempts.labels(outcome).set(0)

    def observe_http(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        status_class = f"{status_code // 100}xx"
        self.http_requests.labels(method, route, status_class).inc()
        self.http_duration.labels(method, route).observe(duration_seconds)

    def observe_evaluation(
        self,
        report: dict[str, Any],
        *,
        replayed: bool,
        duration_seconds: float,
    ) -> None:
        outcome = "replayed" if replayed else ("passed" if report["passed"] else "failed")
        self.evaluations.labels(outcome).inc()
        self.evaluation_duration.labels(outcome).observe(duration_seconds)
        if replayed:
            return
        for check in report["checks"]:
            name = str(check["name"])
            if name not in CHECKS:
                continue
            passed = bool(check["passed"])
            self.check_status.labels(name).set(1 if passed else 0)
            if not passed:
                self.check_failures.labels(name).inc()
        for feature, value in report.get("psi", {}).items():
            if feature in FEATURES:
                self.feature_psi.labels(feature).set(float(value))
        evaluated_at = report.get("evaluated_at")
        if evaluated_at:
            self.last_evaluation.set(datetime.fromisoformat(evaluated_at).timestamp())
        else:
            self.last_evaluation.set(time.time())

    def observe_transition(self, *, transition: str, severity: str) -> None:
        if severity not in SEVERITIES:
            severity = "low"
        self.incident_transitions.labels(transition, severity).inc()

    def refresh_incidents(self, summary: dict[str, Any]) -> None:
        counts = summary.get("open_by_severity", {})
        for severity in SEVERITIES:
            self.open_incidents.labels(severity).set(int(counts.get(severity, 0)))
        notification_counts = summary.get("notifications_by_status", {})
        for status in NOTIFICATION_STATES:
            self.notification_depth.labels(status).set(
                int(notification_counts.get(status, 0))
            )
        attempt_counts = summary.get("notification_attempts_by_outcome", {})
        for outcome in NOTIFICATION_OUTCOMES:
            self.notification_attempts.labels(outcome).set(
                int(attempt_counts.get(outcome, 0))
            )
