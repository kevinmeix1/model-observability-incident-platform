.PHONY: demo reliability-plan policy-audit trace-report chaos-drill optimize-resources network-security gitops-plan dr-plan governance-bundle slo-report cloud-plan supply-chain orchestration-scorecard accelerator-plan device-plan topology-plan kuberay-plan inference-gateway-plan semantic-telemetry-plan deadline-alerts-plan cost-observability elastic-workload-plan indexed-job-resilience provisioning-admission multikueue-dispatch dag-bundle-plan event-driven-assets pod-resource-envelopes cohort-fair-sharing flavor-fungibility tenancy-report identity-report performance-budget queue-simulation incident-evidence-volumes release-admission ci-verify kubernetes-plan minikube-up test clean

demo:
	PYTHONPATH=src python3 -m model_observability_platform demo --output .local

reliability-plan:
	PYTHONPATH=src python3 -m model_observability_platform reliability-plan --output .local

policy-audit:
	PYTHONPATH=src python3 -m model_observability_platform policy-audit --output .local

trace-report:
	PYTHONPATH=src python3 -m model_observability_platform trace-report --output .local

chaos-drill:
	PYTHONPATH=src python3 -m model_observability_platform chaos-drill --output .local

optimize-resources:
	PYTHONPATH=src python3 -m model_observability_platform optimize-resources --output .local

network-security:
	PYTHONPATH=src python3 -m model_observability_platform network-security --output .local

gitops-plan:
	PYTHONPATH=src python3 -m model_observability_platform gitops-plan --output .local

dr-plan:
	PYTHONPATH=src python3 -m model_observability_platform dr-plan --output .local

governance-bundle:
	PYTHONPATH=src python3 -m model_observability_platform governance-bundle --output .local

slo-report:
	PYTHONPATH=src python3 -m model_observability_platform slo-report --output .local

cloud-plan:
	PYTHONPATH=src python3 -m model_observability_platform cloud-plan --output .local

supply-chain:
	PYTHONPATH=src python3 -m model_observability_platform supply-chain --output .local

orchestration-scorecard:
	PYTHONPATH=src python3 -m model_observability_platform orchestration-scorecard --output .local

accelerator-plan:
	PYTHONPATH=src python3 -m model_observability_platform accelerator-plan --output .local

device-plan:
	PYTHONPATH=src python3 -m model_observability_platform device-plan --output .local

topology-plan:
	PYTHONPATH=src python3 -m model_observability_platform topology-plan --output .local

kuberay-plan:
	PYTHONPATH=src python3 -m model_observability_platform kuberay-plan --output .local

inference-gateway-plan:
	PYTHONPATH=src python3 -m model_observability_platform inference-gateway-plan --output .local

semantic-telemetry-plan:
	PYTHONPATH=src python3 -m model_observability_platform semantic-telemetry-plan --output .local

deadline-alerts-plan:
	PYTHONPATH=src python3 -m model_observability_platform deadline-alerts-plan --output .local

cost-observability:
	PYTHONPATH=src python3 -m model_observability_platform cost-observability --output .local

elastic-workload-plan:
	PYTHONPATH=src python3 -m model_observability_platform elastic-workload-plan --output .local

indexed-job-resilience:
	PYTHONPATH=src python3 -m model_observability_platform indexed-job-resilience --output .local

provisioning-admission:
	PYTHONPATH=src python3 -m model_observability_platform provisioning-admission --output .local

multikueue-dispatch:
	PYTHONPATH=src python3 -m model_observability_platform multikueue-dispatch --output .local

dag-bundle-plan:
	PYTHONPATH=src python3 -m model_observability_platform dag-bundle-plan --output .local

event-driven-assets:
	PYTHONPATH=src python3 -m model_observability_platform event-driven-assets --output .local

pod-resource-envelopes:
	PYTHONPATH=src python3 -m model_observability_platform pod-resource-envelopes --output .local

