# Kueue Cohort Fair Sharing

`make cohort-fair-sharing` writes `.local/reports/cohort_fair_sharing_plan.json` and pairs it with `kubernetes/kueue-cohort-fair-sharing.yaml`.

## What It Shows

- Kueue Fair Sharing with `preemptionStrategies` for borrowed observability resources.
- Admission Fair Sharing so `LocalQueue` admission accounts for decayed historical usage and entry penalties.
- `borrowingLimit` and `lendingLimit` for incident-response, drift-monitoring, and retention-maintenance tenants.
- `fairSharing.weight` that protects incident root-cause and rollout-freeze work from noisy retention jobs.
- Preemption policy separation between `withinClusterQueue` and `reclaimWithinCohort`.

## Production Notes

Model observability platforms need elastic capacity for drift backlogs, dashboard backfills, and retention compaction, but incident response has to stay fast when a rollout is already frozen. Cohort borrowing keeps spare capacity useful, while Fair Sharing, lending limits, and weighted queues prevent background maintenance from starving on-call diagnostics.

Admission Fair Sharing adds a second layer inside each `ClusterQueue`: noisy `LocalQueue` submitters build up historical usage and lose admission priority until their share decays. That is useful when retention jobs are healthy in aggregate but one dashboard backfill or compaction stream submits too aggressively.

## References

- Kueue ClusterQueue: <https://kueue.sigs.k8s.io/docs/concepts/cluster_queue/>
- Kueue Cohort: <https://kueue.sigs.k8s.io/docs/concepts/cohort/>
- Kueue Preemption and Fair Sharing: <https://kueue.sigs.k8s.io/docs/concepts/preemption/>
- Kueue Admission Fair Sharing: <https://kueue.sigs.k8s.io/docs/concepts/admission_fair_sharing/>
