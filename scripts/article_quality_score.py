"""Aggregated quality score for retrofit pilot.

Total: 0-10, with 7 sub-scores. Used by article_qa.py and retrofit_pilot.py
to compare baseline vs post-enhancement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from visual_elements import count_visual_elements


@dataclass
class QualityScore:
    content_quality: float = 0.0      # 0-3
    visual_richness: float = 0.0      # 0-2
    entity_coverage: float = 0.0      # 0-2
    voice_authenticity: float = 0.0   # 0-1
    factual_grounding: float = 0.0    # 0-1
    schema_correctness: float = 0.0   # 0-0.5
    geo_optimization: float = 0.0     # 0-0.5
    flags: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(
            self.content_quality + self.visual_richness + self.entity_coverage
            + self.voice_authenticity + self.factual_grounding
            + self.schema_correctness + self.geo_optimization,
            2,
        )


_DR_NAME_RE = re.compile(r'\bDr\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?')
_NAME_DEGREE_RE = re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+,\s+(?:MD|PhD|DVM|DO|LMT|RDN)\b')

_ATTRIBUTION_PHRASES = (
    "according to", "studies show", "research shows", "data shows",
    "research indicates", "experts recommend", "evidence suggests",
)

# Borrow banned words from config — fall back to small list if config is unavailable
try:
    from config import BANNED_WORDS as _BANNED_WORDS
except Exception:
    _BANNED_WORDS = [
        "delve", "tapestry", "crucial", "leverage", "utilize",
        "cutting-edge", "game-changer", "revolutionize", "seamless", "robust",
        "uncover", "realm", "symphony", "bustling", "innovative",
        "furthermore", "moreover",
    ]


def score_article(html: str, niche: str, slug: str,
                  serp_brief: dict | None) -> QualityScore:
    """Compute aggregated 0-10 quality score with sub-scores."""
    s = QualityScore()
    counts = count_visual_elements(html)

    s.content_quality = _score_content_quality(html, counts, serp_brief, s)
    s.visual_richness = _score_visual_richness(counts)
    s.entity_coverage = _score_entity_coverage(html, niche, serp_brief, s)
    s.voice_authenticity = _score_voice_authenticity(html, niche, s)
    s.factual_grounding = _score_factual_grounding(html, s)
    s.schema_correctness = _score_schema(counts, s)
    s.geo_optimization = _score_geo(html, counts)

    return s


def _score_content_quality(html, counts, brief, s) -> float:
    score = 1.0
    if counts.h2_count >= 5:
        score += 1.0
    elif counts.h2_count >= 3:
        score += 0.5
    if counts.h3_count >= 5:
        score += 0.5
    if brief and brief.get("min_word_count") and brief.get("max_word_count"):
        if brief["min_word_count"] <= counts.word_count <= brief["max_word_count"]:
            score += 0.5
        else:
            s.flags.append(
                f"word_count {counts.word_count} outside "
                f"[{brief['min_word_count']},{brief['max_word_count']}]"
            )
    return min(3.0, score)


def _score_visual_richness(counts) -> float:
    score = 0.0
    if counts.callouts >= 3:
        score += 0.8
    elif counts.callouts >= 2:
        score += 0.5
    elif counts.callouts >= 1:
        score += 0.2
    if counts.tables >= 1:
        score += 0.4
    if counts.blockquotes >= 1:
        score += 0.4
    if counts.quick_answer_present:
        score += 0.4
    return min(2.0, score)


def _score_entity_coverage(html, niche, brief, s) -> float:
    """Score 0-2 based on coverage of common_h2_topics from SERP brief."""
    if not brief:
        return 1.0  # neutral when no brief
    common_topics = brief.get("common_h2_topics", []) or []
    if not common_topics:
        return 1.0
    article_text = re.sub(r'<[^>]+>', ' ', html).lower()
    covered = sum(1 for t in common_topics if t.lower() in article_text)
    coverage_ratio = covered / len(common_topics)
    if coverage_ratio < 0.5:
        s.flags.append(f"entity_coverage {coverage_ratio:.0%} of common topics")
    return min(2.0, coverage_ratio * 2.0)


def _score_voice_authenticity(html, niche, s) -> float:
    plain = re.sub(r'<[^>]+>', ' ', html).lower()
    banned_hits = sum(1 for w in _BANNED_WORDS if w in plain)
    if banned_hits > 5:
        s.flags.append(f"banned_words: {banned_hits} hits")
        return 0.3
    if banned_hits > 2:
        return 0.6
    return 1.0


def _score_factual_grounding(html, s) -> float:
    score = 1.0
    unverified = html.count("[unverified]")
    needs_source = html.count("[needs-source]")
    if unverified:
        s.flags.append(f"[unverified] markers: {unverified}")
        score -= min(0.5, unverified * 0.1)
    if needs_source:
        s.flags.append(f"[needs-source] markers: {needs_source}")
        score -= min(0.3, needs_source * 0.05)
    dr_names = _DR_NAME_RE.findall(html)
    name_degrees = _NAME_DEGREE_RE.findall(html)
    if dr_names or name_degrees:
        s.flags.append(
            f"specific_named_persons: {len(dr_names)+len(name_degrees)} "
            f"(verify in stats/stories)"
        )
        score -= 0.2
    return max(0.0, score)


def _score_schema(counts, s) -> float:
    score = 0.0
    if "Article" in counts.schema_types:
        score += 0.25
    if "FAQPage" in counts.schema_types:
        score += 0.15
    if "BreadcrumbList" in counts.schema_types:
        score += 0.10
    if not counts.schema_types:
        s.flags.append("no JSON-LD schema")
    return min(0.5, score)


def _score_geo(html, counts) -> float:
    score = 0.0
    if counts.quick_answer_present:
        score += 0.2
    plain = re.sub(r'<[^>]+>', ' ', html).lower()
    if any(p in plain for p in _ATTRIBUTION_PHRASES):
        score += 0.15
    h3_questions = len(re.findall(
        r'<h3[^>]*>\s*(?:How|What|Why|Where|When|Which|Should|Can|Do|Does)',
        html, re.IGNORECASE,
    ))
    if h3_questions >= 3:
        score += 0.15
    elif h3_questions >= 1:
        score += 0.05
    return min(0.5, score)
