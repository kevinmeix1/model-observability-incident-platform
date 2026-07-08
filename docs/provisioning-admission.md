# Kueue Provisioning Admission

Incident platforms fail badly when diagnostics are admitted on paper but cannot actually run. This project uses Kueue `AdmissionCheck` plus `ProvisioningRequest` to model the missing production guardrail: root-cause probes, impact analysis, rollout-freeze checks, and GPU drift diagnostics should wait for a real capacity signal.

## Incident Admission Flow

1. Airflow starts an incident diagnostic wave or failed-only recovery backfill.
2. Kueue reserves quota in the incident or GPU diagnostic ClusterQueue.
3. The provisioning admission controller creates a `ProvisioningRequest`.
4. Cluster Autoscaler confirms whether the required CPU or GPU capacity can be provisioned.
5. Incident diagnostics run only after the AdmissionCheck becomes `Ready`.

Fresh incident creation and alert routing remain the highest-priority path. Historical diagnostic backfills are requeued if provisioning fails.

## Controls

- `AdmissionCheck` uses `kueue.x-k8s.io/provisioning-request`.
- `ProvisioningRequestConfig` declares `provisioningClassName`, `managedResources`, retry backoff, `podSetMergePolicy`, and `podSetUpdates`.
- `admissionChecksStrategy` scopes the check to incident and GPU diagnostic flavors.
- Job annotations bound diagnostic run duration and booking lifetime.
- Alerts cover pending admission, retry exhaustion, and booking expiry.

## Operating Semantics

| Signal | Incident action |
| --- | --- |
| `Provisioned=true` | Run root-cause, impact, freeze, and diagnostic probes. |
| `Provisioned=false` | Keep diagnostics suspended and page capacity owner if triage SLO is at risk. |
| `Failed=true` | Requeue lower-priority diagnostics, preserve rollout freeze, and keep incidents open. |
| `BookingExpired=true` | Re-run incident smoke checks before publishing dashboard updates. |
| `CapacityRevoked=true` | Keep rollout freeze active and treat diagnostics as incomplete. |

## Interview Talking Point

Observability is part of the release control plane. If incident diagnostics cannot get capacity, the safe response is to freeze rollouts and preserve fresh incident routing, not to silently mark the platform healthy.
