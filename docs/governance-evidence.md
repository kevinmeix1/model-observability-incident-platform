# Governance Evidence

The observability platform generates a reliability evidence bundle:

- `governance/model_card.json`
- `governance/data_card.json`
- `governance/risk_register.json`
- `governance/approval_record.json`
- `governance/reproducibility_manifest.json`
- `reports/governance_evidence_bundle.json`

The bundle is intentionally incident-aware. A failing telemetry window produces `incident_review_required`, which is the correct release decision when drift, SLO, and error-rate checks fail.

Run it locally:

```bash
make demo
make governance-bundle
```

`kubernetes/governance-evidence.yaml` models a release evidence job plus a scheduled reliability review.
