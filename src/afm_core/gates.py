"""Gate evaluation: three outcomes per gate, one verdict overall.

Gate status is deliberately ternary: ``pass``, ``fail``, ``not_measured``.
Binary gates are how "we could not measure it" gets recorded as "it failed".

Verdict precedence is ``fail`` > ``not_measured`` > ``pass``. A single failed
gate is enough to reject; if nothing failed but something was not measured,
the run is inconclusive rather than accepted.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .prereg import OPERATORS, Gate, Preregistration

PASS = "pass"
FAIL = "fail"
NOT_MEASURED = "not_measured"


@dataclass(frozen=True)
class GateResult:
    gate: Gate
    value: float | None
    status: str

    def describe(self) -> str:
        if self.status == NOT_MEASURED:
            return f"{self.gate.name}: not measured ({self.gate.describe()})"
        judgement = "ok" if self.status == PASS else "violates"
        return f"{self.gate.name}: {self.value:.4f} {judgement} {self.gate.describe()}"


def evaluate_gate(gate: Gate, metrics: Mapping[str, float | None]) -> GateResult:
    raw = metrics.get(gate.metric)
    if raw is None or not math.isfinite(float(raw)):
        return GateResult(gate=gate, value=None, status=NOT_MEASURED)
    value = float(raw)
    passed = OPERATORS[gate.op](value, float(gate.threshold))
    return GateResult(gate=gate, value=value, status=PASS if passed else FAIL)


def evaluate(prereg: Preregistration, metrics: Mapping[str, float | None]) -> list[GateResult]:
    return [evaluate_gate(gate, metrics) for gate in prereg.gates]


def verdict(results: Sequence[GateResult]) -> str:
    if not results:
        raise ValueError("no gate results to judge")
    statuses = {result.status for result in results}
    if FAIL in statuses:
        return FAIL
    if NOT_MEASURED in statuses:
        return NOT_MEASURED
    return PASS


def explain(results: Sequence[GateResult]) -> str:
    """A one-line audit trail: every gate, in declaration order."""
    return "; ".join(result.describe() for result in results)
