"""A deterministic synthetic platform.

This is the seam that makes the repository runnable without a real data
provider. It is not a pretend number generator: there is a ground truth, a
tiny expression language, and a simulation that computes PnL from positions
taken before the return is realized.

The world
---------
30 fields, each an AR(1) process with unit stationary variance and 0.5
persistence. Future returns are driven by two of them::

    ret[t+1] = 0.003 * (f_00[t] - 0.75 * f_01[t]) + noise

A third field is the **negative control**: it is made orthogonal to realized
future returns in-sample, so a linear expression over it should fail the value
gates. A constant field is included to exercise zero-variance handling.

Expression language
-------------------
Deliberately small::

    expr := term (('+' | '-') term)*
    term := ['+'] ['-'] ['rank('] field [')']

``rank(X)`` is a rolling percentile over a 60-day window, mapped to [-1, 1].
Raw ``X`` uses the standardized field value directly. Anything else is
rejected, loudly, as an operational error.

Simulation
----------
Positions are taken from the signal at ``t`` and the return realized from
``t`` to ``t+1`` is applied. There is no lookahead in the position, and the
first 60 days are warm-up only.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from statistics import fmean

__all__ = [
    "SyntheticConfig",
    "SyntheticPlatform",
    "SyntheticResult",
    "parse_expression",
]

_FIELD_RE = re.compile(r"f_\d{2}")
_TERM_RE = re.compile(
    r"\s*(?P<sign>[+-]?)\s*(?:(?P<rank>rank)\s*\(\s*(?P<ranked>f_\d{2})\s*\)"
    r"|(?P<raw>f_\d{2}))\s*"
)


@dataclass(frozen=True)
class SyntheticConfig:
    days: int = 1000
    field_count: int = 30
    seed: int = 20261031
    noise_sigma: float = 0.010
    signal_scale: float = 0.003
    position_scale: float = 1.0
    rank_window: int = 60
    persistence: float = 0.5
    min_observations: int = 30


@dataclass(frozen=True)
class SyntheticResult:
    metrics: dict[str, float | None]
    expression: str
    observations: int

    def as_dict(self) -> dict[str, float | None]:
        return dict(self.metrics)


def parse_expression(expression: str) -> list[tuple[float, str, bool]]:
    """Parse ``rank(f_00) - f_01`` into ``[(+1, 'f_00', True), (-1, 'f_01', False)]``.

    Raises ``ValueError`` on anything outside the language. A parser that
    guesses is worse than a parser that refuses.
    """
    text = expression.strip()
    if not text:
        raise ValueError("empty expression")

    terms: list[tuple[float, str, bool]] = []
    position = 0
    first = True
    while position < len(text):
        match = _TERM_RE.match(text, position)
        if match is None:
            raise ValueError(f"cannot parse expression at offset {position}: {text!r}")
        sign = match.group("sign")
        if not first and not sign:
            raise ValueError("terms must be joined by '+' or '-'")
        weight = -1.0 if sign == "-" else 1.0
        if match.group("ranked"):
            terms.append((weight, match.group("ranked"), True))
        else:
            terms.append((weight, match.group("raw"), False))
        position = match.end()
        first = False

    if not terms:
        raise ValueError("expression has no terms")
    return terms


class SyntheticPlatform:
    """Deterministic world plus a simulator over a tiny expression language."""

    def __init__(self, config: SyntheticConfig | None = None) -> None:
        self.config = config or SyntheticConfig()
        self._fields = self._make_fields()
        self._returns = self._make_returns()

    # -- world construction ------------------------------------------------

    def field_names(self) -> tuple[str, ...]:
        return tuple(self._fields)

    @property
    def control_expression(self) -> str:
        """A candidate that must not pass: no linear edge by construction."""
        return "rank(f_29)"

    @property
    def known_positive(self) -> str:
        """A candidate the world is built to support."""
        return "rank(f_00)"

    def _make_fields(self) -> dict[str, list[float]]:
        rng = random.Random(self.config.seed)
        phi = self.config.persistence
        innovation = math.sqrt(1.0 - phi * phi)
        fields: dict[str, list[float]] = {}

        for index in range(self.config.field_count):
            name = f"f_{index:02d}"
            if index == self.config.field_count - 2:
                fields[name] = [1.0] * self.config.days
                continue
            values = [0.0] * self.config.days
            values[0] = rng.gauss(0.0, 1.0)
            for day in range(1, self.config.days):
                values[day] = phi * values[day - 1] + rng.gauss(0.0, innovation)
            fields[name] = values

        # The last field is the negative control. It is generated after returns
        # so it can be residualized against them (see `_orthogonalize_control`).
        fields[f"f_{self.config.field_count - 1:02d}"] = [0.0] * self.config.days
        return fields

    def _make_returns(self) -> list[float]:
        rng = random.Random(self.config.seed + 1)
        days = self.config.days
        f00 = self._fields["f_00"]
        f01 = self._fields["f_01"]
        returns = [0.0] * days
        for day in range(days - 1):
            signal = self.config.signal_scale * (f00[day] - 0.75 * f01[day])
            returns[day + 1] = signal + rng.gauss(0.0, self.config.noise_sigma)
        control_name = f"f_{self.config.field_count - 1:02d}"
        control = self._fields[control_name]
        for day in range(days):
            control[day] = rng.gauss(0.0, 1.0)
        self._orthogonalize_control(control, returns)
        return returns

    def _orthogonalize_control(self, control: list[float], returns: list[float]) -> None:
        """Remove the in-sample projection of control on next-day returns."""
        xs = control[:-1]
        ys = returns[1:]
        mean_x = fmean(xs)
        mean_y = fmean(ys)
        covariance = fmean((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
        variance = fmean((x - mean_x) ** 2 for x in xs)
        beta = covariance / variance if variance > 0 else 0.0
        for day in range(len(control) - 1):
            control[day] = control[day] - beta * (returns[day + 1] - mean_y)
        control[-1] = 0.0

    # -- simulation --------------------------------------------------------

    def simulate(self, expression: str) -> SyntheticResult:
        terms = parse_expression(expression)
        unknown = sorted({name for _, name, _ in terms if name not in self._fields})
        if unknown:
            raise ValueError(f"unknown fields: {', '.join(unknown)}")

        window = self.config.rank_window
        components: list[list[float]] = []
        for weight, name, use_rank in terms:
            values = self._fields[name]
            transformed = self._rolling_rank(values, window) if use_rank else list(values)
            components.append([weight * value for value in transformed])

        position: list[float] = [0.0] * self.config.days
        for day in range(window - 1, self.config.days):
            raw = sum(component[day] for component in components)
            position[day] = math.tanh(raw / self.config.position_scale)

        start = window - 1
        pnl = [position[day] * self._returns[day + 1] for day in range(start, self.config.days - 1)]
        if len(pnl) < self.config.min_observations:
            return SyntheticResult(
                expression=expression,
                observations=len(pnl),
                metrics={
                    name: None for name in ("sharpe", "fitness", "turnover", "returns", "mean_pnl")
                },
            )

        mean_pnl = fmean(pnl)
        variance = fmean((value - mean_pnl) ** 2 for value in pnl)
        std = math.sqrt(variance)

        steps = [
            abs(position[day] - position[day - 1]) for day in range(start + 1, self.config.days)
        ]
        turnover = fmean(steps) if steps else None

        if std == 0:
            # A zero-variance PnL series is a degenerate measurement, not a
            # negative result. Mark the statistics as not measured; turnover
            # itself is still a real observation.
            return SyntheticResult(
                expression=expression,
                observations=len(pnl),
                metrics={
                    "sharpe": None,
                    "fitness": None,
                    "turnover": turnover,
                    "returns": None,
                    "mean_pnl": None,
                },
            )

        annual_return = mean_pnl * 252.0
        sharpe = mean_pnl / std * math.sqrt(252.0)
        if turnover is None:
            fitness = None
        else:
            fitness = sharpe * math.sqrt(abs(annual_return) / max(turnover, 0.125))

        return SyntheticResult(
            expression=expression,
            observations=len(pnl),
            metrics={
                "sharpe": sharpe,
                "fitness": fitness,
                "turnover": turnover,
                "returns": annual_return,
                "mean_pnl": mean_pnl,
            },
        )

    def _rolling_rank(self, values: list[float], window: int) -> list[float]:
        """Rolling percentile in [-1, 1]; warm-up positions stay at zero."""
        out = [0.0] * len(values)
        for index in range(window - 1, len(values)):
            window_values = values[index - window + 1 : index + 1]
            current = values[index]
            below = sum(1 for value in window_values if value < current)
            equal = sum(1 for value in window_values if value == current)
            fraction = (below + 0.5 * (equal - 1)) / max(window - 1, 1)
            out[index] = 2.0 * fraction - 1.0
        return out
