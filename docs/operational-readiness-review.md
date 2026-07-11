# Operational Readiness Review

`make demo` writes `reports/operational_readiness_review.json` as the operator-facing packet for observability control-plane changes.

The review aggregates incident severity, release admission, SLO burn rate, root-cause evidence, alert routing, diagnostic performance budgets, AI workload telemetry, and supply-chain provenance. It is designed to explain whether a monitoring, alerting, or diagnostic change can proceed while incidents are active.

The packet is intentionally fail-closed. If incident control is missing, page-level burn is active, root-cause evidence is incomplete, alert routing is not ready, provenance is absent, or diagnostic budgets fail, the recommendation becomes remediation instead of approval.

Interview review prompts:

- The platform shows what failed, who owns it, and which downstream assets are at risk.
- Incident, SLO, alert-routing, root-cause, and provenance evidence are reviewed together.
- The packet works as both demo evidence and a realistic change-review artifact.
