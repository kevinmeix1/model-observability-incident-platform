# Airflow DAG Bundles

`make dag-bundle-plan` writes `.local/reports/dag_bundle_versioning_plan.json` and pairs it with `airflow/dag-bundle-config.ini`.

## What It Shows

- Airflow 3 `GitDagBundle` configuration for the reliability control-plane DAG.
- Bundle versioning kept on with `disable_bundle_versioning = False`.
- Reruns set to `rerun_with_latest_version = False` so incident replay preserves the original root-cause and rollout-freeze code.
- `sparse_dirs` includes Airflow DAGs, incident evidence Kubernetes manifests, policy contracts, and platform source code.
- Git credentials referenced through `git_conn_id`, so tokens live in Airflow Connections or a secrets backend.
- Scheduler-managed backfills separated from forensic incident replay.

## Production Notes

Incident response is a chain of evidence. A credible model incident record should tie together the incident fingerprint, DAG Bundle version, root-cause fanout job, evidence bundle digest, rollout-freeze decision, and dashboard snapshot.

This project keeps incident replay pinned to the original bundle version. Latest-code remediation runs are still useful, but they should be separate from forensic replay so an interviewer can see exactly what code made the original decision.

## Failure Recovery

- If Git bundle refresh fails, restore the `github_dag_bundle` connection and refresh DAG processors before launching new diagnostic runs.
- If a bad incident workflow commit is deployed, revert it and start a fresh diagnostic run rather than mutating the failed incident evidence.
- If rollout-freeze replay must be tested after a hotfix, keep original-bundle replay as forensic evidence and run latest-code remediation separately.

## References

- Airflow DAG Bundles: <https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html>
- Airflow `GitDagBundle`: <https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html#gitdagbundle>
- Airflow rerun behavior: <https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html#rerun-behavior>
