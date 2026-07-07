# Advanced Reliability Control Plane

This repo now includes a reliability planner in `src/model_observability_platform/reliability_control.py`.

## Operator Workflow

- Run `make demo` to generate reference/current telemetry, checks, incidents, and dashboard output.
- Run `make reliability-plan` to generate `reports/reliability_control_plan.json`.
- Inspect the recommended action: `healthy`, `watch`, `open_incident_review`, or `page_and_freeze_rollouts`.

## What The Planner Uses

- Open incident count and incident severity.
- Failed drift, freshness, latency, and error-rate checks.
- Error-budget burn rate for a 99.5 percent availability target.
- Impacted assets and rollback decision path.

## Production Signal

The planner turns observability from passive charts into an action system. It decides when reliability issues should freeze promotions, page an owner, or remain in watch mode.
