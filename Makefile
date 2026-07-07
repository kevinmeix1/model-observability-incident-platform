.PHONY: demo reliability-plan policy-audit trace-report chaos-drill optimize-resources network-security kubernetes-plan minikube-up test clean

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

kubernetes-plan:
	@find kubernetes -name '*.yaml' -maxdepth 3 -print

minikube-up:
	@echo "Start Minikube and apply the observability control plane:"
	@echo "  minikube start --cpus=4 --memory=8192"
	@echo "  kubectl apply -f kubernetes/observability-control-plane.yaml"
	@echo "  kubectl apply -f kubernetes/resource-optimization.yaml"
	@echo "  kubectl apply -f kubernetes/network-security.yaml"
	@echo "  kubectl apply -f kubernetes/chaos-experiments.yaml"

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	rm -rf .local
