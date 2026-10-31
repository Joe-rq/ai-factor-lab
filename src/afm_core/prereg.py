"""Preregistration: freeze the decision rule before seeing the result.

The point is not ceremony. A rule written after the fact will always fit the
data; a rule written before it can be wrong. This module makes the rule a
content-addressed object so a plan can name the exact rule it ran under.

Every gate must also name its **not-measured slot**. This is the failure mode
that quietly poisons research: a run that produced no usable measurement is
read as "the hypothesis failed", when in fact nothing was tested. Making the
slot mandatory means the decision table cannot silently omit it.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .identity import METRIC_NAMES, canonical_json, sha256_text

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}

GATE_KINDS = ("value", "direction")
DECISION_SLOTS = ("pass", "fail", "not_measured")


@dataclass(frozen=True)
class Gate:
    """One falsifiable condition, named and typed."""

    name: str
    metric: str
    op: str
    threshold: float
    kind: str = "value"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("gate name must be non-empty")
        if self.metric not in METRIC_NAMES:
            raise ValueError(f"unknown metric: {self.metric!r}")
        if self.op not in OPERATORS:
            raise ValueError(f"unknown operator: {self.op!r}")
        if self.kind not in GATE_KINDS:
            raise ValueError(f"unknown gate kind: {self.kind!r}")
        if not isinstance(self.threshold, int | float):
            raise ValueError(f"threshold must be numeric: {self.threshold!r}")

    def describe(self) -> str:
        return f"{self.metric} {self.op} {self.threshold:g}"


@dataclass(frozen=True)
class Preregistration:
    """A frozen decision rule."""

    hypothesis: str
    gates: tuple[Gate, ...]
    decisions: Mapping[str, str]
    invalid_slots: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.hypothesis.strip():
            raise ValueError("hypothesis must be non-empty")
        if not self.gates:
            raise ValueError("at least one gate is required")

        names = [gate.name for gate in self.gates]
        if len(names) != len(set(names)):
            raise ValueError("gate names must be unique")

        missing = [slot for slot in DECISION_SLOTS if not self.decisions.get(slot)]
        if missing:
            raise ValueError(f"decision table is missing slots: {missing}")

        required_slots = {f"{gate.name}:not_measured" for gate in self.gates}
        absent = sorted(required_slots.difference(self.invalid_slots))
        if absent:
            raise ValueError(
                "every gate needs an explicit not-measured slot; missing: " + ", ".join(absent)
            )

    def slot_for(self, gate_name: str) -> str:
        return f"{gate_name}:not_measured"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis,
            "gates": [
                {
                    "name": gate.name,
                    "metric": gate.metric,
                    "op": gate.op,
                    "threshold": gate.threshold,
                    "kind": gate.kind,
                }
                for gate in sorted(self.gates, key=lambda item: item.name)
            ],
            "decisions": dict(sorted(self.decisions.items())),
            "invalid_slots": sorted(self.invalid_slots),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Preregistration:
        return cls(
            hypothesis=str(data["hypothesis"]),
            gates=tuple(
                Gate(
                    name=str(item["name"]),
                    metric=str(item["metric"]),
                    op=str(item["op"]),
                    threshold=float(item["threshold"]),
                    kind=str(item.get("kind", "value")),
                )
                for item in data["gates"]
            ),
            decisions={str(key): str(value) for key, value in data["decisions"].items()},
            invalid_slots=tuple(str(slot) for slot in data.get("invalid_slots", ())),
        )

    def digest(self) -> str:
        """Content address of the frozen rule."""
        return sha256_text(canonical_json(self.to_dict()))
