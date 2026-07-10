# Constrained Impersonation

`make constrained-impersonation` writes `.local/reports/constrained_impersonation_plan.json`.

## What It Shows

- Kubernetes v1.36 `ConstrainedImpersonation` beta behavior.
- Separate authorization for the impersonated service account identity and the actions performed while impersonating.
- Incident support and rollout-freeze workflows that can inspect evidence or patch status without broad incident-router authority.
- Audit expectations for `authenticationMetadata.impersonationConstraint`.
- Alerts for legacy broad `impersonate` grants that bypass least-privilege intent.

## Production Notes

Incident tooling frequently needs to act on behalf of a platform identity, but a
single broad impersonation grant can become an escalation path. Constrained
impersonation keeps support access narrow by requiring both
`impersonate:serviceaccount` for the exact target and scoped
`impersonate-on:serviceaccount:<verb>` permissions for evidence inspection or
incident-status patching.

This is especially useful during rollout freezes, when debugging speed matters
but support tooling still should not inherit create/delete permissions.

References:

- https://kubernetes.io/blog/2026/04/22/kubernetes-v1-36-release/
- https://kubernetes.io/docs/reference/access-authn-authz/user-impersonation/
