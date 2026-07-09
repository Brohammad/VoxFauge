.PHONY: test lint benchmark-onboarding

test:
	pytest -v --tb=short

lint:
	ruff check src tests

benchmark-onboarding:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2

benchmark-onboarding-json:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2 --json

benchmark-onboarding-memory:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2 --memory --json
