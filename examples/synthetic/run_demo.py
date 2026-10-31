#!/usr/bin/env python3
"""End-to-end demo: register -> plan -> simulate -> record -> classify.

The demo is intentionally a *pipeline*, not a script that prints hand-picked
numbers. Every number in the report came out of the ledger, and every outcome
came out of the same gate evaluator a production run would use.

Run it with::

    uv run python examples/synthetic/run_demo.py

Exit code is 1 if the positive control passed (which would mean the harness is
not discriminating), otherwise 0.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Allow running straight from a checkout before `uv sync` installs the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from afm_core.classify import classify
from afm_core.gates import evaluate
from afm_core.ledger import Ledger
from afm_core.prereg import Gate, Preregistration
from afm_core.synthetic import SyntheticConfig, SyntheticPlatform

METRIC_COLUMNS = ("sharpe", "fitness", "turnover")


def build_preregistration() -> Preregistration:
    """The decision rule is frozen before the first simulation runs."""
    return Preregistration(
        hypothesis=(
            "A signal built from a field that leads next-day returns can clear "
            "a 2.0 Sharpe and a 2.0 fitness bar at moderate turnover."
        ),
        gates=(
            Gate("sharpe_floor", "sharpe", ">=", 2.0, "value"),
            Gate("fitness_floor", "fitness", ">=", 2.0, "value"),
            Gate("turnover_cap", "turnover", "<=", 0.80, "value"),
            Gate("direction", "mean_pnl", ">", 0.0, "direction"),
        ),
        decisions={
            "pass": "recognized",
            "fail": "no_value, or effective_negative when the direction gate fails",
            "not_measured": "operational_error; nothing was decided",
        },
        invalid_slots=(
            "sharpe_floor:not_measured",
            "fitness_floor:not_measured",
            "turnover_cap:not_measured",
            "direction:not_measured",
        ),
    )


def generate_candidates(platform: SyntheticPlatform, count: int, seed: int) -> list[str]:
    """One hundred deterministic expressions, including two named controls."""
    rng = random.Random(seed)
    fields = platform.field_names()
    expressions: list[str] = []

    def add(expression: str) -> None:
        if expression not in expressions:
            expressions.append(expression)

    # Named controls, always present:
    add(platform.control_expression)  # must not be recognized
    add(platform.known_positive)  # the world is built to support this one
    add("-rank(f_00)")  # direction gate must fire
    add("rank(f_28)")  # constant field: zero variance, not measured

    while len(expressions) < count:
        first, second = rng.choice(fields), rng.choice(fields)
        form = rng.randrange(5)
        if form == 0:
            expression = f"rank({first})"
        elif form == 1:
            expression = f"-rank({first})"
        elif form == 2:
            expression = f"rank({first}) + rank({second})"
        elif form == 3 and first != second:
            expression = f"rank({first}) - rank({second})"
        elif form == 3:
            expression = f"rank({first})"
        else:
            expression = first
        add(expression)

    return expressions[:count]


def run(database: Path, count: int, seed: int) -> tuple[list[dict], str]:
    platform = SyntheticPlatform(SyntheticConfig(seed=seed))
    prereg = build_preregistration()
    constants = {
        "instrument": "EQUITY",
        "language": "FASTEXPR",
        "neutralization": "INDUSTRY",
    }

    if database.exists():
        database.unlink()
    ledger = Ledger.open(database)
    try:
        for expression in generate_candidates(platform, count, seed):
            cid = ledger.register_candidate(expression, constants)
            plan_id = ledger.create_plan(cid, prereg.digest(), seed)
            attempt_id = ledger.start_attempt(plan_id)

            try:
                simulation = platform.simulate(expression)
                metrics = simulation.as_dict()
                failure = None
            except ValueError as exc:
                metrics = {
                    name: None for name in ("sharpe", "fitness", "turnover", "returns", "mean_pnl")
                }
                failure = str(exc)

            ledger.complete_attempt(attempt_id, metrics)
            results = evaluate(prereg, metrics)
            outcome_class, rationale = classify(results)
            if failure:
                rationale = f"simulation error: {failure}; {rationale}"
            ledger.record_outcome(attempt_id, outcome_class, rationale)
    finally:
        ledger.close()

    # Everything below reads back from the ledger, not from local variables.
    with Ledger.open(database) as ledger:
        rows = ledger.outcomes()
        counts = ledger.outcome_counts()
    return rows, _render_report(prereg.digest(), rows, counts, platform)


def _format_metric(value: object) -> str:
    if value is None:
        return "  n/a"
    return f"{float(value):7.3f}"


def _render_report(
    prereg_digest: str,
    rows: list[dict],
    counts: dict[str, int],
    platform: SyntheticPlatform,
) -> str:
    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("ai-factor-lab synthetic run")
    lines.append("=" * 100)
    lines.append(f"prereg digest : {prereg_digest}")
    lines.append(f"fields        : {len(platform.field_names())}   candidates: {len(rows)}")
    lines.append(f"control       : {platform.control_expression} (must not be recognized)")
    lines.append(f"known positive: {platform.known_positive}")
    lines.append("")
    lines.append(
        f"{'expression':<32} {'sharpe':>7} {'fitness':>7} {'turnover':>8}  {'outcome':<18} reason"
    )
    lines.append("-" * 100)

    for row in rows:
        metrics = json.loads(row["metrics"]) if row["metrics"] else {}
        values = " ".join(_format_metric(metrics.get(name)) for name in METRIC_COLUMNS)
        reason = row["rationale"].split(";")[0]
        lines.append(
            f"{row['expression'][:32]:<32} {values}  {row['outcome_class']:<18} {reason[:48]}"
        )

    lines.append("")
    lines.append("Outcome counts")
    lines.append("-" * 100)
    for name in ("recognized", "effective_negative", "no_value", "operational_error", "pending"):
        lines.append(f"  {name:<20} {counts.get(name, 0)}")

    lines.append("")
    lines.append("Positive control")
    lines.append("-" * 100)
    control_rows = [row for row in rows if row["expression"] == platform.control_expression]
    if not control_rows:
        lines.append("  CONTROL MISSING -- the harness cannot prove it discriminates")
    else:
        control = control_rows[0]
        lines.append(f"  {control['expression']} -> {control['outcome_class']}")
        lines.append(f"  reason: {control['rationale']}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("synthetic_run.db"))
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)

    rows, report = run(args.db, args.candidates, args.seed)
    print(report)
    if args.report:
        args.report.write_text(report + "\n", encoding="utf-8")
        print(f"\nreport written to {args.report}")

    control = [row for row in rows if row["expression"] == "rank(f_29)"]
    if control and control[0]["outcome_class"] == "recognized":
        print("\nPOSITIVE CONTROL FAILED: a known-negative candidate was recognized.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
