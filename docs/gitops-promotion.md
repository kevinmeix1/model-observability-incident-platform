# GitOps Promotion

This project models GitOps promotion for the observability and incident-response plane. Promotion should prove that telemetry remains fresh, incidents are still idempotent, and burn-rate checks stay healthy before full rollout.

Run:

```bash
make gitops-plan
```

The report is written to `.local/reports/gitops_plan.json`.

## Design

- Apply network, security, capacity, and alerting resources before runtime changes.
- Use pre-sync hooks for telemetry schema and incident dedupe dry-runs.
- Use post-sync analysis for freshness and burn-rate health.
- Keep production sync manual when high-severity incidents are active.
- Use Argo Rollouts for control-plane changes and preserve incident routing capacity.

## References

Argo CD sync waves and hooks make promotion order explicit. Automated sync/self-heal can be enabled in lower environments. Argo Rollouts AnalysisTemplates provide metric-based promotion or abort decisions.
