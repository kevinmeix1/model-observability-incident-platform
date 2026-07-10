# Root Cause Evidence Bundle

The demo writes `reports/root_cause_evidence_bundle.json` to explain why the platform selected a likely root cause. It keeps incident fingerprints stable and stores the explanation beside the incident, so retries and duplicate prevention are not affected by changing review language.

The bundle combines three evidence classes:

- Symptom-first SLO evidence: user-impacting error and latency checks drive paging and release freeze decisions before causal labels are complete.
- Lineage facets: OpenLineage-style run and dataset facets attach RCA, feature-window, and serving-telemetry metadata to the incident review.
- Rollout context: feature flag evaluation context records shadow reads, canary weight, and fail-closed incident freeze state.

This is intentionally probabilistic. The demo records missing evidence such as delayed outcome labels, assigns a confidence score, and keeps the next action tied to the reliability control plan.

Run:

```bash
make demo
make root-cause-evidence
make dashboard
```
