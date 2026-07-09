#!/usr/bin/env python3
"""Reproducible benchmark for onboarding programmatic sample-call pipeline.

Measures end-to-end turn latency, platform overhead, evaluation latency, and
optional memory retrieval latency using mock providers (no API keys required).

Usage:
    python scripts/benchmark_onboarding.py
    python scripts/benchmark_onboarding.py --iterations 20 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

# Allow running from repo root without install
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from voxforge.config import Settings, get_settings
from voxforge.core.domain.entities import TransportType
from voxforge.core.domain.evaluation import TurnEvaluationInput
from voxforge.infrastructure.db.base import Base
from voxforge.infrastructure.db.evaluation_repository import EvaluationRepository
from voxforge.infrastructure.db.memory_repository import MemoryRepository
from voxforge.infrastructure.db.outcome_repository import OutcomeRepository
from voxforge.infrastructure.providers.factory import (
    create_llm_provider,
    create_stt_provider,
    create_tts_provider,
)
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.infrastructure.voice.programmatic_runner import ProgrammaticPipelineRunner
from voxforge.modules.agent_orchestrator.application.factory import create_response_generator
from voxforge.modules.evaluation.application.service import EvaluationEngine
from voxforge.modules.memory.application.service import MemoryService
from voxforge.modules.onboarding.application.sample_scripts import get_default_sample_script
from voxforge.modules.outcomes.application.service import OutcomeExtractionService
from voxforge.modules.session_manager.application.service import SessionManager
from voxforge.modules.voice_gateway.application.pipeline import VoicePipelineService


@dataclass
class LatencyStats:
    mean: float
    p50: float
    p95: float
    min: float
    max: float

    @classmethod
    def from_samples(cls, samples: list[float]) -> LatencyStats:
        ordered = sorted(samples)
        count = len(ordered)

        def percentile(p: float) -> float:
            if count == 1:
                return ordered[0]
            index = min(int(round((p / 100) * (count - 1))), count - 1)
            return ordered[index]

        return cls(
            mean=round(statistics.mean(ordered), 3),
            p50=round(percentile(50), 3),
            p95=round(percentile(95), 3),
            min=round(ordered[0], 3),
            max=round(ordered[-1], 3),
        )


class FixedEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, text: str) -> list[float]:
        return list(self._vector)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [list(self._vector) for _ in texts]


def _configure_benchmark_env() -> None:
    os.environ.setdefault("STT_PROVIDER", "mock")
    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("TTS_PROVIDER", "mock")
    os.environ.setdefault("EVALUATION_HALLUCINATION_ENABLED", "false")
    os.environ.setdefault("TOOLS_ENABLED", "false")
    os.environ.setdefault("LOG_LEVEL", "ERROR")
    get_settings.cache_clear()


def _environment_metadata() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "providers": {
            "stt": os.getenv("STT_PROVIDER", "mock"),
            "llm": os.getenv("LLM_PROVIDER", "mock"),
            "tts": os.getenv("TTS_PROVIDER", "mock"),
        },
        "memory_enabled": os.getenv("MEMORY_ENABLED", "false").lower() == "true",
    }


async def _build_pipeline(
    db_session,
    fake_redis,
    *,
    memory_enabled: bool,
) -> tuple[SessionManager, ProgrammaticPipelineRunner, EvaluationEngine, MemoryService | None]:
    from voxforge.core.events.bus import EventBus

    settings = get_settings()
    event_bus = EventBus()
    state_store = RedisSessionStateStore(fake_redis, ttl_seconds=settings.session_state_ttl_seconds)
    session_manager = SessionManager(db_session, state_store, event_bus, settings)

    llm = create_llm_provider(settings)
    memory_service: MemoryService | None = None
    if memory_enabled:
        memory_service = MemoryService(
            MemoryRepository(db_session),
            FixedEmbedder([1.0, 0.0, 0.0] + [0.0] * 1533),
            Settings(memory_enabled=True),
            llm,
        )

    response_generator = create_response_generator(settings, llm, memory_service, None)
    pipeline = VoicePipelineService(
        session_manager,
        create_stt_provider(settings),
        response_generator,
        create_tts_provider(settings),
        settings,
        memory_service,
        EvaluationEngine(EvaluationRepository(db_session), settings, llm),
        OutcomeExtractionService(OutcomeRepository(db_session)),
    )
    runner = ProgrammaticPipelineRunner(pipeline)
    evaluation = EvaluationEngine(EvaluationRepository(db_session), settings, llm)
    return session_manager, runner, evaluation, memory_service


async def run_benchmark(*, iterations: int, warmup: int, memory_enabled: bool) -> dict:
    import fakeredis.aioredis

    _configure_benchmark_env()
    if memory_enabled:
        os.environ["MEMORY_ENABLED"] = "true"
        get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    script = get_default_sample_script()

    wall_clock_samples: list[float] = []
    e2e_samples: list[float] = []
    llm_first_token_samples: list[float] = []
    tts_first_byte_samples: list[float] = []
    evaluation_samples: list[float] = []
    memory_retrieval_samples: list[float] = []

    async with factory() as db_session:
        session_manager, runner, evaluation, memory_service = await _build_pipeline(
            db_session, fake_redis, memory_enabled=memory_enabled
        )
        org_id = uuid4()

        total_runs = warmup + iterations
        for i in range(total_runs):
            session = await session_manager.create_session(
                transport_type=TransportType.WEBSOCKET,
                config={"sample_call": True, "script_id": script.script_id},
                org_id=org_id,
            )

            wall_start = time.perf_counter()
            metrics = await runner.run_scripted_turn(
                session_id=session.id,
                org_id=org_id,
                transcript=script.user_transcript,
                user_metadata=script.user_metadata,
            )
            wall_ms = (time.perf_counter() - wall_start) * 1000

            if i >= warmup:
                wall_clock_samples.append(wall_ms)
                if metrics.e2e_ms is not None:
                    e2e_samples.append(metrics.e2e_ms)
                if metrics.llm_first_token_ms is not None:
                    llm_first_token_samples.append(metrics.llm_first_token_ms)
                if metrics.tts_first_byte_ms is not None:
                    tts_first_byte_samples.append(metrics.tts_first_byte_ms)

                eval_start = time.perf_counter()
                await evaluation.evaluate_turn(
                    TurnEvaluationInput(
                        session_id=session.id,
                        org_id=org_id,
                        user_transcript=script.user_transcript,
                        assistant_response=(
                        "I verified your account and updated the billing contact."
                    ),
                        stt_ms=metrics.stt_ms,
                        llm_first_token_ms=metrics.llm_first_token_ms,
                        tts_first_byte_ms=metrics.tts_first_byte_ms,
                        e2e_ms=metrics.e2e_ms,
                    )
                )
                evaluation_samples.append((time.perf_counter() - eval_start) * 1000)

                if memory_service is not None:
                    mem_start = time.perf_counter()
                    await memory_service.retrieve_context(
                        org_id=org_id,
                        session_id=session.id,
                        query=script.user_transcript,
                    )
                    memory_retrieval_samples.append((time.perf_counter() - mem_start) * 1000)

            await session_manager.end_session(session.id, reason="benchmark")
            await db_session.commit()

    await engine.dispose()

    overhead_samples = [
        wall - e2e for wall, e2e in zip(wall_clock_samples, e2e_samples, strict=False)
    ]

    result = {
        "benchmark": "onboarding_sample_call",
        "iterations": iterations,
        "warmup": warmup,
        "environment": _environment_metadata(),
        "latency_ms": {
            "wall_clock": LatencyStats.from_samples(wall_clock_samples).__dict__,
            "pipeline_e2e": LatencyStats.from_samples(e2e_samples).__dict__,
            "pipeline_overhead": LatencyStats.from_samples(overhead_samples).__dict__,
            "llm_first_token": LatencyStats.from_samples(llm_first_token_samples).__dict__,
            "tts_first_byte": LatencyStats.from_samples(tts_first_byte_samples).__dict__,
            "evaluation_isolated": LatencyStats.from_samples(evaluation_samples).__dict__,
        },
        "notes": {
            "provider_latency": "excluded (mock STT/LLM/TTS)",
            "pipeline_overhead_definition": "wall_clock_ms - pipeline_e2e_ms",
            "memory_retrieval": (
                LatencyStats.from_samples(memory_retrieval_samples).__dict__
                if memory_retrieval_samples
                else None
            ),
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark onboarding sample-call pipeline")
    parser.add_argument("--iterations", type=int, default=10, help="Measured iterations")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup iterations (discarded)")
    parser.add_argument("--memory", action="store_true", help="Include memory retrieval benchmark")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    result = asyncio.run(
        run_benchmark(iterations=args.iterations, warmup=args.warmup, memory_enabled=args.memory)
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    latency = result["latency_ms"]
    print("VoxForge Onboarding Benchmark")
    print("=" * 40)
    print(f"Iterations: {result['iterations']} (warmup {result['warmup']})")
    print(f"Platform:   {result['environment']['platform']}")
    print(f"Python:     {result['environment']['python']}")
    print(f"Providers:  {result['environment']['providers']}")
    print()
    print("Latency (ms):")
    for key, stats in latency.items():
        print(
            f"  {key:22} mean={stats['mean']:8.3f}  "
            f"p50={stats['p50']:8.3f}  p95={stats['p95']:8.3f}"
        )
    memory = result["notes"]["memory_retrieval"]
    if memory:
        print(
            f"  memory_retrieval       mean={memory['mean']:8.3f}  "
            f"p50={memory['p50']:8.3f}  p95={memory['p95']:8.3f}"
        )
    else:
        print("  memory_retrieval       N/A (pass --memory to enable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
