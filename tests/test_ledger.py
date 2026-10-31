from __future__ import annotations

import sqlite3

import pytest

from afm_core.ledger import Ledger

SETTINGS = {"instrument": "EQUITY", "language": "FASTEXPR", "neutralization": "INDUSTRY"}


def test_register_is_idempotent() -> None:
    with Ledger.in_memory() as ledger:
        first = ledger.register_candidate("rank(f_00)", SETTINGS)
        second = ledger.register_candidate("  rank(f_00) ", SETTINGS)
        assert first == second


def test_plan_requires_a_known_candidate() -> None:
    with Ledger.in_memory() as ledger:
        with pytest.raises(KeyError):
            ledger.create_plan("CAND-" + "0" * 64, "a" * 64, 1)


def test_attempt_and_observation_flow() -> None:
    with Ledger.in_memory() as ledger:
        cid = ledger.register_candidate("rank(f_00)", SETTINGS)
        plan = ledger.create_plan(cid, "b" * 64, 7)
        attempt = ledger.start_attempt(plan)
        observation = ledger.complete_attempt(attempt, {"sharpe": 2.0, "fitness": 2.0})
        assert observation.startswith("OBS-")
        assert ledger.plan_prereg_digest(plan) == "b" * 64


def test_attempt_cannot_complete_twice() -> None:
    with Ledger.in_memory() as ledger:
        cid = ledger.register_candidate("rank(f_00)", SETTINGS)
        plan = ledger.create_plan(cid, "b" * 64, 7)
        attempt = ledger.start_attempt(plan)
        ledger.complete_attempt(attempt, {"sharpe": 2.0})
        with pytest.raises(KeyError):
            ledger.complete_attempt(attempt, {"sharpe": 2.0})


def test_outcomes_are_terminal_in_both_directions() -> None:
    with Ledger.in_memory() as ledger:
        cid = ledger.register_candidate("rank(f_00)", SETTINGS)
        plan = ledger.create_plan(cid, "b" * 64, 7)
        attempt = ledger.start_attempt(plan)
        ledger.complete_attempt(attempt, {"sharpe": 2.0})
        ledger.record_outcome(attempt, "recognized", "all gates passed")

        connection = ledger._conn  # noqa: SLF001 - the test is about the schema
        with pytest.raises(sqlite3.IntegrityError, match="terminal"):
            connection.execute("UPDATE outcomes SET outcome_class = 'no_value'")
        with pytest.raises(sqlite3.IntegrityError, match="terminal"):
            connection.execute("DELETE FROM outcomes")


def test_unknown_outcome_class_is_rejected() -> None:
    with Ledger.in_memory() as ledger:
        cid = ledger.register_candidate("rank(f_00)", SETTINGS)
        plan = ledger.create_plan(cid, "b" * 64, 7)
        attempt = ledger.start_attempt(plan)
        ledger.complete_attempt(attempt, {"sharpe": 2.0})
        with pytest.raises(ValueError, match="unknown outcome class"):
            ledger.record_outcome(attempt, "kind_of_worked", "no")


def test_outcome_counts_read_back_from_the_ledger() -> None:
    with Ledger.in_memory() as ledger:
        for index, outcome in enumerate(("recognized", "no_value", "no_value")):
            cid = ledger.register_candidate(f"rank(f_{index:02d})", SETTINGS)
            plan = ledger.create_plan(cid, "b" * 64, index)
            attempt = ledger.start_attempt(plan)
            ledger.complete_attempt(attempt, {"sharpe": 1.0})
            ledger.record_outcome(attempt, outcome, "because")
        assert ledger.outcome_counts() == {"recognized": 1, "no_value": 2}
