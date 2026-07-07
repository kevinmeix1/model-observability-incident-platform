# Cloud Migration Plan

Generate the machine-readable plan with:

```bash
make cloud-plan
```

## AWS Target

- Run observability checks on EKS Auto Mode or Karpenter-style NodePools.
- Store telemetry windows and baselines in versioned S3.
- Store incidents in DynamoDB or PostgreSQL keyed by dedupe fingerprint.
- Send metrics to Amazon Managed Service for Prometheus and Grafana.
- Route Alertmanager webhooks to PagerDuty, Slack, or email.
- Expose rollout-freeze decisions to Airflow, GitOps, or model release automation.

## Portability Notes

- Keep incident fingerprints stable across backends.
- Keep thresholds in `contracts/observability_policy.yml`.
- Keep cloud-specific IAM, buckets, and cluster configuration in `infra/terraform/aws`.
