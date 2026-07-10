# Runtime Incident Recovery Runbook

## Scope

Use this runbook when the model-observability API is unavailable, rejects a
retry, cannot update incident state, or reports an unexpected release freeze.
It covers the local and Compose runtime. Kubernetes manifests remain a
deployment mapping until a cluster run is separately verified.

## First Five Minutes

1. Check liveness and readiness:

   ```bash
   curl -fsS http://127.0.0.1:8081/health/live
   curl -fsS http://127.0.0.1:8081/health/ready
   ```

2. Capture bounded runtime state:

   ```bash
   curl -fsS http://127.0.0.1:8081/v1/runtime
   curl -fsS http://127.0.0.1:8081/v1/incidents
   curl -fsS http://127.0.0.1:8081/metrics
   ```

3. Preserve the request ID, trace ID, evaluation ID, policy version, and the
   affected incident's event history. Do not attach raw telemetry to a ticket.

4. Stop automated release promotion while a high or critical incident remains
   active. The API decision is guidance; production enforcement belongs in the
   deployment control plane.

## Symptom Matrix

| Symptom | Likely cause | Evidence | First action |
| --- | --- | --- | --- |
| Readiness 503 | State database unavailable or schema mismatch | `/health/ready`, container logs, state volume | Keep service out of rotation and inspect volume ownership/integrity |
| Evaluation 409 | Idempotency key reused with changed payload | Error body and caller request log | Generate a new evaluation ID only for genuinely new work |
| Transition 409, version mismatch | Another operator or recovery evaluation changed the incident | `GET /v1/incidents/{id}` and event history | Re-read state and decide from the newest version |
| Transition 409, key mismatch | Transition key reused for a different command | Error body and caller log | Do not overwrite history; use a new key for a new command |
| Evaluation 503 | Concurrency queue deadline exceeded | HTTP metrics and logs | Retry with jitter after `Retry-After`; reduce upstream concurrency |
| Repeated release freeze | Failed checks remain active or incident reopened | Evaluation report and incident events | Confirm signal quality, then repair the source rather than manually clearing repeatedly |
| OTLP export failure | Collector unavailable or endpoint misconfigured | Exporter logs; API health remains green | Restore collector separately; do not block incident state writes |

## SQLite State Failure

1. Stop the control-plane process before copying database files.
2. Capture `incidents.sqlite3`, `incidents.sqlite3-wal`, and
   `incidents.sqlite3-shm` together when they exist.
3. Confirm the volume is writable by UID/GID 65532.
4. Run a read-only integrity check on a copy:

   ```bash
   sqlite3 incidents.sqlite3 'PRAGMA integrity_check;'
   ```

5. Restore the most recent validated backup to a new volume. Do not delete a
   WAL file independently from its database.
6. Run `make api-smoke` against the restored service before returning it to
   use.

For a real environment, automate consistent snapshots and restore rehearsals;
the repository does not claim that a local Docker volume is a backup system.

## Safe Replay

Re-send the exact original evaluation payload with the original
`evaluation_id`. A successful response with `X-Idempotent-Replay: true` proves
that the stored decision was returned without mutating occurrence counts.

If the source payload changed, create a new evaluation ID. Reusing the old ID
to force an overwrite is intentionally rejected.

## Incident Recovery

1. Fix the telemetry, serving, or upstream cause.
2. Submit a new healthy evaluation window.
3. Confirm `recovery_observed` in each affected incident history.
4. Submit a second independent healthy window.
5. Confirm `auto_resolved`, zero active incidents, and an unfrozen release
   decision.
6. If policy allows manual resolution, use the newest incident version and a
   unique transition ID. Record why automatic evidence was insufficient.

## Rollback

The API is stateless apart from its mounted database. Roll back the image while
preserving the state volume only when the database schema is backward
compatible. Schema version `1` is checked at readiness.

For an incompatible future migration:

1. freeze writes
2. snapshot and verify the database
3. run a tested down-migration or restore procedure
4. deploy the previous image against a compatible copy
5. run the runtime contract before reopening traffic

## Closure Evidence

Attach only bounded metadata:

- incident and evaluation IDs
- policy and model versions
- first failure, acknowledgement, and resolution timestamps
- failed check names and severities
- root-cause category and repair action
- recovery event sequence
- trace IDs and dashboard/report artifact hashes

Do not attach raw feature values or full telemetry windows unless an approved
privacy workflow explicitly requires them.
