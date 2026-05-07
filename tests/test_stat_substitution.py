"""Tests for fabricated-stat substitution against stats.md library."""

from stat_substitution import (
    find_number_bearing_sentences,
    find_citable_claim_sentences,
    looks_like_citable_claim,
    match_stat_to_library,
    StatMatch,
)


def test_find_number_bearing_sentences_simple():
    text = "The market was 8.4 billion dollars. Sales grew. Now it's 12 trillion."
    sents = find_number_bearing_sentences(text)
    assert len(sents) == 2
    assert "8.4 billion" in sents[0]
    assert "12 trillion" in sents[1]


def test_find_number_bearing_skips_non_numeric():
    text = "Dogs are great. Cats are fine."
    sents = find_number_bearing_sentences(text)
    assert sents == []


def test_find_number_bearing_catches_percent():
    text = "About 45% of dog owners report this. Many vets agree."
    sents = find_number_bearing_sentences(text)
    assert len(sents) == 1
    assert "45%" in sents[0]


def test_match_stat_high_similarity():
    library = [
        {"claim": "Korean cosmetics export volume reached", "value": "$8.4 billion",
         "year": 2023, "source": "KCS", "url": "https://x.com",
         "verified_at": "2026-05-06"}
    ]
    sent = "Korean cosmetics exports reached $8.4 billion in 2023."
    match = match_stat_to_library(sent, library)
    assert match.score >= 0.5  # at least medium
    assert match.action in ("substitute", "mark_needs_source")


def test_match_stat_low_similarity_marks_unverified():
    library = [
        {"claim": "Korean cosmetics export volume", "value": "$8.4 billion",
         "year": 2023, "source": "KCS", "url": "https://x.com",
         "verified_at": "2026-05-06"}
    ]
    sent = "Roughly 73% of dog owners use crates."
    match = match_stat_to_library(sent, library)
    assert match.score < 0.5
    assert match.action == "mark_unverified"


def test_match_stat_empty_library_marks_unverified():
    sent = "About 50% of users report this."
    match = match_stat_to_library(sent, [])
    assert match.action == "mark_unverified"


def test_match_stat_returns_best_entry():
    library = [
        {"claim": "Dog ownership in US households", "value": "65 million",
         "source": "AVMA", "year": 2024, "url": "x", "verified_at": "2026-05-06"},
        {"claim": "Korean cosmetics market", "value": "$8.4 billion",
         "source": "KCS", "year": 2023, "url": "x", "verified_at": "2026-05-06"},
    ]
    sent = "About 65 million dogs live in US households."
    match = match_stat_to_library(sent, library)
    assert match.library_entry["source"] == "AVMA"


# --- Containment-style matching: terse stat in verbose sentence ----------

def test_terse_stat_substitutes_in_verbose_natural_sentence():
    """A stat with ~10 tokens should substitute when its key tokens appear in
    a verbose 20-30 token article sentence. Jaccard fails this; containment
    against the smaller stat-token set should pass."""
    library = [
        {"claim": "average hours an adult dog sleeps per 24-hour period",
         "value": "12 to 14 hours",
         "source": "AKC", "year": 2024, "url": "x",
         "verified_at": "2026-05-06"}
    ]
    sent = ("An adult dog typically sleeps 12 to 14 hours per day "
            "according to recent veterinary research on canine sleep needs.")
    match = match_stat_to_library(sent, library)
    assert match.action == "substitute", (
        f"expected substitute, got {match.action} (score={match.score:.3f})"
    )


def test_off_topic_verbose_sentence_does_not_false_positive():
    """A verbose sentence on a different topic should not substitute even though
    the library entry is short."""
    library = [
        {"claim": "average hours an adult dog sleeps per 24-hour period",
         "value": "12 to 14 hours",
         "source": "AKC", "year": 2024, "url": "x",
         "verified_at": "2026-05-06"}
    ]
    sent = ("Roughly 68% of Bulldogs prefer raised head positions to reduce "
            "snoring symptoms according to fabricated journal data.")
    match = match_stat_to_library(sent, library)
    assert match.action != "substitute", (
        f"expected non-substitute, got {match.action} (score={match.score:.3f})"
    )


# --- Claim-shape filter (β-lite): only flag sentences that look like
#     attributable factual claims, not methodology / specs / recommendations. ---

def test_citable_pct_of_population():
    """X% of [population] is a clear citable claim."""
    s = "Studies show that 73 percent of dogs over age 7 show improved mobility."
    assert looks_like_citable_claim(s) is True


def test_citable_named_org():
    """Named authority + number = citable."""
    s = "According to the AKC, puppies need to go outside every 30 minutes."
    assert looks_like_citable_claim(s) is True


def test_citable_outcome_pct():
    """Quantified outcome ('reduces by X%') is citable."""
    s = "The right bedding reduces crate refusal by 61 percent overall."
    assert looks_like_citable_claim(s) is True


def test_skip_first_person_methodology():
    """First-person testing without citation = methodology, skip."""
    s = "I spent 16 weeks testing these crates with real dogs in real homes."
    assert looks_like_citable_claim(s) is False


def test_skip_in_my_testing():
    """'In my testing' phrasing = methodology, skip."""
    s = "In my testing with three rescue dogs over six months, irritability dropped 40%."
    assert looks_like_citable_claim(s) is False


def test_skip_plain_recommendation():
    """'Every X weeks' without citation = recommendation, skip."""
    s = "Bathe most healthy adult dogs every 4 to 6 weeks."
    assert looks_like_citable_claim(s) is False


def test_skip_product_spec():
    """Product dimensions / pricing = spec, skip."""
    s = "Big Barker offers 7 inches of orthopedic foam at $240 to $400."
    assert looks_like_citable_claim(s) is False


def test_skip_duration_observation():
    """'After X days' descriptive observation = skip."""
    s = "Most beds compress within 12 to 18 months of daily use."
    assert looks_like_citable_claim(s) is False


def test_keep_first_person_with_research_cite():
    """First-person 'in our study' with cite = still citable."""
    s = "In our study published in the Journal of Veterinary Behavior, 40% of dogs improved."
    assert looks_like_citable_claim(s) is True


def test_find_citable_claim_sentences_filters():
    """find_citable_claim_sentences should be strict subset of find_number_bearing."""
    text = (
        "I tested for 16 weeks with three dogs. "
        "Studies show 73 percent of dogs over age 7 have arthritis. "
        "Bathe every 4 to 6 weeks. "
        "The bed reduces pressure by 40 percent."
    )
    all_num = find_number_bearing_sentences(text)
    citable = find_citable_claim_sentences(text)
    assert len(all_num) == 4
    assert len(citable) == 2  # only the studies + reduces sentences
    assert all("Studies show" in s or "reduces" in s for s in citable)


def test_partial_topical_overlap_marks_needs_source():
    """Overlapping topic but different claim (article: mobility%; library: OA%)
    should land in mark_needs_source, not substitute."""
    library = [
        {"claim": "percentage of dogs over age 7 affected by osteoarthritis",
         "value": "approximately 80 percent",
         "source": "AAHA", "year": 2023, "url": "x",
         "verified_at": "2026-05-06"}
    ]
    sent = ("Veterinary studies show that 73 percent of dogs over age 7 "
            "show improved mobility when bedding matches their preferred sleep position.")
    match = match_stat_to_library(sent, library)
    # Should NOT substitute (different claim — mobility vs osteoarthritis)
    # but should NOT be silent (topically related, deserves human review)
    assert match.action in ("mark_needs_source", "mark_unverified")
