"""Tests for SERP brief schema validator + builder."""

import pytest

from serp_brief import (
    validate_brief,
    BriefValidationError,
    build_brief_from_data,
    get_word_count_target,
    GLOBAL_FLOOR,
    GLOBAL_CEILING,
)


def _minimal_valid_brief():
    return {
        "query": "x", "intent": "informational", "intent_source": "perplexity",
        "ai_overview_present": False, "ai_overview_citations": [],
        "featured_snippet_url": None, "paa_questions": [], "related_searches": [],
        "top_results": [], "median_word_count": 1500, "target_word_count": 1650,
        "min_word_count": 1402, "max_word_count": 1980,
        "common_h2_topics": [], "missing_h2_topics": [],
        "format_signature": "guide", "do_not_copy": [],
        "fetched_at": "2026-05-06T12:00:00Z",
    }


def test_minimal_valid_brief_passes():
    validate_brief(_minimal_valid_brief())


def test_brief_with_top_result_passes():
    brief = _minimal_valid_brief()
    brief["top_results"] = [{
        "rank": 1, "url": "https://x.com", "domain": "x.com",
        "title": "Title", "h1": "H1", "h2_tree": ["a"], "h3_tree": [["b"]],
        "word_count": 2000, "schema_types": ["Article"],
        "internal_links": 10, "external_links": 2,
    }]
    validate_brief(brief)


def test_brief_missing_required_field_fails():
    with pytest.raises(BriefValidationError, match="missing required field"):
        validate_brief({"query": "x"})


def test_brief_with_negative_word_count_fails():
    brief = _minimal_valid_brief()
    brief["target_word_count"] = -100
    with pytest.raises(BriefValidationError, match="must be positive"):
        validate_brief(brief)


def test_brief_with_min_greater_than_max_fails():
    brief = _minimal_valid_brief()
    brief["min_word_count"] = 5000
    brief["max_word_count"] = 3000
    with pytest.raises(BriefValidationError, match="min_word_count.*max_word_count"):
        validate_brief(brief)


def test_brief_top_result_missing_field_fails():
    brief = _minimal_valid_brief()
    brief["top_results"] = [{"rank": 1, "url": "x"}]  # missing many fields
    with pytest.raises(BriefValidationError, match="missing field"):
        validate_brief(brief)


def test_build_brief_basic():
    serp_data = {
        "organic": [
            {"position": 1, "url": "https://a.com", "title": "A", "snippet": "..."},
        ],
        "paa_questions": ["q1"],
        "serp_features": ["people_also_ask"],
    }
    page_contents = [
        {"h1": "A", "h2_tree": ["intro", "options", "verdict"],
         "h3_tree": [], "word_count": 2000, "schema_types": ["Article"],
         "internal_links": 10, "external_links": 2}
    ]
    brief = build_brief_from_data(
        query="x", intent="informational", intent_source="perplexity",
        serp_data=serp_data, page_contents=page_contents,
        is_ymyl=False,
    )
    validate_brief(brief)
    assert brief["target_word_count"] == int(2000 * 1.10)
    assert brief["query"] == "x"
    assert brief["top_results"][0]["word_count"] == 2000


def test_build_brief_ymyl_uses_120_multiplier():
    serp_data = {
        "organic": [{"position": 1, "url": "https://a.com",
                     "title": "A", "snippet": "..."}],
        "paa_questions": [], "serp_features": [],
    }
    page_contents = [
        {"h1": "A", "h2_tree": ["a"], "h3_tree": [], "word_count": 2000,
         "schema_types": [], "internal_links": 0, "external_links": 0}
    ]
    brief = build_brief_from_data(
        query="x", intent="informational", intent_source="perplexity",
        serp_data=serp_data, page_contents=page_contents,
        is_ymyl=True,
    )
    assert brief["target_word_count"] == int(2000 * 1.20)


