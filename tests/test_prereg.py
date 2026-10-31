from __future__ import annotations

import pytest

from afm_core.prereg import Gate, Preregistration


def build() -> Preregistration:
    return Preregistration(
        hypothesis="A leads B.",
        gates=(Gate("sharpe_floor", "sharpe", ">=", 1.0),),
        decisions={"pass": "go", "fail": "stop", "not_measured": "rerun"},
        invalid_slots=("sharpe_floor:not_measured",),
    )


def test_digest_is_stable_across_construction_order() -> None:
    one = Preregistration(
        hypothesis="A leads B.",
        gates=(
            Gate("sharpe_floor", "sharpe", ">=", 1.0),
            Gate("turnover_cap", "turnover", "<=", 0.5),
        ),
        decisions={"pass": "go", "fail": "stop", "not_measured": "rerun"},
        invalid_slots=("sharpe_floor:not_measured", "turnover_cap:not_measured"),
    )
    two = Preregistration(
        hypothesis="A leads B.",
        gates=(
            Gate("turnover_cap", "turnover", "<=", 0.5),
            Gate("sharpe_floor", "sharpe", ">=", 1.0),
        ),
        decisions={"not_measured": "rerun", "fail": "stop", "pass": "go"},
        invalid_slots=("turnover_cap:not_measured", "sharpe_floor:not_measured"),
    )
    assert one.digest() == two.digest()


def test_every_gate_needs_an_explicit_not_measured_slot() -> None:
    with pytest.raises(ValueError, match="not-measured slot"):
        Preregistration(
            hypothesis="A leads B.",
            gates=(Gate("sharpe_floor", "sharpe", ">=", 1.0),),
            decisions={"pass": "go", "fail": "stop", "not_measured": "rerun"},
            invalid_slots=(),
        )


def test_decision_table_must_cover_all_three_slots() -> None:
    with pytest.raises(ValueError, match="missing slots"):
        Preregistration(
            hypothesis="A leads B.",
            gates=(Gate("sharpe_floor", "sharpe", ">=", 1.0),),
            decisions={"pass": "go", "fail": "stop"},
            invalid_slots=("sharpe_floor:not_measured",),
        )


def test_gate_metric_and_operator_are_closed_sets() -> None:
    with pytest.raises(ValueError, match="unknown metric"):
        Gate("weird", "sortino", ">=", 1.0)
    with pytest.raises(ValueError, match="unknown operator"):
        Gate("weird", "sharpe", "==", 1.0)


def test_round_trip_through_dict() -> None:
    original = build()
    restored = Preregistration.from_dict(original.to_dict())
    assert restored.digest() == original.digest()
