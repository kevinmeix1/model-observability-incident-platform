# ADR 005: Persist Incident Notifications In A Transactional Outbox

- Status: accepted
- Date: 2026-07-10

## Context

Incident state is durable, but calling a webhook after committing state creates
a dual-write gap. A process can exit after the incident commit but before the
notification, or notify a receiver before the incident transaction rolls back.
Inline retries also hold API capacity and couple incident correctness to an
external receiver's latency.

## Decision

Append one CloudEvents-compatible outbox row in the same transaction as every
incident event. Deliver outside the request path with:

- deterministic event identity;
- at-least-once semantics and receiver idempotency;
- ordering within an incident, concurrency across incidents;
- bounded leases and stale-owner fencing;
- persisted exponential retry and a terminal dead-letter state;
- immutable attempt evidence.

SQLite WAL is retained for the executable local contract and one writer. A
production implementation moves the same domain fields to Postgres and claims
rows with row locks or relays them to a durable broker.

## Consequences

Incident commits no longer depend on receiver availability, and notification
loss after a successful incident transaction is recoverable. Operators can
distinguish pending, active, delivered, and dead-letter work.

The design does not provide exactly-once side effects. Receivers must persist
event IDs. Per-incident ordering can delay a later lifecycle event behind a
retrying predecessor. Dead-lettering unblocks the sequence but requires the
receiver to detect an incident-version gap.

## Rejected Alternatives

- **Inline webhook:** leaves a dual-write gap and couples API latency to the
  receiver.
- **Delete after send:** loses audit and makes crash ambiguity harder to
  diagnose.
- **Global ordering:** serializes independent incidents without a business
  requirement.
- **Exactly-once claim:** cannot be honestly guaranteed across an arbitrary
  external receiver without shared transaction support.