def test_build_brief_clamps_to_floor():
    """Tiny SERP word counts must clamp to floor."""
    serp_data = {"organic": [], "paa_questions": [], "serp_features": []}
    page_contents = []
    brief = build_brief_from_data(
        query="x", intent="informational", intent_source="default",
        serp_data=serp_data, page_contents=page_contents, is_ymyl=False,
    )
    assert brief["target_word_count"] >= GLOBAL_FLOOR


def test_build_brief_clamps_to_ceiling():
    serp_data = {
        "organic": [{"position": 1, "url": "https://a.com",
                     "title": "A", "snippet": "..."}],
        "paa_questions": [], "serp_features": [],
    }
    page_contents = [{
        "h1": "A", "h2_tree": [], "h3_tree": [], "word_count": 6000,  # huge
        "schema_types": [], "internal_links": 0, "external_links": 0,
    }]
    brief = build_brief_from_data(
        query="x", intent="informational", intent_source="default",
        serp_data=serp_data, page_contents=page_contents, is_ymyl=False,
    )
    assert brief["target_word_count"] <= GLOBAL_CEILING


def test_build_brief_detects_ai_overview():
    serp_data = {
        "organic": [{"position": 1, "url": "https://a.com",
                     "title": "A", "snippet": "..."}],
        "paa_questions": [],
        "serp_features": ["ai_overview"],
    }
    page_contents = [{
        "h1": "A", "h2_tree": [], "h3_tree": [], "word_count": 1500,
        "schema_types": [], "internal_links": 0, "external_links": 0,
    }]
    brief = build_brief_from_data(
        query="x", intent="informational", intent_source="default",
        serp_data=serp_data, page_contents=page_contents, is_ymyl=False,
    )
    assert brief["ai_overview_present"] is True


def test_build_brief_detects_common_h2():
    """An H2 topic appearing in 3+ of 5 results becomes a common topic."""
    serp_data = {
        "organic": [
            {"position": i, "url": f"https://{i}.com",
             "title": f"R{i}", "snippet": ""} for i in range(1, 6)
        ],
        "paa_questions": [], "serp_features": [],
    }
    # All 5 mention "ingredients"
    page_contents = [
        {"h1": "R1", "h2_tree": ["ingredients", "routine"],
         "h3_tree": [], "word_count": 1500, "schema_types": [],
         "internal_links": 0, "external_links": 0},
        {"h1": "R2", "h2_tree": ["ingredients"],
         "h3_tree": [], "word_count": 1500, "schema_types": [],
         "internal_links": 0, "external_links": 0},
        {"h1": "R3", "h2_tree": ["ingredients", "skin types"],
         "h3_tree": [], "word_count": 1500, "schema_types": [],
         "internal_links": 0, "external_links": 0},
        {"h1": "R4", "h2_tree": ["overview"],
         "h3_tree": [], "word_count": 1500, "schema_types": [],
         "internal_links": 0, "external_links": 0},
        {"h1": "R5", "h2_tree": ["overview"],
         "h3_tree": [], "word_count": 1500, "schema_types": [],
         "internal_links": 0, "external_links": 0},
    ]
    brief = build_brief_from_data(
        query="x", intent="informational", intent_source="default",
        serp_data=serp_data, page_contents=page_contents, is_ymyl=False,
    )
    assert "ingredients" in brief["common_h2_topics"]


def test_get_word_count_target_with_brief():
    brief = _minimal_valid_brief()
    target, mn, mx = get_word_count_target("dog-comfort", brief)
    assert target == 1650
    assert mn <= target <= mx


def test_get_word_count_target_without_brief_uses_niche_default():
    target, mn, mx = get_word_count_target("dog-comfort", None)
    assert target == 1800  # niche default
    assert mn >= GLOBAL_FLOOR
    assert mx <= GLOBAL_CEILING


def test_get_word_count_target_unknown_niche_falls_back():
    target, mn, mx = get_word_count_target("not-a-real-niche", None)
    assert mn >= GLOBAL_FLOOR
    assert mx <= GLOBAL_CEILING
