# Incident Response Runbook

## Feature And Prediction Drift

Symptoms:

- `feature_drift` fails
- `prediction_drift` fails
- root cause mentions population shift

Actions:

1. Compare current and reference feature means.
2. Segment by traffic source, product, geography, or customer cohort.
3. Check whether an upstream product launch or routing change occurred.
4. Decide whether to retrain, recalibrate, or update thresholds.
5. Avoid model promotion until the shift is explained.

## Latency And Error Rate

Actions:

1. Inspect p95 and p99 latency separately.
2. Check KServe pods, autoscaling, and cold starts.
3. Check upstream feature service or database latency.
4. Roll back if a new model version caused the regression.
5. Add capacity or reduce model complexity if the issue is sustained.

## Freshness Failure

Actions:

1. Check telemetry ingestion jobs.
2. Verify event timestamps and clock skew.
3. Confirm alert delivery paths.
4. Backfill missing telemetry before closing the incident.

## Duplicate Alert Prevention

The incident store deduplicates using a fingerprint. If an incident is already open, repeated monitor runs should update evidence in production rather than create new incident IDs.

