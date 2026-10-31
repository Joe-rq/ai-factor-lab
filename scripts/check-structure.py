#!/usr/bin/env python3
"""Rule-layer checks that a machine can decide.

Run with::

    uv run python scripts/check-structure.py

Exits non-zero and prints every finding. This is the first of the three
verification layers: anything a rule can judge should never wait for a human.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "afm_core"

REQUIRED = (
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "SECURITY.md",
    "pyproject.toml",
    "src/afm_core/__init__.py",
    "src/afm_core/identity.py",
    "src/afm_core/ledger.py",
    "src/afm_core/prereg.py",
    "src/afm_core/gates.py",
    "src/afm_core/classify.py",
    "src/afm_core/synthetic.py",
    "examples/synthetic/run_demo.py",
    "docs/architecture.md",
    "docs/preregistration.md",
    "docs/verification.md",
    "docs/positive-controls.md",
    "docs/workflow.md",
    "docs/case-study.md",
    "docs/production-vs-repo.md",
    "docs/assets/worldquant-gold.png",
    "tests/test_identity.py",
    "tests/test_ledger.py",
    "tests/test_prereg.py",
    "tests/test_gates.py",
    "tests/test_demo.py",
    "scripts/check-structure.py",
    "scripts/check-hygiene.py",
)

FORBIDDEN_IMPORTS = {
    "httpx",
    "requests",
    "aiohttp",
    "urllib.request",
    "http.client",
    "socket",
}

MAX_MODULE_LINES = 400


def check_required() -> list[str]:
    return [f"missing required file: {name}" for name in REQUIRED if not (ROOT / name).is_file()]


def check_imports() -> list[str]:
    findings: list[str] = []
    for path in sorted(SOURCE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name in FORBIDDEN_IMPORTS:
                    findings.append(f"{path.relative_to(ROOT)}: forbidden import {name!r}")
    return findings


def check_docstrings() -> list[str]:
    findings: list[str] = []
    for path in sorted(SOURCE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not ast.get_docstring(tree):
            findings.append(f"{path.relative_to(ROOT)}: module docstring is missing")
    return findings


def check_line_budget() -> list[str]:
    findings: list[str] = []
    for path in sorted(SOURCE.glob("*.py")):
        lines = path.read_text(encoding="utf-8").count("\n")
        if lines > MAX_MODULE_LINES:
            findings.append(
                f"{path.relative_to(ROOT)}: {lines} lines exceeds the {MAX_MODULE_LINES} budget"
            )
    return findings


def main() -> int:
    findings = check_required() + check_imports() + check_docstrings() + check_line_budget()
    if findings:
        print("structure check failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("structure check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
