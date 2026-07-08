# Semantic Telemetry Contract

`make semantic-telemetry-plan` writes `.local/reports/semantic_telemetry_plan.json` and validates the telemetry fields the incident workflow depends on.

## What It Shows

- OpenTelemetry-style service and Kubernetes resource attributes on trace spans.
- GenAI-style model, token, and estimated cost fields for serving degradation analysis.
- Incident IDs, severity, root-cause hints, SLO burn rate, and detection latency attached to reliability spans.
- Gateway objective and model-version pivots so a page can connect failed checks to serving routes.
- Collector-side redaction of prompts, responses, request bodies, and incident payloads before export.

## Production Notes

The important production pattern is the contract, not the demo values. Incident automation should fail closed when required attributes are missing, because dashboards and runbooks cannot reliably answer "which model, route, pod, SLO, and incident changed?" from free-form logs. The collector keeps high-value route, model, cost, and SLO context while stripping payload fields by default.
