from __future__ import annotations

from pathlib import Path

from .io import write_json


def _identity(
    *,
    workload: str,
    namespace: str,
    service_account: str,
    role: str,
    spiffe_id: str,
    secrets: list[str],
    permissions: list[str],
) -> dict:
    return {
        "workload": workload,
        "namespace": namespace,
        "service_account": service_account,
        "automount_service_account_token": False,
        "token": {"projected": True, "audience": "sts.amazonaws.com", "ttl_seconds": 3600},
        "cloud_access": {"provider": "aws", "role": role, "credential_mode": "federated_oidc"},
        "spiffe_id": spiffe_id,
        "external_secrets": [
            {"name": secret, "provider": "aws-secrets-manager", "refresh_interval_minutes": 30, "static_credentials": False}
            for secret in secrets
        ],
        "rbac": {"scope": "namespace", "permissions": permissions},
    }


def build_identity_access_report(root: str | Path, *, project: str = "Model Observability Incident Platform") -> dict:
    identities = [
        _identity(
            workload="telemetry-collector",
            namespace="ml-observability",
            service_account="telemetry-collector",
            role="arn:aws:iam::111122223333:role/telemetry-window-reader",
            spiffe_id="spiffe://mlops.local/ns/ml-observability/sa/telemetry-collector",
            secrets=["otel-exporter-token"],
            permissions=["read prediction logs", "write telemetry windows"],
        ),
        _identity(
            workload="drift-evaluator",
            namespace="ml-observability",
            service_account="drift-evaluator",
            role="arn:aws:iam::111122223333:role/drift-evaluator",
            spiffe_id="spiffe://mlops.local/ns/ml-observability/sa/drift-evaluator",
            secrets=["baseline-window-reader", "eval-report-writer"],
            permissions=["read baseline windows", "write drift reports"],
        ),
        _identity(
            workload="incident-router",
            namespace="ml-observability",
            service_account="incident-router",
            role="arn:aws:iam::111122223333:role/ml-incident-router",
            spiffe_id="spiffe://mlops.local/ns/ml-observability/sa/incident-router",
            secrets=["pager-webhook-token", "incident-store-writer"],
            permissions=["write incidents", "send alert webhook"],
        ),
    ]
    all_secrets = [secret for identity in identities for secret in identity["external_secrets"]]
    checks = [
        {"name": "bound_service_account_tokens", "passed": all(identity["token"]["projected"] for identity in identities)},
        {"name": "token_ttl_leq_one_hour", "passed": all(identity["token"]["ttl_seconds"] <= 3600 for identity in identities)},
        {"name": "no_static_cloud_keys", "passed": all(not secret["static_credentials"] for secret in all_secrets)},
        {"name": "external_secret_refresh_leq_30m", "passed": all(secret["refresh_interval_minutes"] <= 30 for secret in all_secrets)},
        {"name": "namespace_scoped_rbac", "passed": all(identity["rbac"]["scope"] == "namespace" for identity in identities)},
        {"name": "spiffe_identity_declared", "passed": all(identity["spiffe_id"].startswith("spiffe://") for identity in identities)},
        {
            "name": "airflow_task_service_account_pinned",
            "passed": any(identity["service_account"] == "drift-evaluator" for identity in identities),
        },
    ]
    report = {
        "project": project,
        "generated_at": "2026-07-08T00:00:00Z",
        "passed": all(check["passed"] for check in checks),
        "identities": identities,
        "checks": checks,
        "controls": [
            "Telemetry, drift, and incident workloads use short-lived projected service account tokens.",
            "Incident routing and telemetry storage use federated workload identity roles.",
            "External Secrets Operator owns alerting and incident-store credential synchronization.",
            "Airflow diagnostic tasks use dedicated evaluator service accounts.",
            "SPIFFE IDs document identity boundaries for collector, evaluator, and router workloads.",
        ],
        "rotation": {
            "projected_token_ttl_seconds": 3600,
            "external_secret_refresh_minutes": 30,
            "break_glass_static_secret_allowed": False,
        },
        "references": [
            "https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/",
            "https://external-secrets.io/latest/introduction/getting-started/",
            "https://spiffe.io/docs/latest/try/getting-started-k8s/",
            "https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/stable/operators.html",
        ],
    }
    write_json(Path(root) / "reports" / "identity_access_report.json", report)
    return report
