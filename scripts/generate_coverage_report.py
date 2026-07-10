#!/usr/bin/env python3
"""Generate coverage.xml, HTML report, and markdown summary for CI artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = "src/voxforge/modules"


def run_pytest_cov(args: argparse.Namespace) -> None:
    html_dir = ROOT / "htmlcov"
    xml_path = ROOT / "coverage.xml"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "--tb=no",
        f"--cov={args.package}",
        f"--cov-report=xml:{xml_path}",
        f"--cov-report=html:{html_dir}",
        "--cov-report=term-missing",
        f"--cov-fail-under={args.fail_under}",
    ]
    if args.markers:
        cmd.extend(["-m", args.markers])
    subprocess.run(cmd, cwd=ROOT, check=False)


def parse_coverage_xml(xml_path: Path) -> tuple[float, float, int, int]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    overall = root.attrib
    line_rate = float(overall.get("line-rate", 0)) * 100
    branch_rate = float(overall.get("branch-rate", 0)) * 100
    lines_valid = int(overall.get("lines-valid", 0))
    lines_covered = int(overall.get("lines-covered", 0))
    return line_rate, branch_rate, lines_covered, lines_valid


def business_logic_rate(xml_path: Path) -> float:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    covered = 0
    total = 0
    for cls in root.findall(".//class"):
        filename = cls.attrib.get("filename", "")
        if not (
            filename.startswith("src/voxforge/modules/")
            or filename.startswith("src/voxforge/core/")
        ):
            continue
        for line in cls.findall("lines/line"):
            total += 1
            if int(line.attrib.get("hits", 0)) > 0:
                covered += 1
    return (covered / total * 100) if total else 0.0


def write_markdown(
    md_path: Path,
    *,
    overall: float,
    branch: float,
    business: float,
    covered: int,
    total: int,
    fail_under: int,
    business_target: int,
) -> None:
    status = "PASS" if overall >= fail_under and business >= business_target else "FAIL"
    md_path.write_text(
        "\n".join(
            [
                "# VoxForge Coverage Report",
                "",
                "| Metric | Value | Target |",
                "|--------|------:|-------:|",
                f"| Overall line coverage | {overall:.1f}% | {fail_under}% |",
                f"| Branch coverage | {branch:.1f}% | — |",
                f"| Business logic coverage | {business:.1f}% | {business_target}% |",
                f"| Lines covered | {covered:,} / {total:,} | — |",
                f"| Gate status | **{status}** | — |",
                "",
                "## Artifacts",
                "",
                "- `coverage.xml` — CI/Sonar compatible",
                "- `htmlcov/index.html` — interactive HTML report",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tests and emit coverage artifacts")
    parser.add_argument("--package", default="voxforge")
    parser.add_argument("--fail-under", type=int, default=70)
    parser.add_argument("--business-target", type=int, default=85)
    parser.add_argument("--markers", default="")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    if not args.skip_tests:
        run_pytest_cov(args)

    xml_path = ROOT / "coverage.xml"
    if not xml_path.exists():
        print("coverage.xml not found", file=sys.stderr)
        return 1

    overall, branch, covered, total = parse_coverage_xml(xml_path)
    business = business_logic_rate(xml_path)
    md_path = ROOT / "docs" / "testing" / "coverage-report.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(
        md_path,
        overall=overall,
        branch=branch,
        business=business,
        covered=covered,
        total=total,
        fail_under=args.fail_under,
        business_target=args.business_target,
    )
    print(f"Overall: {overall:.1f}% | Business logic: {business:.1f}% | Report: {md_path}")
    return 0 if overall >= args.fail_under else 1


if __name__ == "__main__":
    raise SystemExit(main())
