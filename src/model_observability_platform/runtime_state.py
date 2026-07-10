from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .checks import likely_root_cause
from .incidents import next_action

SCHEMA_VERSION = "1"
INCIDENT_STATES = {"open", "acknowledged", "resolved"}
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class EvaluationConflict(RuntimeError):
    pass


class TransitionConflict(RuntimeError):
    pass


class IncidentNotFound(RuntimeError):
    pass


class InvalidTransition(RuntimeError):
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
                    incident_version INTEGER NOT NULL,
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

                CREATE INDEX IF NOT EXISTS incidents_status_idx
                    ON incidents(status, severity, updated_at);
                CREATE INDEX IF NOT EXISTS incident_events_incident_idx
                    ON incident_events(incident_id, event_id);
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

    @staticmethod
    def _replay(response_json: str, trace_id: str) -> dict[str, Any]:
        response = json.loads(response_json)
        response["replayed"] = True
        response["original_trace_id"] = response.get("trace_id")
        response["trace_id"] = trace_id
        return response

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
        by_severity = {severity: 0 for severity in SEVERITY_ORDER}
        for row in active_rows:
            by_severity[str(row["severity"])] = int(row["count"])
        open_count = sum(by_severity.values())
        return {
            "schema_version": SCHEMA_VERSION,
            "evaluation_count": evaluation_count,
            "incident_count": incident_count,
            "open_count": open_count,
            "top_severity": highest_severity(
                [severity for severity, count in by_severity.items() if count]
            ),
            "open_by_severity": by_severity,
        }

    def record_evaluation(
        self,
        *,
        request_payload: dict[str, Any],
        report: dict[str, Any],
        trace_id: str,
        created_at: str | None = None,
    ) -> tuple[dict[str, Any], bool, list[dict[str, str]]]:
        created_at = created_at or utc_iso()
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
        created_at = created_at or utc_iso()
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
