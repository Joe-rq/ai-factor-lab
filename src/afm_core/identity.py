"""Content-addressed identity: normalize first, then hash.

The same conceptual candidate entering the system through different paths must
collapse onto the same ledger row. Normalization is therefore part of identity,
not a formatting concern. This module is the single place that decides what
"the same candidate" means.

Design rule: an ID is derived from content, never assigned. Re-registering the
same content is a no-op; changing any byte of the expression or its settings
produces a different candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any

# Closed set of metrics the ledger understands. A metric that is absent is
# reported as "not measured" all the way down to the verdict -- never as zero.
METRIC_NAMES = ("sharpe", "fitness", "turnover", "returns", "mean_pnl")

DEFAULT_SETTINGS: dict[str, str] = {
    "instrument": "EQUITY",
    "language": "FASTEXPR",
    "neutralization": "INDUSTRY",
}

_WHITESPACE = re.compile(r"\s+")


def normalize_expression(expression: str) -> str:
    """Collapse surrounding and repeated whitespace; semantics are unchanged."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be a non-empty string")
    return _WHITESPACE.sub(" ", expression.strip())


def normalize_settings(settings: Mapping[str, Any] | None) -> dict[str, str]:
    """Fill defaults and normalize values so equivalent settings hash equally.

    Unknown keys are rejected: silently ignoring a setting is how two different
    experiments end up sharing one identity.
    """
    merged = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f"unknown setting: {key!r}")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"setting {key!r} must be a non-empty string")
        merged[key] = value.strip().upper()
    return merged


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, no NaN.

    ``allow_nan=False`` matters: NaN is not legal JSON, and a ledger that can
    only be read back by a permissive parser is not an auditable ledger.
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(expression: str, settings: Mapping[str, Any] | None = None) -> str:
    payload = {
        "expression": normalize_expression(expression),
        "settings": normalize_settings(settings),
    }
    return sha256_text(canonical_json(payload))


def candidate_id(
    expression: str, settings: Mapping[str, Any] | None = None, *, prefix: str = "CAND"
) -> str:
    """Content-addressed candidate ID.

    The prefix is a presentation choice; the hash is the identity. Keeping the
    prefix out of the digest means a fork can rename it without rewriting history.
    """
    return f"{prefix}-{content_hash(expression, settings)}"


def clean_metrics(metrics: Mapping[str, Any]) -> dict[str, float | None]:
    """Keep only finite numbers or explicit ``None``.

    ``None`` means "not measured" and survives normalization; NaN does not,
    because it cannot be written to a JSON column honestly.
    """
    clean: dict[str, float | None] = {}
    for key in sorted(metrics):
        value = metrics[key]
        if value is None:
            clean[key] = None
        elif isinstance(value, int | float) and math.isfinite(float(value)):
            clean[key] = float(value)
        else:
            raise ValueError(f"metric {key!r} is not a finite number: {value!r}")
    return clean


def metrics_digest(metrics: Mapping[str, Any]) -> str:
    """Digest of a measurement payload, used as an observation ID."""
    return sha256_text(canonical_json(clean_metrics(metrics)))
