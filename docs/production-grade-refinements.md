# Production-Grade Refinements

This project turns monitoring into incident response.

## Drift Detection

- Feature drift uses both mean-delta checks and PSI-style distribution checks.
- Prediction drift is tracked independently from feature drift.
- This separation helps distinguish population shift, calibration issues, and serving regressions.

## SLO Monitoring

- Latency p95 and p99 are tracked.
- Error rate is evaluated as a serving reliability gate.
- Freshness prevents stale telemetry from creating false confidence.

## Incident Management

- Incidents are deduplicated by stable fingerprints.
- Severity and next action are assigned at creation time.
- Root-cause hints distinguish population shift, serving degradation, freshness delay, and contract violations.

## Why This Matters

A dashboard that does not create actionable incidents is easy to ignore. This project models the production loop from failed check to deduplicated incident and runbook action.
