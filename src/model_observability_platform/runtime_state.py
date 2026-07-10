from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .checks import likely_root_cause
from .incidents import next_action

SCHEMA_VERSION = "2"
INCIDENT_STATES = {"open", "acknowledged", "resolved"}
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
NOTIFICATION_STATES = {"pending", "in_flight", "delivered", "dead_letter"}
CLOUD_EVENT_SOURCE = "/model-observability/incident-control-plane"
CLOUD_EVENT_TYPE = "io.github.kevinmeix1.model-observability.incident.lifecycle.v1"


class EvaluationConflict(RuntimeError):
    pass


class TransitionConflict(RuntimeError):
    pass


class IncidentNotFound(RuntimeError):
    pass


class InvalidTransition(RuntimeError):
    pass


class NotificationNotFound(RuntimeError):
    pass


class OutboxLeaseConflict(RuntimeError):
    pass


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def incident_fingerprint(
    *,
    model_name: str,
    model_version: str,
    policy_version: str,
    check_name: str,
) -> str:
    return canonical_hash(
        {
            "model_name": model_name,
            "model_version": model_version,
            "policy_version": policy_version,
            "check_name": check_name,
        }
    )[:20]


def highest_severity(values: list[str]) -> str:
    return max(values or ["low"], key=lambda value: SEVERITY_ORDER.get(value, 0))


