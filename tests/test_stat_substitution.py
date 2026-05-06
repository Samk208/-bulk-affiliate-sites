"""Tests for fabricated-stat substitution against stats.md library."""

from stat_substitution import (
    find_number_bearing_sentences,
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
