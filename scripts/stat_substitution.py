"""Fabricated-stat detection + substitution against per-niche stats.md library.

Uses containment-coefficient on tokenized claim text — score is the fraction
of library-claim tokens present in the article sentence. This rewards strong
topical overlap regardless of sentence verbosity (jaccard penalised long
sentences against terse claims; observed real-article max ~0.16).

Substitution requires both score >= threshold AND at least 3 overlapping tokens
(prevents 1-2 word stat entries from triggering on coincidental matches).

Threshold tiers:
  >= 0.6   → substitute with vetted version + source citation
  0.4-0.6  → mark [needs-source] for QA review
  <  0.4   → mark [unverified] for QA review
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


SUBSTITUTE_THRESHOLD = 0.60
NEEDS_SOURCE_THRESHOLD = 0.40
MIN_TOKEN_OVERLAP = 3  # absolute floor — prevents 1-2 word stat entries from false-positive


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


# ---- Claim-shape filter (β-lite) -----------------------------------------
# Number-bearing != citable claim. find_number_bearing_sentences over-flags
# methodology sentences ("I tested for 16 weeks"), product specs ("4-inch foam"),
# and recommendations ("every 4 to 6 weeks"). Only sentences that look like
# attributable factual claims should be marked [unverified] when no library
# match is found.

_FIRST_PERSON_VERB_RE = re.compile(
    r"\b(?:i|we)\s+(?:tested|spent|tracked|found|noticed|observed|trained|"
    r"fostered|adopted|own|owned|raised|measured|tried|see|"
    r"have\s+(?:tested|spent|seen|noticed|tracked|found|observed)|"
    r"'?ve\s+(?:tested|spent|seen|noticed|tracked|found|observed))\b"
    r"|\bin\s+(?:my|our)\s+(?:testing|experience|study|trial|observation|home)\b"
    r"|\bafter\s+(?:tracking|testing|trying|spending|monitoring)\b"
    r"|\bmy\s+(?:lab|dog|puppy|senior|rescue|foster|neighbor|client)\b",
    re.IGNORECASE,
)

_CITE_RE = re.compile(
    r"\b(?:stud(?:y|ies)|research(?:ers?)?|surveys?|data|reports?|evidence|"
    r"according\s+to|published\s+in|journals?\s+of?|peer[\s-]?reviewed|"
    r"clinical(?:\s+(?:study|trial|stud|trials))?|"
    r"akc|aaha|avma|aspca|fda|nih|cdc|aafp|nasc|"
    r"american\s+(?:kennel|veterinary|animal|college)|"
    r"veterinary\s+(?:medical|behaviorist|surgical|board|college|institute|behaviou?rist)|"
    r"university\s+of|institute\s+for|"
    r"approximately|estimated|behaviou?rists?|"
    r"shows?\s+that|finds?\s+that|indicates?\s+that|"
    r"per\s+\d{4}|in\s+\d{4}\s+(?:study|stud|research))\b",
    re.IGNORECASE,
)

_PCT_RE = re.compile(r"\d[\d,]*\.?\d*\s*%|\d[\d,]*\.?\d*\s*percent\b", re.IGNORECASE)

_POPULATION_RE = re.compile(
    r"\b(?:dogs?|puppies|owners?|breeds?|households?|americans?|"
    r"adults?|seniors?|veterinarians?|consumers?|pets?|cats?|"
    r"manufacturers?|companies)\b",
    re.IGNORECASE,
)

_OUTCOME_VERB_RE = re.compile(
    r"\b(?:reduces?|reduced|increases?|increased|cuts?|cut|improves?|improved|"
    r"prevents?|prevented|saves?|saved|lowers?|lowered|extends?|extended|"
    r"kills?|killed|drops?|dropped|slows?|slowed|raises?|raised|boosts?|boosted|"
    r"grows?|grew|shortens?|shortened|lengthens?|lengthened|decreases?|decreased|"
    r"rises?|rose|falls?|fell|spikes?|spiked|masks?|masked)\b",
    re.IGNORECASE,
)


def looks_like_citable_claim(sentence: str) -> bool:
    """True if sentence looks like an attributable factual claim worth flagging
    when no library match exists.

    Rules:
      - First-person methodology ("I tested for 16 weeks") → False unless
        accompanied by a citation marker ("in our study published in...").
      - Citation markers (study/AKC/AVMA/research/etc.) → True
      - Percentage + population descriptor (e.g. "73% of dogs") → True
      - Percentage + outcome verb (e.g. "reduces by 40%") → True
      - Otherwise (plain recommendations, product specs, durations) → False
    """
    has_pct = bool(_PCT_RE.search(sentence))
    has_pop = bool(_POPULATION_RE.search(sentence))
    has_cite = bool(_CITE_RE.search(sentence))
    has_outcome = bool(_OUTCOME_VERB_RE.search(sentence))
    has_claim_signal = (
        has_cite
        or (has_pct and has_pop)
        or (has_pct and has_outcome)
    )

    if _FIRST_PERSON_VERB_RE.search(sentence):
        # First-person — only flag if explicitly cited
        return has_cite
    return has_claim_signal


def find_citable_claim_sentences(text: str) -> list[str]:
    """Strict subset of find_number_bearing_sentences — only sentences that
    look like attributable factual claims."""
    return [s for s in find_number_bearing_sentences(text)
            if looks_like_citable_claim(s)]


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _containment(stat_tokens: set[str], sent_tokens: set[str]) -> tuple[float, int]:
    """Fraction of stat tokens present in the sentence. Returns (score, overlap_count)."""
    if not stat_tokens or not sent_tokens:
        return 0.0, 0
    overlap = len(stat_tokens & sent_tokens)
    return overlap / len(stat_tokens), overlap


def match_stat_to_library(sentence: str, library: list[dict]) -> StatMatch:
    """Find best library match for a sentence. Decide action by containment tier."""
    if not library:
        return StatMatch(sentence, None, 0.0, "mark_unverified")

    sent_tokens = _tokenize(sentence)
    best_score = 0.0
    best_overlap = 0
    best_entry = None

    for entry in library:
        claim_text = f"{entry.get('claim', '')} {entry.get('value', '')}"
        claim_tokens = _tokenize(claim_text)
        score, overlap = _containment(claim_tokens, sent_tokens)
        if score > best_score:
            best_score = score
            best_overlap = overlap
            best_entry = entry

    if best_score >= SUBSTITUTE_THRESHOLD and best_overlap >= MIN_TOKEN_OVERLAP:
        action = "substitute"
    elif best_score >= NEEDS_SOURCE_THRESHOLD:
        action = "mark_needs_source"
    else:
        action = "mark_unverified"

    return StatMatch(sentence, best_entry, best_score, action)
