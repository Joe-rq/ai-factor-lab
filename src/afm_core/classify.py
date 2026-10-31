"""Outcome classification: a closed vocabulary, in one place.

The classes are deliberately not a ranking. They answer different questions:

* ``recognized`` -- the gates passed; the candidate earned a place in the book.
* ``effective_negative`` -- the directional claim was tested and rejected.
* ``no_value`` -- the run was valid but the value thresholds were not met.
* ``operational_error`` -- something was not measured; nothing was decided.
* ``pending`` -- recorded but not yet judged.

Keeping ``no_value`` and ``operational_error`` apart is the whole point. Merging
them teaches a system that "not measured" means "failed", and after that every
silent data problem looks like evidence.
"""

from __future__ import annotations

from collections.abc import Sequence

from .gates import FAIL, NOT_MEASURED, PASS, GateResult, explain

OUTCOME_CLASSES = (
    "recognized",
    "effective_negative",
    "no_value",
    "operational_error",
    "pending",
)


def classify(results: Sequence[GateResult]) -> tuple[str, str]:
    """Return ``(outcome_class, rationale)`` for a set of gate results.

    A definitive failure outranks an unmeasured gate: one gate failing is
    positive evidence, while a missing measurement elsewhere cannot undo it.
    ``not_measured`` only becomes ``operational_error`` when nothing failed.
    """
    if not results:
        raise ValueError("cannot classify an empty gate set")

    failed = [result for result in results if result.status == FAIL]
    unmeasured = [result for result in results if result.status == NOT_MEASURED]
    trail = explain(results)

    if failed:
        directional = [result for result in failed if result.gate.kind == "direction"]
        if directional:
            return (
                "effective_negative",
                "direction gate failed: "
                + ", ".join(result.gate.name for result in directional)
                + f"; {trail}",
            )
        return ("no_value", f"value gate failed: {trail}")
    if unmeasured:
        return (
            "operational_error",
            f"not measured: {', '.join(result.gate.name for result in unmeasured)}; {trail}",
        )
    if all(result.status == PASS for result in results):
        return ("recognized", f"all gates passed: {trail}")
    raise AssertionError("unreachable: every gate status handled above")
