"""Evaluation quality gate script tests."""

import subprocess
import sys
from pathlib import Path


def test_eval_gate_passes():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "eval_gate.py")],
        cwd=root,
        capture_output=True,
        text=True,
        env={
            **dict(__import__("os").environ),
            "EVAL_GATE_MIN_OVERALL": "0.75",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "EVAL GATE PASSED" in result.stdout
