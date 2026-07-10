"""Regression tests for production deployment scripts and compose config."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SH = ROOT / "deploy.sh"
COMPOSE_FILE = ROOT / "docker-compose.prod.yml"


def _require_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker not available")


@pytest.mark.parametrize(
    "pattern",
    [
        "--entrypoint certbot certbot certonly",
        "--entrypoint certbot certbot renew",
    ],
)
def test_deploy_sh_uses_certbot_entrypoint_override(pattern: str) -> None:
    text = DEPLOY_SH.read_text()
    assert pattern in text


def test_docker_compose_prod_parses_with_defaults() -> None:
    _require_docker()
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "POSTGRES_PASSWORD": "test-secret"},
    )
    assert result.returncode == 0, result.stderr


def test_docker_compose_cpu_limits_are_configurable() -> None:
    _require_docker()
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **dict(__import__("os").environ),
            "POSTGRES_PASSWORD": "test-secret",
            "COMPOSE_CPU_APP": "0.25",
            "COMPOSE_MEM_APP": "768M",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "cpus: 0.25" in result.stdout


def test_ensure_demo_account_script_exists() -> None:
    assert (ROOT / "scripts" / "ensure_demo_account.py").is_file()


def test_docker_entrypoint_skips_missing_demo_script() -> None:
    text = (ROOT / "scripts" / "docker-entrypoint.sh").read_text()
    assert '[ -f /app/scripts/ensure_demo_account.py ]' in text
