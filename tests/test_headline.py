from __future__ import annotations

import pytest

from cept.core import HEADLINE_HARD_CAP_WORDS, HEADLINE_SOFT_CAP_WORDS, _validate_headline


def test_validate_headline_passes_three_word_phrase() -> None:
    cleaned, warning = _validate_headline("audit research README")
    assert cleaned == "audit research README"
    assert warning is None


def test_validate_headline_passes_at_soft_cap() -> None:
    headline = " ".join(["w"] * HEADLINE_SOFT_CAP_WORDS)
    cleaned, warning = _validate_headline(headline)
    assert cleaned == headline
    assert warning is None


def test_validate_headline_warns_above_soft_cap() -> None:
    cleaned, warning = _validate_headline("debug oauth callback loop now")
    assert cleaned == "debug oauth callback loop now"
    assert warning is not None
    assert "5 words" in warning


def test_validate_headline_truncates_above_hard_cap() -> None:
    headline = "one two three four five six seven eight"
    cleaned, warning = _validate_headline(headline)
    expected = " ".join(headline.split()[:HEADLINE_HARD_CAP_WORDS]) + "…"
    assert cleaned == expected
    assert warning is not None
    assert "truncated" in warning


def test_validate_headline_strips_whitespace() -> None:
    cleaned, _ = _validate_headline("   audit research README   ")
    assert cleaned == "audit research README"


def test_validate_headline_collapses_internal_whitespace_for_word_count() -> None:
    cleaned, warning = _validate_headline("audit\t  research\n  README")
    # str.split() collapses runs of whitespace
    assert len(cleaned.split()) == 3
    assert warning is None


def test_validate_headline_rejects_empty() -> None:
    with pytest.raises(ValueError, match="headline is required"):
        _validate_headline("")


def test_validate_headline_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="headline is required"):
        _validate_headline("   \n\t  ")


def test_validate_headline_rejects_none_via_empty_str_path() -> None:
    # The wire surface forces str — if the caller bypasses it and sends None
    # we still want a clean ValueError, not an AttributeError.
    with pytest.raises(ValueError):
        _validate_headline(None)  # type: ignore[arg-type]


def test_validate_headline_single_word_is_fine() -> None:
    cleaned, warning = _validate_headline("debug")
    assert cleaned == "debug"
    assert warning is None
