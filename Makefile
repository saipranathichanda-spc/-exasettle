.PHONY: help demo test verify-audit run preflight server generate-data scale-test load-test feedback-loop idempotency-test build-frontend

help:
	@echo "ExaSettle - Evaluator Commands"
	@echo "  make demo              Execute complete end-to-end evaluator demo"
	@echo "  make test              Run full automated test suite (pytest)"
	@echo "  make verify-audit      Verify cryptographic SHA-256 tamper-evident hash chain"
	@echo "  make run               Execute deterministic reconciliation run (SCN_CORE_8PACK)"
	@echo "  make preflight         Run environment & dependency health preflight"
	@echo "  make server            Launch FastAPI web server on 127.0.0.1:8000"
	@echo "  make generate-data     Generate 30-day 300k transaction dataset & charts"
	@echo "  make scale-test        Run 100k/1M scale benchmarks & EXPLAIN query plan"
	@echo "  make load-test         Run Locust concurrency load tests (10, 50, 100 users)"
	@echo "  make feedback-loop     Run 6-persona simulated feedback loop (Round 1 & 2)"
	@echo "  make idempotency-test  Run idempotency & deduplication invariant tests"
	@echo "  make build-frontend    Build React/Tailwind frontend bundle"

demo:
	python -m exasettle.cli demo

test:
	pytest -v -rs

verify-audit:
	python -m exasettle.cli verify-audit

run:
	python -m exasettle.cli run --scenario SCN_CORE_8PACK --seed 42 --threshold 24.0

preflight:
	python -m exasettle.cli preflight

server:
	python -m exasettle.cli server --host 127.0.0.1 --port 8000

generate-data:
	python scripts/generate_reports_and_charts.py

scale-test:
	python scripts/run_scale_and_load.py

load-test:
	python -m locust -f tests/locustfile.py --headless -u 50 -r 10 --run-time 10s --host http://127.0.0.1:8000 --only-summary

feedback-loop:
	python scripts/run_simulated_feedback_loop.py

idempotency-test:
	pytest tests/test_idempotency.py -v

build-frontend:
	cd frontend && npm run build
