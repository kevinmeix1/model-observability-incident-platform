# ADR 004: Single-Process Transactional Incident Control Plane

- **Status:** Accepted for the local portfolio runtime
- **Date:** 2026-07-10

## Context

The original demonstration wrote incidents to JSON Lines and regenerated
reports in one process. That path was deterministic but did not provide a safe
concurrent lifecycle, restart-safe request replay, or an executable HTTP
boundary. Listing Postgres, Prometheus, OpenTelemetry, and FastAPI as future
integrations did not prove those behaviors.

## Decision

Add a bounded FastAPI control plane backed by SQLite WAL with one Uvicorn
worker. Persist evaluations, incidents, lifecycle events, and transition
idempotency records in one database.

Use:

- canonical payload hashes for evaluation and transition replay
- a stable model/policy/check incident fingerprint
- optimistic incident versions for operator transitions
- two healthy evaluations for automatic recovery
- a dedicated Prometheus registry with bounded labels
- manual OpenTelemetry spans using stable HTTP route templates
- a non-root, read-only container with a named state volume

Keep the dependency-free JSONL demonstration as a separate teaching path. Do
not claim that it and the API are one distributed production deployment.

## Consequences

Positive:

- transaction boundaries and replay behavior are inspectable
- the API can be tested in-process, over a real socket, and in Compose
- incident identity remains stable as observed values change
- reviewers can distinguish implemented telemetry from design documents

Negative:

- SQLite serializes writers and prevents honest horizontal API scaling
- one process owns in-memory metric state
- state migration and retention are intentionally basic
- authentication and tenant isolation remain outside the local scope

## Alternatives

**Keep JSON Lines only:** rejected for the runtime because lifecycle updates and
idempotency cannot be made safely transactional under concurrent requests.

**Start with Postgres:** deferred because it would add operational machinery
without changing the domain contracts being demonstrated. Postgres becomes the
right choice when multiple replicas, online migrations, stronger access
control, or sustained concurrent writes are required.

**Use an external incident platform as the source of truth:** deferred because
the project needs to expose and test its own deduplication and recovery
semantics first. A ticket integration should consume committed events rather
than define core transaction correctness.

## Revisit Trigger

Replace SQLite before claiming high availability, multiple API replicas,
multi-tenant access control, or production retention guarantees.
