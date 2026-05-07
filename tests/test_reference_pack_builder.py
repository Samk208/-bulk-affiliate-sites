"""Tests for the pure-function pieces of reference_pack_builder."""

from reference_pack_builder import should_accept_verification


def test_accepts_verified_with_exact_match():
    result = {"verified": True, "exact_match": True, "source_url": "x", "notes": ""}
    assert should_accept_verification(result) is True


def test_accepts_verified_without_exact_match():
    """Perplexity often verifies the substance via multiple sources without
    matching the wording. Don't waste those — accept verified=true regardless."""
    result = {"verified": True, "exact_match": False, "source_url": "x",
              "notes": "Multiple sources support 8-12 yrs; claim is 9-12."}
    assert should_accept_verification(result) is True


def test_rejects_unverified():
    result = {"verified": False, "exact_match": False, "notes": "no source"}
    assert should_accept_verification(result) is False


def test_rejects_unverified_even_if_exact_match_true():
    """Defensive — verified=false should never be accepted regardless of other fields."""
    result = {"verified": False, "exact_match": True, "notes": "weird"}
    assert should_accept_verification(result) is False


def test_rejects_missing_verified_key():
    result = {"notes": "no fields"}
    assert should_accept_verification(result) is False


def test_rejects_empty_dict():
    assert should_accept_verification({}) is False
