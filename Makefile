.PHONY: test lint benchmark-onboarding benchmark-knowledge-base livekit-worker deploy-validate

test:
	pytest -v --tb=short

lint:
	ruff check src tests

livekit-worker:
	python -m voxforge.infrastructure.livekit.worker

deploy-validate:
	ENV_FILE=.env.production APP_ENV=production PYTHONPATH=src python scripts/validate_production_env.py

benchmark-onboarding:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2

benchmark-onboarding-json:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2 --json

benchmark-onboarding-memory:
	python scripts/benchmark_onboarding.py --iterations 10 --warmup 2 --memory --json

benchmark-knowledge-base:
	python scripts/benchmark_knowledge_base.py --iterations 100

benchmark-knowledge-base-json:
	python scripts/benchmark_knowledge_base.py --iterations 100 --json
