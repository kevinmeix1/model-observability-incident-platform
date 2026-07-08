# Gateway API Inference Extension

`make inference-gateway-plan` writes `.local/reports/inference_gateway_plan.json` and pairs it with `kubernetes/inference-gateway-routing.yaml`.

## What It Shows

- Stable v1 `InferencePool` metadata as an observability target.
- Endpoint Picker health as an incident signal.
- Alpha `InferenceObjective` priority examples captured in incident context.
- Gateway API `HTTPRoute` references that route diagnostic replay through an `InferencePool`.
- Alerts that freeze canaries when objective-level routing signals disappear.

## Production Notes

The observability platform should watch inference-gateway health without owning production request routing. This project treats endpoint-picker readiness, pool backend health, objective priority, and route skew as first-class incident signals that can explain serving regressions and trigger rollback recommendations.

References: Kubernetes Gateway API Inference Extension, InferencePool v1 docs, and Istio integration guide.
