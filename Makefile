.PHONY: demo test clean

demo:
	PYTHONPATH=src python3 -m model_observability_platform demo --output .local

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	rm -rf .local
