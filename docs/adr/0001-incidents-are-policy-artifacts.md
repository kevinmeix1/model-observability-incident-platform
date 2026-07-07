# ADR 0001: Incidents Are Policy Artifacts

## Status

Accepted

## Context

Model monitoring often produces noisy dashboards but weak operational follow-through. A production platform needs to turn checks into actionable incidents with ownership, dedupe, severity, and runbook guidance.

## Decision

Represent observability failures as incident records generated from policy-defined checks. Keep a stable fingerprint so repeated monitor runs do not spam responders.

## Consequences

Benefits:

- Checks become actionable.
- Deduplication is testable.
- Root-cause hints can be improved over time.
- The incident store can plug into PagerDuty, Slack, or Jira.

Trade-offs:

- Root-cause classification starts heuristic.
- Production needs status transitions, ownership, comments, and audit history.