cohort-fair-sharing:
	PYTHONPATH=src python3 -m model_observability_platform cohort-fair-sharing --output .local

flavor-fungibility:
	PYTHONPATH=src python3 -m model_observability_platform flavor-fungibility --output .local

tenancy-report:
	PYTHONPATH=src python3 -m model_observability_platform tenancy-report --output .local

identity-report:
	PYTHONPATH=src python3 -m model_observability_platform identity-report --output .local

performance-budget:
	PYTHONPATH=src python3 -m model_observability_platform performance-budget --output .local

queue-simulation:
	PYTHONPATH=src python3 -m model_observability_platform queue-simulation --output .local

incident-evidence-volumes:
	PYTHONPATH=src python3 -m model_observability_platform incident-evidence-volumes --output .local

release-admission:
	PYTHONPATH=src python3 -m model_observability_platform release-admission --output .local

ci-verify:
	PYTHONPATH=src python3 -m compileall -q src tests
	test -f .local/reports/model_observability_dashboard.html
	test -f .local/reports/index.html
	test -f .local/reports/governance_evidence_bundle.json
	test -f .local/reports/slo_error_budget.json
	test -f .local/reports/cloud_migration_plan.json
	test -f .local/reports/supply_chain_evidence.json
	test -f .local/reports/orchestration_scorecard.json
	test -f .local/reports/accelerator_capacity_plan.json
	test -f .local/reports/device_allocation_plan.json
	test -f .local/reports/topology_placement_plan.json
	test -f .local/reports/kuberay_capacity_plan.json
	test -f .local/reports/inference_gateway_plan.json
	test -f .local/reports/semantic_telemetry_plan.json
	test -f .local/reports/deadline_alert_plan.json
	test -f .local/reports/cost_observability_report.json
	test -f .local/reports/elastic_workload_plan.json
	test -f .local/reports/indexed_job_resilience_plan.json
	test -f .local/reports/provisioning_admission_plan.json
	test -f .local/reports/multikueue_dispatch_plan.json
	test -f .local/reports/dag_bundle_versioning_plan.json
	test -f .local/reports/event_driven_assets_plan.json
	test -f .local/reports/pod_resource_envelope_plan.json
	test -f .local/reports/cohort_fair_sharing_plan.json
	test -f .local/reports/flavor_fungibility_plan.json
	test -f .local/reports/tenancy_fairness_report.json
	test -f .local/reports/identity_access_report.json
	test -f .local/reports/performance_budget.json
	test -f .local/reports/queue_simulation.json
	test -f .local/reports/incident_evidence_volume_plan.json
	test -f .local/reports/release_admission_decision.json
	test -f .local/supply-chain/subject.checksums.txt
	python3 -m json.tool .local/reports/governance_evidence_bundle.json >/dev/null
	python3 -m json.tool .local/reports/slo_error_budget.json >/dev/null
	python3 -m json.tool .local/reports/cloud_migration_plan.json >/dev/null
	python3 -m json.tool .local/reports/supply_chain_evidence.json >/dev/null
	python3 -m json.tool .local/reports/orchestration_scorecard.json >/dev/null
	python3 -m json.tool .local/reports/accelerator_capacity_plan.json >/dev/null
	python3 -m json.tool .local/reports/device_allocation_plan.json >/dev/null
	python3 -m json.tool .local/reports/topology_placement_plan.json >/dev/null
	python3 -m json.tool .local/reports/kuberay_capacity_plan.json >/dev/null
	python3 -m json.tool .local/reports/inference_gateway_plan.json >/dev/null
	python3 -m json.tool .local/reports/semantic_telemetry_plan.json >/dev/null
	python3 -m json.tool .local/reports/deadline_alert_plan.json >/dev/null
	python3 -m json.tool .local/reports/cost_observability_report.json >/dev/null
	python3 -m json.tool .local/reports/elastic_workload_plan.json >/dev/null
	python3 -m json.tool .local/reports/indexed_job_resilience_plan.json >/dev/null
	python3 -m json.tool .local/reports/provisioning_admission_plan.json >/dev/null
	python3 -m json.tool .local/reports/multikueue_dispatch_plan.json >/dev/null
	python3 -m json.tool .local/reports/dag_bundle_versioning_plan.json >/dev/null
	python3 -m json.tool .local/reports/event_driven_assets_plan.json >/dev/null
	python3 -m json.tool .local/reports/pod_resource_envelope_plan.json >/dev/null
	python3 -m json.tool .local/reports/cohort_fair_sharing_plan.json >/dev/null
	python3 -m json.tool .local/reports/flavor_fungibility_plan.json >/dev/null
	python3 -m json.tool .local/reports/tenancy_fairness_report.json >/dev/null
	python3 -m json.tool .local/reports/identity_access_report.json >/dev/null
	python3 -m json.tool .local/reports/performance_budget.json >/dev/null
	python3 -m json.tool .local/reports/queue_simulation.json >/dev/null
	python3 -m json.tool .local/reports/incident_evidence_volume_plan.json >/dev/null
	python3 -m json.tool .local/reports/release_admission_decision.json >/dev/null

