from __future__ import annotations

import pytest

from afm_core.identity import (
    candidate_id,
    clean_metrics,
    content_hash,
    normalize_expression,
    normalize_settings,
)


def test_whitespace_is_not_identity() -> None:
    assert normalize_expression("  rank( f_00 )\n+ f_01 ") == "rank( f_00 ) + f_01"
    assert content_hash("rank(f_00) + f_01") == content_hash("  rank(f_00)  +   f_01  ")


def test_settings_order_does_not_change_identity() -> None:
    first = content_hash("rank(f_00)", {"language": "fastexpr", "instrument": "equity"})
    second = content_hash("rank(f_00)", {"instrument": "EQUITY", "language": "FASTEXPR"})
    assert first == second


def test_defaults_are_part_of_identity() -> None:
    assert content_hash("rank(f_00)", {}) == content_hash(
        "rank(f_00)",
        {"instrument": "EQUITY", "language": "FASTEXPR", "neutralization": "INDUSTRY"},
    )


def test_unknown_setting_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown setting"):
        normalize_settings({"universe": "TOP3000"})


def test_different_content_is_a_different_candidate() -> None:
    assert candidate_id("rank(f_00)") != candidate_id("rank(f_01)")
    assert candidate_id("rank(f_00)").startswith("CAND-")
    assert len(candidate_id("rank(f_00)")) == len("CAND-") + 64


def test_prefix_is_presentation_only() -> None:
    left = candidate_id("rank(f_00)", prefix="CAND")
    right = candidate_id("rank(f_00)", prefix="ALT")
    assert left.split("-", 1)[1] == right.split("-", 1)[1]


def test_metrics_reject_non_finite_values() -> None:
    with pytest.raises(ValueError, match="not a finite number"):
        clean_metrics({"sharpe": float("nan")})
    with pytest.raises(ValueError, match="not a finite number"):
        clean_metrics({"sharpe": "high"})


def test_metrics_keep_explicit_none() -> None:
    assert clean_metrics({"sharpe": None, "turnover": 0.1}) == {
        "sharpe": None,
        "turnover": 0.1,
    }
