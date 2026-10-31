#!/usr/bin/env python3
"""Hygiene scan: refuse to publish identifiers, paths, and secrets.

Run with::

    uv run python scripts/check-hygiene.py

The patterns are intentionally narrow. This is not a replacement for a secret
scanner; it is the cheap, always-on gate that catches the mistakes this
repository is most likely to make: pasting a platform ID, an absolute path, or
a credential into an example.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".cfg", ".ini"}
SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def _assembled(*parts: str) -> re.Pattern[str]:
    """Build a pattern from fragments so this file does not match itself.

    The repository's acceptance check greps for these literals directly; a
    scanner that contains them would report itself and drown the signal.
    """
    return re.compile("".join(parts))


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("platform alpha identifier", re.compile(r"\bA10[A-Za-z0-9]{5,}\b")),
    ("platform credential prefix", _assembled(r"\bWQB", r"_\w+")),
    ("legacy candidate prefix", _assembled("CAND", "-v1-")),
    ("local run directory", _assembled("state", "/run")),
    ("absolute home path", re.compile(r"/Users/[^/\s]+")),
    ("private key block", re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY")),
    (
        "assigned secret",
        re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"]{4,}['\"]"),
    ),
    ("email address", re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b")),
)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == SELF:
            continue
        if any(part in SKIP_DIRECTORIES for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return sorted(files)


def scan() -> list[str]:
    findings: list[str] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}: {label}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("hygiene scan failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("hygiene scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