def parse_utc(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed.astimezone(UTC)


class IncidentStore:
    def __init__(self, path: str | Path, *, auto_resolve_after: int = 2) -> None:
        if auto_resolve_after < 1:
            raise ValueError("auto_resolve_after must be positive")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.auto_resolve_after = auto_resolve_after
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            existing = connection.execute(
                "SELECT value FROM runtime_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if existing is not None:
                try:
                    existing_version = int(existing["value"])
                except ValueError as exc:
                    raise RuntimeError("runtime schema version is not numeric") from exc
                if existing_version > int(SCHEMA_VERSION):
                    raise RuntimeError(
                        f"runtime schema {existing_version} is newer than supported "
                        f"schema {SCHEMA_VERSION}"
                    )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    occurrence_count INTEGER NOT NULL,
                    healthy_streak INTEGER NOT NULL,
                    observed_json TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    next_action TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    resolved_at TEXT
                );

                CREATE TABLE IF NOT EXISTS incident_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    incident_version INTEGER NOT NULL CHECK (incident_version > 0),
                    actor TEXT NOT NULL,
                    note TEXT,
                    trace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
                );

                CREATE TABLE IF NOT EXISTS transition_requests (
                    transition_id TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notification_outbox (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    incident_id TEXT NOT NULL,
                    incident_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'in_flight', 'delivered', 'dead_letter')
                    ),
                    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
                    available_at TEXT NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id),
                    UNIQUE (incident_id, incident_version)
                );

                CREATE TABLE IF NOT EXISTS notification_attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
                    worker_id TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK (
                        outcome IN (
                            'in_flight', 'lease_expired', 'retry_scheduled',
                            'delivered', 'dead_letter'
                        )
                    ),
                    error TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (event_id) REFERENCES notification_outbox(event_id),
                    UNIQUE (event_id, attempt_number)
                );

                CREATE INDEX IF NOT EXISTS incidents_status_idx
                    ON incidents(status, severity, updated_at);
                CREATE INDEX IF NOT EXISTS incident_events_incident_idx
                    ON incident_events(incident_id, event_id);
                CREATE INDEX IF NOT EXISTS notification_outbox_dispatch_idx
                    ON notification_outbox(status, available_at, sequence);
                CREATE INDEX IF NOT EXISTS notification_outbox_incident_idx
                    ON notification_outbox(incident_id, sequence);
                CREATE INDEX IF NOT EXISTS notification_attempts_event_idx
                    ON notification_attempts(event_id, attempt_number);
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO runtime_metadata(key, value) VALUES (?, ?)",
                ("schema_version", SCHEMA_VERSION),
            )

    @staticmethod
    def _incident(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "incident_id": row["incident_id"],
            "fingerprint": row["fingerprint"],
            "model_name": row["model_name"],
            "model_version": row["model_version"],
            "policy_version": row["policy_version"],
            "check": row["check_name"],
            "severity": row["severity"],
            "status": row["status"],
            "version": row["version"],
            "occurrence_count": row["occurrence_count"],
            "healthy_streak": row["healthy_streak"],
            "observed": json.loads(row["observed_json"]),
            "root_cause": row["root_cause"],
            "next_action": row["next_action"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "updated_at": row["updated_at"],
            "acknowledged_at": row["acknowledged_at"],
            "resolved_at": row["resolved_at"],
        }

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        *,
        incident_id: str,
        event_type: str,
        from_status: str | None,
        to_status: str,
        incident_version: int,
        actor: str,
        note: str | None,
        trace_id: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO incident_events (
                incident_id, event_type, from_status, to_status,
                incident_version, actor, note, trace_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                event_type,
                from_status,
                to_status,
                incident_version,
                actor,
                note,
                trace_id,
                created_at,
            ),
        )
        incident = connection.execute(
            """
            SELECT model_name, model_version, policy_version, check_name, severity
            FROM incidents
            WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()
        if incident is None:
            raise IncidentNotFound(incident_id)
        event_id = "evt_" + canonical_hash(
            {
                "incident_id": incident_id,
                "incident_version": incident_version,
                "event_type": event_type,
            }
        )[:24]
        cloud_event = {
            "specversion": "1.0",
            "id": event_id,
            "source": CLOUD_EVENT_SOURCE,
            "type": CLOUD_EVENT_TYPE,
            "subject": incident_id,
            "time": created_at,
            "datacontenttype": "application/json",
            "traceid": trace_id,
            "data": {
                "incident_id": incident_id,
                "incident_version": incident_version,
                "event_type": event_type,
                "from_status": from_status,
                "to_status": to_status,
                "model_name": incident["model_name"],
                "model_version": incident["model_version"],
                "policy_version": incident["policy_version"],
                "check": incident["check_name"],
                "severity": incident["severity"],
                "actor": actor,
                "note": note,
            },
        }
        connection.execute(
            """
            INSERT INTO notification_outbox (
                event_id, incident_id, incident_version, event_type,
                payload_json, status, attempt_count, available_at,
                created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?)
            """,
            (
                event_id,
                incident_id,
                incident_version,
                event_type,
                json.dumps(cloud_event, sort_keys=True, separators=(",", ":")),
                created_at,
                created_at,
            ),
        )

    @staticmethod
    def _replay(response_json: str, trace_id: str) -> dict[str, Any]:
        response = json.loads(response_json)
        response["replayed"] = True
        response["original_trace_id"] = response.get("trace_id")
        response["trace_id"] = trace_id
        return response

    @staticmethod
    def _notification(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": row["sequence"],
            "event_id": row["event_id"],
            "incident_id": row["incident_id"],
            "incident_version": row["incident_version"],
            "event_type": row["event_type"],
            "cloud_event": json.loads(row["payload_json"]),
            "status": row["status"],
            "attempt_count": row["attempt_count"],
            "available_at": row["available_at"],
            "lease_owner": row["lease_owner"],
            "lease_expires_at": row["lease_expires_at"],
            "last_error": row["last_error"],
            "created_at": row["created_at"],
            "delivered_at": row["delivered_at"],
        }

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT value FROM runtime_metadata WHERE key = 'schema_version'"
                ).fetchone()
            return row is not None and row["value"] == SCHEMA_VERSION
        except sqlite3.Error:
            return False

    def list_incidents(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in INCIDENT_STATES:
            raise ValueError(f"invalid incident status: {status}")
        if severity is not None and severity not in SEVERITY_ORDER:
            raise ValueError(f"invalid severity: {severity}")
        clauses = []
        values: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            values.append(status)
        if severity is not None:
            clauses.append("severity = ?")
            values.append(severity)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM incidents {where} ORDER BY updated_at DESC LIMIT ?",
                values,
            ).fetchall()
        return [self._incident(row) for row in rows]

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            raise IncidentNotFound(incident_id)
        return self._incident(row)

    def incident_events(
        self,
        incident_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        self.get_incident(incident_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT event_id, event_type, from_status, to_status,
                           incident_version, actor, note, trace_id, created_at
                    FROM incident_events
                    WHERE incident_id = ?
                    ORDER BY event_id DESC
                    LIMIT ?
                )
                ORDER BY event_id
                """,
                (incident_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_notifications(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in NOTIFICATION_STATES:
            raise ValueError(f"invalid notification status: {status}")
        where = "WHERE status = ?" if status is not None else ""
        values: list[Any] = [status] if status is not None else []
        values.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM notification_outbox {where} ORDER BY sequence LIMIT ?",
                values,
            ).fetchall()
        return [self._notification(row) for row in rows]

    def notification_attempts(
        self,
        event_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM notification_outbox WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if exists is None:
                raise NotificationNotFound(event_id)
            rows = connection.execute(
                """
                SELECT attempt_id, event_id, attempt_number, worker_id, outcome,
                       error, started_at, completed_at
                FROM notification_attempts
                WHERE event_id = ?
                ORDER BY attempt_number DESC
                LIMIT ?
                """,
                (event_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def claim_notifications(
        self,
        *,
        worker_id: str,
        limit: int = 10,
        lease_seconds: float = 30.0,
        claimed_at: str | datetime | None = None,
    ) -> list[dict[str, Any]]:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = parse_utc(claimed_at or datetime.now(UTC))
        now_iso = now.isoformat()
        lease_expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT candidate.*
                FROM notification_outbox AS candidate
                WHERE (
                    (candidate.status = 'pending' AND candidate.available_at <= ?)
                    OR (
                        candidate.status = 'in_flight'
                        AND candidate.lease_expires_at IS NOT NULL
                        AND candidate.lease_expires_at <= ?
                    )
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM notification_outbox AS earlier
                    WHERE earlier.incident_id = candidate.incident_id
                      AND earlier.sequence < candidate.sequence
                      AND earlier.status NOT IN ('delivered', 'dead_letter')
                )
                ORDER BY candidate.sequence
                LIMIT ?
                """,
                (now_iso, now_iso, max(1, min(limit, 100))),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            for row in rows:
                prior_attempt = int(row["attempt_count"])
                if row["status"] == "in_flight" and prior_attempt:
                    connection.execute(
                        """
                        UPDATE notification_attempts
                        SET outcome = 'lease_expired', completed_at = ?
                        WHERE event_id = ? AND attempt_number = ?
                          AND outcome = 'in_flight'
                        """,
                        (now_iso, row["event_id"], prior_attempt),
                    )
                attempt = prior_attempt + 1
                connection.execute(
                    """
                    UPDATE notification_outbox
                    SET status = 'in_flight', attempt_count = ?,
                        lease_owner = ?, lease_expires_at = ?
                    WHERE event_id = ?
                    """,
                    (attempt, worker_id, lease_expires_at, row["event_id"]),
                )
                connection.execute(
                    """
                    INSERT INTO notification_attempts (
                        event_id, attempt_number, worker_id, outcome, started_at
                    ) VALUES (?, ?, ?, 'in_flight', ?)
                    """,
                    (row["event_id"], attempt, worker_id, now_iso),
                )
                updated = connection.execute(
                    "SELECT * FROM notification_outbox WHERE event_id = ?",
                    (row["event_id"],),
                ).fetchone()
                claimed.append(self._notification(updated))
            connection.commit()
            return claimed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def complete_notification(
        self,
        *,
        event_id: str,
        worker_id: str,
        delivered: bool,
        error: str | None = None,
        max_attempts: int = 5,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 300.0,
        completed_at: str | datetime | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if base_backoff_seconds < 0 or max_backoff_seconds < 0:
            raise ValueError("backoff values must not be negative")
        now = parse_utc(completed_at or datetime.now(UTC))
        now_iso = now.isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM notification_outbox WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None:
                raise NotificationNotFound(event_id)
            if row["status"] == "delivered" and delivered:
                connection.rollback()
                return self._notification(row), True
            if row["status"] != "in_flight" or row["lease_owner"] != worker_id:
                raise OutboxLeaseConflict(
                    f"notification {event_id} is not leased by worker {worker_id}"
                )
            if parse_utc(row["lease_expires_at"]) <= now:
                raise OutboxLeaseConflict(f"notification {event_id} lease has expired")

            attempt = int(row["attempt_count"])
            terminal_failure = not delivered and attempt >= max_attempts
            if delivered:
                status = "delivered"
                outcome = "delivered"
                available_at = row["available_at"]
                delivered_at = now_iso
                last_error = None
            elif terminal_failure:
                status = "dead_letter"
                outcome = "dead_letter"
                available_at = row["available_at"]
                delivered_at = None
                last_error = (error or "delivery failed")[:1_000]
            else:
                status = "pending"
                outcome = "retry_scheduled"
                delay = min(
                    max_backoff_seconds,
                    base_backoff_seconds * (2 ** max(0, attempt - 1)),
                )
                available_at = (now + timedelta(seconds=delay)).isoformat()
                delivered_at = None
                last_error = (error or "delivery failed")[:1_000]
            connection.execute(
                """
                UPDATE notification_outbox
                SET status = ?, available_at = ?, lease_owner = NULL,
                    lease_expires_at = NULL, last_error = ?, delivered_at = ?
                WHERE event_id = ?
                """,
                (status, available_at, last_error, delivered_at, event_id),
            )
            updated_attempt = connection.execute(
                """
                UPDATE notification_attempts
                SET outcome = ?, error = ?, completed_at = ?
                WHERE event_id = ? AND attempt_number = ?
                  AND worker_id = ? AND outcome = 'in_flight'
                """,
                (outcome, last_error, now_iso, event_id, attempt, worker_id),
            )
            if updated_attempt.rowcount != 1:
                raise OutboxLeaseConflict(
                    f"notification {event_id} has no active attempt for worker {worker_id}"
                )
            updated = connection.execute(
                "SELECT * FROM notification_outbox WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            connection.commit()
            return self._notification(updated), False
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            evaluation_count = connection.execute(
                "SELECT COUNT(*) AS count FROM evaluations"
            ).fetchone()["count"]
            incident_count = connection.execute(
                "SELECT COUNT(*) AS count FROM incidents"
            ).fetchone()["count"]
            active_rows = connection.execute(
                """
                SELECT severity, COUNT(*) AS count
                FROM incidents
                WHERE status != 'resolved'
                GROUP BY severity
                """
            ).fetchall()
            notification_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM notification_outbox
                GROUP BY status
                """
            ).fetchall()
            notification_attempt_rows = connection.execute(
                """
                SELECT outcome, COUNT(*) AS count
                FROM notification_attempts
                GROUP BY outcome
                """
            ).fetchall()
            oldest_pending = connection.execute(
                """
                SELECT MIN(created_at) AS created_at
                FROM notification_outbox
                WHERE status IN ('pending', 'in_flight')
                """
            ).fetchone()["created_at"]
        by_severity = {severity: 0 for severity in SEVERITY_ORDER}
        for row in active_rows:
            by_severity[str(row["severity"])] = int(row["count"])
        open_count = sum(by_severity.values())
        notifications_by_status = {status: 0 for status in NOTIFICATION_STATES}
        for row in notification_rows:
            notifications_by_status[str(row["status"])] = int(row["count"])
        notification_attempts_by_outcome = {
            "in_flight": 0,
            "lease_expired": 0,
            "retry_scheduled": 0,
            "delivered": 0,
            "dead_letter": 0,
        }
        for row in notification_attempt_rows:
            notification_attempts_by_outcome[str(row["outcome"])] = int(row["count"])
        return {
            "schema_version": SCHEMA_VERSION,
            "evaluation_count": evaluation_count,
            "incident_count": incident_count,
            "open_count": open_count,
            "top_severity": highest_severity(
                [severity for severity, count in by_severity.items() if count]
            ),
            "open_by_severity": by_severity,
            "notification_count": sum(notifications_by_status.values()),
            "notifications_by_status": notifications_by_status,
            "notification_attempts_by_outcome": notification_attempts_by_outcome,
            "oldest_undelivered_at": oldest_pending,
        }

    def record_evaluation(
        self,
        *,
        request_payload: dict[str, Any],
        report: dict[str, Any],
        trace_id: str,
        created_at: str | None = None,
    ) -> tuple[dict[str, Any], bool, list[dict[str, str]]]:
        created_at = parse_utc(created_at or utc_iso()).isoformat()
        evaluation_id = str(request_payload["evaluation_id"])
        model_name = str(request_payload["model_name"])
        model_version = str(request_payload["model_version"])
        policy_version = str(request_payload["policy_version"])
        request_hash = canonical_hash(request_payload)

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT request_hash, response_json FROM evaluations WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()
        if existing is not None:
            if existing["request_hash"] != request_hash:
                raise EvaluationConflict("evaluation id was already used with a different payload")
            return self._replay(existing["response_json"], trace_id), True, []

        failed = [check for check in report["checks"] if not check["passed"]]
        root_cause = likely_root_cause(failed)
        changes: list[dict[str, str]] = []
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT request_hash, response_json FROM evaluations WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                if existing["request_hash"] != request_hash:
                    raise EvaluationConflict(
                        "evaluation id was already used with a different payload"
                    )
                return self._replay(existing["response_json"], trace_id), True, []

            for check in report["checks"]:
                check_name = str(check["name"])
                fp = incident_fingerprint(
                    model_name=model_name,
                    model_version=model_version,
                    policy_version=policy_version,
                    check_name=check_name,
                )
                row = connection.execute(
                    "SELECT * FROM incidents WHERE fingerprint = ?",
                    (fp,),
                ).fetchone()
                if not check["passed"]:
                    severity = str(check.get("severity", "medium"))
                    observed_json = json.dumps(
                        check.get("observed"),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if row is None:
                        incident_id = f"inc_{fp}"
                        connection.execute(
                            """
                            INSERT INTO incidents (
                                incident_id, fingerprint, model_name, model_version,
                                policy_version, check_name, severity, status, version,
                                occurrence_count, healthy_streak, observed_json,
                                root_cause, next_action, first_seen_at, last_seen_at,
                                updated_at, acknowledged_at, resolved_at
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, 'open', 1, 1, 0,
                                ?, ?, ?, ?, ?, ?, NULL, NULL
                            )
                            """,
                            (
                                incident_id,
                                fp,
                                model_name,
                                model_version,
                                policy_version,
                                check_name,
                                severity,
                                observed_json,
                                root_cause,
                                next_action(check_name),
                                created_at,
                                created_at,
                                created_at,
                            ),
                        )
                        event_type = "opened"
                        from_status = None
                        version = 1
                    else:
                        incident_id = row["incident_id"]
                        from_status = row["status"]
                        event_type = "reopened" if from_status == "resolved" else "evidence_updated"
                        status = "open" if from_status == "resolved" else from_status
                        version = int(row["version"]) + 1
                        severity = highest_severity([row["severity"], severity])
                        connection.execute(
                            """
                            UPDATE incidents
                            SET severity = ?, status = ?, version = ?,
                                occurrence_count = occurrence_count + 1,
                                healthy_streak = 0, observed_json = ?, root_cause = ?,
                                next_action = ?, last_seen_at = ?, updated_at = ?,
                                resolved_at = CASE WHEN ? = 'open' THEN NULL ELSE resolved_at END
                            WHERE incident_id = ?
                            """,
                            (
                                severity,
                                status,
                                version,
                                observed_json,
                                root_cause,
                                next_action(check_name),
                                created_at,
                                created_at,
                                status,
                                incident_id,
                            ),
                        )
                    self._event(
                        connection,
                        incident_id=incident_id,
                        event_type=event_type,
                        from_status=from_status,
                        to_status="open" if from_status == "resolved" else (from_status or "open"),
                        incident_version=version,
                        actor="monitoring-runtime",
                        note=f"evaluation {evaluation_id}",
                        trace_id=trace_id,
                        created_at=created_at,
                    )
                    changes.append({"incident_id": incident_id, "change": event_type})
                elif row is not None and row["status"] != "resolved":
                    incident_id = row["incident_id"]
                    from_status = row["status"]
                    streak = int(row["healthy_streak"]) + 1
                    version = int(row["version"]) + 1
                    auto_resolved = streak >= self.auto_resolve_after
                    status = "resolved" if auto_resolved else from_status
                    event_type = "auto_resolved" if auto_resolved else "recovery_observed"
                    connection.execute(
                        """
                        UPDATE incidents
                        SET status = ?, version = ?, healthy_streak = ?, updated_at = ?,
                            resolved_at = CASE WHEN ? = 'resolved' THEN ? ELSE resolved_at END
                        WHERE incident_id = ?
                        """,
                        (
                            status,
                            version,
                            streak,
                            created_at,
                            status,
                            created_at,
                            incident_id,
                        ),
                    )
                    self._event(
                        connection,
                        incident_id=incident_id,
                        event_type=event_type,
                        from_status=from_status,
                        to_status=status,
                        incident_version=version,
                        actor="monitoring-runtime",
                        note=f"healthy evaluation {evaluation_id}",
                        trace_id=trace_id,
                        created_at=created_at,
                    )
                    changes.append({"incident_id": incident_id, "change": event_type})

            active_rows = connection.execute(
                """
                SELECT * FROM incidents
                WHERE model_name = ? AND model_version = ?
                  AND policy_version = ? AND status != 'resolved'
                ORDER BY updated_at DESC
                """,
                (model_name, model_version, policy_version),
            ).fetchall()
            active = [self._incident(row) for row in active_rows]
            top_severity = highest_severity([item["severity"] for item in active])
            release_frozen = top_severity in {"high", "critical"}
            decision = {
                "release_frozen": release_frozen,
                "recommended_action": (
                    "page_and_freeze_rollouts"
                    if release_frozen
                    else ("incident_review" if active else "healthy")
                ),
                "open_incident_count": len(active),
                "top_severity": top_severity,
            }
            response = {
                "evaluation_id": evaluation_id,
                "replayed": False,
                "trace_id": trace_id,
                "model_name": model_name,
                "model_version": model_version,
                "policy_version": policy_version,
                "passed": bool(report["passed"]),
                "failed_checks": [check["name"] for check in failed],
                "report": report,
                "incident_changes": changes,
                "active_incidents": active,
                "decision": decision,
                "evaluated_at": created_at,
            }
            response_json = json.dumps(
                response,
                sort_keys=True,
                separators=(",", ":"),
            )
            connection.execute(
                """
                INSERT INTO evaluations (
                    evaluation_id, request_hash, model_name, model_version,
                    policy_version, outcome, response_json, trace_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation_id,
                    request_hash,
                    model_name,
                    model_version,
                    policy_version,
                    "passed" if report["passed"] else "failed_checks",
                    response_json,
                    trace_id,
                    created_at,
                ),
            )
            connection.commit()
            return response, False, changes
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def transition(
        self,
        *,
        incident_id: str,
        target_status: str,
        transition_id: str,
        expected_version: int,
        actor: str,
        note: str | None,
        trace_id: str,
        created_at: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if target_status not in {"acknowledged", "resolved"}:
            raise InvalidTransition(f"unsupported target state: {target_status}")
        created_at = parse_utc(created_at or utc_iso()).isoformat()
        request = {
            "incident_id": incident_id,
            "target_status": target_status,
            "transition_id": transition_id,
            "expected_version": expected_version,
            "actor": actor,
            "note": note,
        }
        request_hash = canonical_hash(request)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                """
                SELECT request_hash, response_json
                FROM transition_requests
                WHERE transition_id = ?
                """,
                (transition_id,),
            ).fetchone()
            if replay is not None:
                connection.rollback()
                if replay["request_hash"] != request_hash:
                    raise TransitionConflict(
                        "transition id was already used with a different payload"
                    )
                return self._replay(replay["response_json"], trace_id), True

            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
            if row is None:
                raise IncidentNotFound(incident_id)
            if int(row["version"]) != expected_version:
                raise TransitionConflict(
                    f"incident version is {row['version']}, expected {expected_version}"
                )
            from_status = str(row["status"])
            allowed = {
                "open": {"acknowledged", "resolved"},
                "acknowledged": {"resolved"},
                "resolved": set(),
            }
            if target_status not in allowed[from_status]:
                raise InvalidTransition(
                    f"cannot transition incident from {from_status} to {target_status}"
                )

            version = expected_version + 1
            acknowledged_at = (
                created_at if target_status == "acknowledged" else row["acknowledged_at"]
            )
            resolved_at = created_at if target_status == "resolved" else row["resolved_at"]
            connection.execute(
                """
                UPDATE incidents
                SET status = ?, version = ?, updated_at = ?,
                    acknowledged_at = ?, resolved_at = ?
                WHERE incident_id = ?
                """,
                (
                    target_status,
                    version,
                    created_at,
                    acknowledged_at,
                    resolved_at,
                    incident_id,
                ),
            )
            self._event(
                connection,
                incident_id=incident_id,
                event_type=target_status,
                from_status=from_status,
                to_status=target_status,
                incident_version=version,
                actor=actor,
                note=note,
                trace_id=trace_id,
                created_at=created_at,
            )
            updated = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
            response = {
                "replayed": False,
                "trace_id": trace_id,
                "transition_id": transition_id,
                "incident": self._incident(updated),
            }
            response_json = json.dumps(response, sort_keys=True, separators=(",", ":"))
            connection.execute(
                """
                INSERT INTO transition_requests (
                    transition_id, request_hash, response_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (transition_id, request_hash, response_json, created_at),
            )
            connection.commit()
            return response, False
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
