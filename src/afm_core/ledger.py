"""A small, auditable ledger.

Five tables, one direction of flow::

    candidates -> plans -> attempts -> observations
                                   \\-> outcomes

Every row is derived from content where it makes sense (candidate and
observation IDs) and carries an explicit timestamp where it does not. The
schema enforces the properties that are cheap to enforce and expensive to
recover from:

* ``outcome_class`` is a closed set;
* an outcome is terminal -- the database refuses UPDATE and DELETE;
* an observation must belong to a completed attempt;
* a plan must name the preregistration digest it was created under.

SQLite is used only as a file format. Nothing here depends on a server.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .identity import (
    candidate_id,
    canonical_json,
    metrics_digest,
    normalize_expression,
    normalize_settings,
    sha256_text,
)

OUTCOME_CLASSES = (
    "recognized",
    "effective_negative",
    "no_value",
    "operational_error",
    "pending",
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id  TEXT PRIMARY KEY NOT NULL,
    expression    TEXT NOT NULL CHECK (length(trim(expression)) > 0),
    settings      TEXT NOT NULL CHECK (json_valid(settings)),
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id       TEXT PRIMARY KEY NOT NULL,
    candidate_id  TEXT NOT NULL REFERENCES candidates(candidate_id),
    prereg_digest TEXT NOT NULL CHECK (length(prereg_digest) = 64),
    seed          INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id   TEXT PRIMARY KEY NOT NULL,
    plan_id      TEXT NOT NULL REFERENCES plans(plan_id),
    state        TEXT NOT NULL CHECK (state IN ('pending', 'completed')),
    started_at   TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY NOT NULL,
    attempt_id     TEXT NOT NULL REFERENCES attempts(attempt_id),
    metrics        TEXT NOT NULL CHECK (json_valid(metrics)),
    recorded_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id    TEXT PRIMARY KEY NOT NULL,
    attempt_id    TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
    outcome_class TEXT NOT NULL CHECK (outcome_class IN
        ('recognized', 'effective_negative', 'no_value', 'operational_error', 'pending')),
    rationale     TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    decided_at    TEXT NOT NULL
);

-- Outcomes are terminal. A re-run is a new attempt, not an edit of history.
CREATE TRIGGER IF NOT EXISTS trg_outcome_no_update
BEFORE UPDATE ON outcomes
BEGIN
    SELECT RAISE(ABORT, 'outcomes are terminal: record a new attempt instead');
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_no_delete
BEFORE DELETE ON outcomes
BEGIN
    SELECT RAISE(ABORT, 'outcomes are terminal: record a new attempt instead');
END;
"""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ledger:
    """Thin, explicit wrapper around a single SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    @classmethod
    def open(cls, path: str | Path) -> Ledger:
        path = Path(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path))

    @classmethod
    def in_memory(cls) -> Ledger:
        return cls(sqlite3.connect(":memory:"))

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- write path -------------------------------------------------------

    def register_candidate(self, expression: str, settings: Mapping[str, Any] | None = None) -> str:
        """Register a candidate; identical content is idempotent."""
        expr = normalize_expression(expression)
        normalized = normalize_settings(settings)
        cid = candidate_id(expr, normalized)
        self._conn.execute(
            "INSERT INTO candidates (candidate_id, expression, settings, registered_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(candidate_id) DO NOTHING",
            (cid, expr, canonical_json(normalized), utc_now()),
        )
        self._conn.commit()
        return cid

    def create_plan(self, cid: str, prereg_digest: str, seed: int) -> str:
        """Freeze the pair (candidate, preregistration) before any simulation.

        The plan ID is content-addressed over all three inputs, so re-planning
        the same pair is a no-op and changing the seed is visibly a new plan.
        """
        if not self._has("candidates", "candidate_id", cid):
            raise KeyError(f"unknown candidate: {cid}")
        plan_id = "PLAN-" + sha256_text(
            canonical_json({"candidate": cid, "prereg": prereg_digest, "seed": seed})
        )
        self._conn.execute(
            "INSERT INTO plans (plan_id, candidate_id, prereg_digest, seed, created_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(plan_id) DO NOTHING",
            (plan_id, cid, prereg_digest, seed, utc_now()),
        )
        self._conn.commit()
        return plan_id

    def start_attempt(self, plan_id: str) -> str:
        if not self._has("plans", "plan_id", plan_id):
            raise KeyError(f"unknown plan: {plan_id}")
        started = utc_now()
        attempt_id = "ATT-" + sha256_text(canonical_json({"plan": plan_id, "at": started}))
        self._conn.execute(
            "INSERT INTO attempts (attempt_id, plan_id, state, started_at)"
            " VALUES (?, ?, 'pending', ?)",
            (attempt_id, plan_id, started),
        )
        self._conn.commit()
        return attempt_id

    def complete_attempt(self, attempt_id: str, metrics: Mapping[str, Any]) -> str:
        """Attach a measurement to an attempt. Observation IDs are content-addressed."""
        cursor = self._conn.execute(
            "UPDATE attempts SET state = 'completed', completed_at = ?"
            " WHERE attempt_id = ? AND state = 'pending'",
            (utc_now(), attempt_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"attempt not pending or missing: {attempt_id}")
        observation_id = "OBS-" + sha256_text(
            canonical_json({"attempt": attempt_id, "metrics": metrics_digest(metrics)})
        )
        self._conn.execute(
            "INSERT INTO observations (observation_id, attempt_id, metrics, recorded_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(observation_id) DO NOTHING",
            (observation_id, attempt_id, canonical_json(metrics), utc_now()),
        )
        self._conn.commit()
        return observation_id

    def record_outcome(self, attempt_id: str, outcome_class: str, rationale: str) -> str:
        if outcome_class not in OUTCOME_CLASSES:
            raise ValueError(f"unknown outcome class: {outcome_class!r}")
        if not rationale.strip():
            raise ValueError("an outcome needs a rationale")
        outcome_id = "OUT-" + sha256_text(
            canonical_json({"attempt": attempt_id, "class": outcome_class})
        )
        self._conn.execute(
            "INSERT INTO outcomes (outcome_id, attempt_id, outcome_class, rationale, decided_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (outcome_id, attempt_id, outcome_class, rationale.strip(), utc_now()),
        )
        self._conn.commit()
        return outcome_id

    # -- read path --------------------------------------------------------

    def candidate(self, cid: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM candidates WHERE candidate_id = ?", (cid,)
        ).fetchone()
        return dict(row) if row else None

    def outcomes(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT c.candidate_id, c.expression, o.outcome_class,
                   o.rationale, ob.metrics
              FROM outcomes o
              JOIN attempts a ON a.attempt_id = o.attempt_id
              JOIN plans p ON p.plan_id = a.plan_id
              JOIN candidates c ON c.candidate_id = p.candidate_id
              LEFT JOIN observations ob ON ob.attempt_id = a.attempt_id
             ORDER BY c.expression
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def outcome_counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT outcome_class, COUNT(*) AS n FROM outcomes GROUP BY outcome_class"
        ).fetchall()
        return {row["outcome_class"]: row["n"] for row in rows}

    def plan_prereg_digest(self, plan_id: str) -> str:
        row = self._conn.execute(
            "SELECT prereg_digest FROM plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown plan: {plan_id}")
        return str(row["prereg_digest"])

    # -- helpers ----------------------------------------------------------

    def _has(self, table: str, key: str, value: str) -> bool:
        row = self._conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (value,)).fetchone()
        return row is not None
