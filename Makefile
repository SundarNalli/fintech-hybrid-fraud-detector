.PHONY: help demo serve latency test eval

help:
	@echo "make serve    - run the service; ops screen at http://127.0.0.1:8000/, API docs at /docs"
	@echo "make latency  - 50,000-event latency run (in-process)"
	@echo "make eval     - evaluation with the scripted stand-in (not a model)"
	@echo "make test     - run the tests"
	@echo "make demo     - start the service in replay mode and print the demo script path"

serve:
	python -m hybrid_fraud.service.main

latency:
	python -m hybrid_fraud.eval.latency

eval:
	python -m hybrid_fraud.eval.run --provider scripted --repeats 3

test:
	python -m pytest -q

demo:
	@echo "Demo script: docs/client/demo-script.md  (no API key needed: replay mode)"
	python -m hybrid_fraud.service.main
