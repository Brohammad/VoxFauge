.PHONY: test lint benchmark-onboarding livekit-worker

test:
	pytest -v --tb=short

lint:
	ruff check src tests

livekit-worker:
	python -m voxforge.infrastructure.livekit.worker

benchmark-onboarding:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2

benchmark-onboarding-json:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2 --json

benchmark-onboarding-memory:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2 --memory --json
