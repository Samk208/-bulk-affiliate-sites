"""Fabricated-stat detection + substitution against per-niche stats.md library.

Uses Jaccard similarity on tokenized claim text. No LLM, no extra deps.
Threshold tiers (from stat-policy.md):
  >= 0.75  → substitute with vetted version + source citation
  0.5-0.75 → mark [needs-source] for QA review
  <  0.5   → mark [unverified] for QA review
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Match number-bearing claims: $X, X%, X percent, X billion/million/thousand/etc.,
# X years/days/weeks/months. Must be substantive (not just "5 minutes ago").
_NUMBER_RE = re.compile(
    r'(\$?\d[\d,]*\.?\d*\s*'
    r'(?:billion|trillion|million|thousand|percent|%|years?|days?|weeks?|months?))',
    re.IGNORECASE,
)

# Sentence splitter — simple but adequate for our HTML-stripped text.
_SENT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "this", "that", "these", "those", "it", "its", "by", "as", "but",
    "from", "into", "about", "than", "so", "if", "then",
}


SUBSTITUTE_THRESHOLD = 0.75
NEEDS_SOURCE_THRESHOLD = 0.50


@dataclass
class StatMatch:
    sentence: str
    library_entry: dict | None
    score: float           # 0.0 - 1.0 Jaccard similarity
    action: str            # "substitute" | "mark_needs_source" | "mark_unverified"


def find_number_bearing_sentences(text: str) -> list[str]:
    """Return list of sentences (stripped) that contain a number-bearing claim."""
    sentences = _SENT_RE.split(text)
    return [s.strip() for s in sentences if _NUMBER_RE.search(s)]


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def match_stat_to_library(sentence: str, library: list[dict]) -> StatMatch:
    """Find best library match for a sentence. Decide action by similarity tier."""
    if not library:
        return StatMatch(sentence, None, 0.0, "mark_unverified")

    sent_tokens = _tokenize(sentence)
    best_score = 0.0
    best_entry = None

    for entry in library:
        claim_text = f"{entry.get('claim', '')} {entry.get('value', '')}"
        claim_tokens = _tokenize(claim_text)
        score = _jaccard(sent_tokens, claim_tokens)
        if score > best_score:
            best_score = score
            best_entry = entry

    if best_score >= SUBSTITUTE_THRESHOLD:
        action = "substitute"
    elif best_score >= NEEDS_SOURCE_THRESHOLD:
        action = "mark_needs_source"
    else:
        action = "mark_unverified"

    return StatMatch(sentence, best_entry, best_score, action)