kubernetes-plan:
	@find kubernetes gitops -name '*.yaml' -maxdepth 3 -print

minikube-up:
	@echo "Start Minikube and apply the observability control plane:"
	@echo "  minikube start --cpus=4 --memory=8192"
	@echo "  kubectl apply -f kubernetes/observability-control-plane.yaml"
	@echo "  kubectl apply -f kubernetes/resource-optimization.yaml"
	@echo "  kubectl apply -f kubernetes/network-security.yaml"
	@echo "  kubectl apply -f kubernetes/chaos-experiments.yaml"
	@echo "  kubectl apply -f kubernetes/disaster-recovery.yaml"
	@echo "  kubectl apply -f kubernetes/governance-evidence.yaml"
	@echo "  kubectl apply -f kubernetes/slo-alerts.yaml"
	@echo "  kubectl apply -f kubernetes/cloud-nodepools.yaml"
	@echo "  kubectl apply -f kubernetes/supply-chain-policy.yaml"
	@echo "  kubectl apply -f kubernetes/accelerator-scheduling.yaml"
	@echo "  kubectl apply -f kubernetes/dynamic-resource-allocation.yaml"
	@echo "  kubectl apply -f kubernetes/topology-aware-scheduling.yaml"
	@echo "  kubectl apply -f kubernetes/kuberay-kueue-workloads.yaml"
	@echo "  kubectl apply -f kubernetes/kueue-elastic-workloads.yaml"
	@echo "  kubectl apply -f kubernetes/indexed-job-resilience.yaml"
	@echo "  kubectl apply -f kubernetes/provisioning-admission-checks.yaml"
	@echo "  kubectl apply -f kubernetes/multikueue-dispatch.yaml"
	@echo "  kubectl apply -f kubernetes/incident-evidence-volumes.yaml"
	@echo "  kubectl apply -f kubernetes/pod-resource-envelopes.yaml"
	@echo "  kubectl apply -f kubernetes/kueue-cohort-fair-sharing.yaml"
	@echo "  kubectl apply -f kubernetes/kueue-flavor-fungibility.yaml"
	@echo "  kubectl apply -f kubernetes/inference-gateway-routing.yaml"
	@echo "  kubectl apply -f kubernetes/multitenancy-fairness.yaml"
	@echo "  kubectl apply -f kubernetes/workload-identity.yaml"
	@echo "  kubectl apply -f kubernetes/performance-budget-policy.yaml"
	@echo "  kubectl apply -f kubernetes/queue-simulation-policy.yaml"
	@echo "  kubectl apply -f kubernetes/release-admission-policy.yaml"
	@echo "  kubectl apply -f kubernetes/opencost-finops.yaml"
	@echo "  kubectl apply -f gitops/gitops-promotion.yaml"

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	rm -rf .local
