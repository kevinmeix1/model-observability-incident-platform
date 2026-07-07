.PHONY: demo reliability-plan policy-audit trace-report chaos-drill optimize-resources network-security gitops-plan dr-plan governance-bundle kubernetes-plan minikube-up test clean

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
	@echo "  kubectl apply -f gitops/gitops-promotion.yaml"

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	rm -rf .local
