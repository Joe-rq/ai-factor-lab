from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY / "examples" / "synthetic" / "run_demo.py"

spec = importlib.util.spec_from_file_location("run_demo", MODULE_PATH)
assert spec and spec.loader
run_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_demo)


def test_candidate_generation_is_deterministic() -> None:
    platform = run_demo.SyntheticPlatform()
    first = run_demo.generate_candidates(platform, 100, 20261031)
    second = run_demo.generate_candidates(platform, 100, 20261031)
    assert first == second
    assert len(first) == 100
    assert platform.control_expression in first
    assert platform.known_positive in first


def test_pipeline_records_every_candidate(tmp_path: Path) -> None:
    rows, report = run_demo.run(tmp_path / "demo.db", 40, 20261031)
    assert len(rows) == 40
    assert "Outcome counts" in report
    assert "prereg digest" in report


def test_control_is_not_recognized(tmp_path: Path) -> None:
    rows, _ = run_demo.run(tmp_path / "demo.db", 40, 20261031)
    control = [row for row in rows if row["expression"] == "rank(f_29)"][0]
    assert control["outcome_class"] != "recognized"
    assert "violates" in control["rationale"]


def test_zero_variance_candidate_is_operational_error(tmp_path: Path) -> None:
    rows, _ = run_demo.run(tmp_path / "demo.db", 40, 20261031)
    constant = [row for row in rows if row["expression"] == "rank(f_28)"][0]
    assert constant["outcome_class"] == "operational_error"
    assert "not measured" in constant["rationale"]


def test_known_positive_is_recognized(tmp_path: Path) -> None:
    rows, _ = run_demo.run(tmp_path / "demo.db", 40, 20261031)
    positive = [row for row in rows if row["expression"] == "rank(f_00)"][0]
    assert positive["outcome_class"] == "recognized"


def test_script_entrypoint_exits_zero(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--db",
            str(tmp_path / "demo.db"),
            "--candidates",
            "40",
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "POSITIVE CONTROL FAILED" not in result.stdout
    assert "rank(f_29)" in result.stdout
