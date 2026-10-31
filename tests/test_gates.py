from __future__ import annotations

from afm_core.classify import classify
from afm_core.gates import FAIL, NOT_MEASURED, PASS, evaluate, verdict
from afm_core.prereg import Gate, Preregistration


def rule() -> Preregistration:
    return Preregistration(
        hypothesis="A leads B.",
        gates=(
            Gate("sharpe_floor", "sharpe", ">=", 1.0, "value"),
            Gate("direction", "mean_pnl", ">", 0.0, "direction"),
        ),
        decisions={"pass": "go", "fail": "stop", "not_measured": "rerun"},
        invalid_slots=("sharpe_floor:not_measured", "direction:not_measured"),
    )


def test_missing_metric_is_not_measured_not_zero() -> None:
    results = evaluate(rule(), {"sharpe": None, "mean_pnl": 0.01})
    statuses = {result.gate.name: result.status for result in results}
    assert statuses["sharpe_floor"] == NOT_MEASURED
    assert statuses["direction"] == PASS


def test_fail_outranks_not_measured() -> None:
    results = evaluate(rule(), {"sharpe": 0.5, "mean_pnl": None})
    assert verdict(results) == FAIL


def test_not_measured_outranks_pass() -> None:
    results = evaluate(rule(), {"sharpe": 2.0, "mean_pnl": None})
    assert verdict(results) == NOT_MEASURED


def test_all_pass() -> None:
    results = evaluate(rule(), {"sharpe": 2.0, "mean_pnl": 0.01})
    assert verdict(results) == PASS


def test_classification_priorities() -> None:
    operational = evaluate(rule(), {"sharpe": None, "mean_pnl": 0.01})
    assert classify(operational)[0] == "operational_error"

    negative = evaluate(rule(), {"sharpe": 2.0, "mean_pnl": -0.01})
    assert classify(negative)[0] == "effective_negative"

    no_value = evaluate(rule(), {"sharpe": 0.5, "mean_pnl": 0.01})
    assert classify(no_value)[0] == "no_value"

    recognized = evaluate(rule(), {"sharpe": 2.0, "mean_pnl": 0.01})
    assert classify(recognized)[0] == "recognized"


def test_rationale_names_the_failing_gate() -> None:
    results = evaluate(rule(), {"sharpe": 0.5, "mean_pnl": 0.01})
    _, rationale = classify(results)
    assert "sharpe_floor" in rationale
    assert "violates" in rationale


def test_definitive_failure_outranks_an_unmeasured_gate() -> None:
    results = evaluate(rule(), {"sharpe": 0.5, "mean_pnl": None})
    assert classify(results)[0] == "no_value"


def test_failed_direction_outranks_an_unmeasured_value_gate() -> None:
    results = evaluate(rule(), {"sharpe": None, "mean_pnl": -0.01})
    assert classify(results)[0] == "effective_negative"
