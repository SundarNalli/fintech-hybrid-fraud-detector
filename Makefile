.PHONY: help demo serve latency test

help:
	@echo "make serve    - run the payout service at http://127.0.0.1:8000/docs"
	@echo "make latency  - 50,000-event latency run (in-process)"
	@echo "make test     - run the tests"
	@echo "make demo     - run the whole flow in replay mode (not built yet)"

serve:
	python -m hybrid_fraud.service.main

latency:
	python -m hybrid_fraud.eval.latency

test:
	python -m pytest -q

demo:
	@echo "The demo does not exist yet. See README.md for the current phase."
