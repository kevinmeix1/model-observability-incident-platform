# Network Security

The observability platform uses a default-deny namespace boundary with narrow telemetry and incident paths. The aim is to keep monitoring useful during incidents without giving every observability job broad network reach.

Run:

```bash
make network-security
```

The report is written to `.local/reports/network_security.json`.

## Controls

- Default deny for ingress and egress.
- Explicit DNS egress allow.
- Collector ingress only from model-serving runtimes on the OTLP port.
- Incident router egress only to alert webhook ranges.
- Strict mTLS and AuthorizationPolicy for incident notifications.
- Collector-to-registry and drift-evaluator-to-admin paths denied by default.

## References

Kubernetes NetworkPolicy isolates selected pods and requires explicit allow rules under default deny. Istio `PeerAuthentication` strict mode requires mTLS, while AuthorizationPolicy narrows calls to specific workload identities.
