# Indexed Job Resilience

Incident response is also a finite batch problem: freshness checks, drift checks, root-cause probes, impact analysis, alert routing, rollback-freeze validation, and dashboard publishing all need deterministic shard ownership and bounded retry behavior.

## Kubernetes Controls

- `completionMode: Indexed` gives every incident shard a deterministic `JOB_COMPLETION_INDEX`.
- `backoffLimitPerIndex` limits retries for one bad source window without delaying unrelated checks.
- `maxFailedIndexes` stops wasteful waves when the incident is too degraded to continue automatically.
- `podFailurePolicy` marks bad source windows as `FailIndex`, image/config problems as `FailJob`, and node disruption as `Ignore`.
- `successPolicy` can declare quorum success while preserving failed-index evidence for targeted recovery.

## Airflow Backfill Create

Historical incident repair uses failed-only reprocessing:

```bash
airflow backfill create \
  --dag-id model_reliability_control_plane \
  --from-date 2026-07-01 \
  --to-date 2026-07-07 \
  --reprocess-behavior failed \
  --max-active-runs 2 \
  --run-backwards
```

Use reverse ordering so recent incident evidence recovers first. Keep backfill concurrency lower than live incident creation and alert-routing concurrency.

## Failure Semantics

| Failure | Policy | Outcome |
| --- | --- | --- |
| Bad telemetry window | `FailIndex` | Mark that check failed and continue unrelated incident probes. |
| Bad image or command | `FailJob` | Stop the wave because retries would be wasteful. |
| Node drain or preemption | `Ignore` | Do not count infrastructure churn against the retry budget. |
| Too many failed shards | `maxFailedIndexes` | Stop the wave and page for manual incident triage. |

## Recovery Flow

1. Inspect `status.failedIndexes` and `status.completedIndexes`.
2. Rerun only failed telemetry, drift, root-cause, or publish shards.
3. Keep incident creation, rollback freeze, and alert routing above historical recovery in Airflow pools and Kueue priority.
4. Attach `indexed_job_resilience_plan.json` to the incident record.
