#!/usr/bin/env python3
"""Regenerate docs/project-metrics.md from repository state."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTEST = ROOT / ".venv" / "bin" / "pytest"
if not PYTEST.exists():
    PYTEST = Path(sys.executable)
API_DIR = ROOT / "src" / "voxforge" / "api"
MODULES_DIR = ROOT / "src" / "voxforge" / "modules"


def count_rest_endpoints() -> int:
    pattern = re.compile(r"@router\.(get|post|put|patch|delete)\(")
    total = 0
    for path in API_DIR.rglob("*.py"):
        total += len(pattern.findall(path.read_text()))
    return total


def count_websocket_endpoints() -> int:
    pattern = re.compile(r"@router\.websocket\(")
    total = 0
    for path in API_DIR.rglob("*.py"):
        total += len(pattern.findall(path.read_text()))
    return total


def count_tests() -> int:
    result = subprocess.run(
        [str(PYTEST), "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, "PYTHONPATH": str(ROOT)},
        check=False,
    )
    for line in reversed(result.stdout.splitlines()):
        match = re.search(r"(\d+) tests collected", line)
        if match:
            return int(match.group(1))
    return 0


def coverage_percent() -> str:
    result = subprocess.run(
        [str(PYTEST), "--cov=src/voxforge", "--cov-report=term", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, "PYTHONPATH": str(ROOT)},
        check=False,
    )
    for line in result.stdout.splitlines():
        if line.startswith("TOTAL"):
            parts = line.split()
            return parts[-1]
    return "n/a"


def main() -> None:
    modules = sorted(
        p.name
        for p in MODULES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and p.name != "__pycache__"
    )
    adrs = sorted((ROOT / "docs" / "adr").glob("ADR-*.md"))
    arch_docs = sorted((ROOT / "docs" / "architecture").glob("*.md"))
    benchmarks = sorted((ROOT / "docs" / "benchmarks").glob("*.md"))

    content = f"""# VoxForge Project Metrics

> Single source of truth for repository engineering metrics.  
> Last updated: {datetime.now(UTC).strftime("%Y-%m-%d")}  
> Regenerate: `python scripts/generate_project_metrics.py`

## Summary

| Metric | Value |
|--------|------:|
| Application modules | {len(modules)} |
| REST endpoints | {count_rest_endpoints()} |
| WebSocket endpoints | {count_websocket_endpoints()} |
| Tests collected | {count_tests()} |
| Line coverage (`src/voxforge`) | {coverage_percent()} |
| ADRs | {len(adrs)} |
| Architecture documents | {len(arch_docs)} |
| Benchmark documents | {len(benchmarks)} |

## Application modules ({len(modules)})

{chr(10).join(f"- `{m}`" for m in modules)}

## API surface

| Transport | Count | Entry points |
|-----------|------:|--------------|
| REST | {count_rest_endpoints()} | `/api/v1/*` routers |
| WebSocket | {count_websocket_endpoints()} | `/api/v1/ws/voice` |

## Tests

Run: `PYTHONPATH=. pytest -v`

| Category | Location |
|----------|----------|
| Unit | `tests/unit/` |
| Integration | `tests/integration/` |

## Architecture decision records ({len(adrs)})

{chr(10).join(f"- [{a.name}](adr/{a.name})" for a in adrs)}

## Architecture documents ({len(arch_docs)})

{chr(10).join(f"- [{a.name}](architecture/{a.name})" for a in arch_docs)}

## Benchmarks ({len(benchmarks)})

{chr(10).join(f"- [{b.name}](benchmarks/{b.name})" for b in benchmarks)}

## Supported providers

| Capability | Providers |
|------------|-----------|
| STT | `deepgram`, `mock` |
| LLM | `openai`, `mock` |
| TTS | `cartesia`, `mock` |
| Embeddings | `openai` (`text-embedding-3-small`) |
| WebRTC transport | LiveKit |
| Voice transport | WebSocket, LiveKit WebRTC |

## Supported MCP servers

MCP servers are **runtime-discovered** from `MCP_SERVERS_CONFIG` (stdio transport). Static
tool metadata is used as a degraded fallback when discovery fails. Inspect live status via:

- `GET /api/v1/tools/mcp/health`
- `GET /api/v1/tools/mcp/servers`

No servers are hardcoded in the repository; operators declare servers in environment config.

## Phase status

| Phase | Status |
|-------|--------|
| Phase 0 — Stabilization | Complete |
| Phase 1 — Onboarding voice pipeline | Complete |
| Phase 2 — CI hardening | Complete |
| Phase 3 — MCP runtime discovery | Complete |
| Phase 4 — LiveKit transport adapter | Complete |
| Public deployment | Planned |
| Production hardening & load testing | Planned |
"""
    (ROOT / "docs" / "project-metrics.md").write_text(content)
    print("Wrote docs/project-metrics.md")


if __name__ == "__main__":
    main()
