.PHONY: test test-unit test-integration test-feature test-failure test-e2e test-cov lint benchmark-onboarding benchmark-knowledge-base livekit-worker deploy-validate

test:
	pytest -v --tb=short

test-unit:
	pytest tests/unit -v --tb=short

test-integration:
	pytest tests/integration -v --tb=short

test-feature:
	pytest tests/feature -v --tb=short -m feature

test-failure:
	pytest tests/failure -v --tb=short -m failure

test-e2e:
	pytest tests/e2e -v --tb=short -m e2e

test-cov:
	python scripts/generate_coverage_report.py --fail-under=70

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

knowledge-worker:
	python -m voxforge.infrastructure.knowledge.worker
