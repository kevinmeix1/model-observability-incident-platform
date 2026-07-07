.PHONY: demo kubernetes-plan minikube-up test clean

demo:
	PYTHONPATH=src python3 -m model_observability_platform demo --output .local

kubernetes-plan:
	@find kubernetes -name '*.yaml' -maxdepth 3 -print

minikube-up:
	@echo "Start Minikube and apply the observability control plane:"
	@echo "  minikube start --cpus=4 --memory=8192"
	@echo "  kubectl apply -f kubernetes/observability-control-plane.yaml"

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	rm -rf .local
