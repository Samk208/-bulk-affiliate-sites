"""Count visual elements + words in article HTML.

Used by:
  - article_enhancer.py: regression check (post counts must be >= baseline)
  - article_qa.py: visual richness scoring
  - regression_test.py: before/after diff
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Callout div: any <div> with style attribute matching our callout pattern
# (background + border-left, which all SITE_STYLES callouts use).
_CALLOUT_RE = re.compile(
    r'<div[^>]*style="[^"]*background\s*:\s*#[0-9a-fA-F]{3,6}[^"]*'
    r'border-left\s*:\s*\d+px\s+solid[^"]*"',
    re.IGNORECASE,
)
_TABLE_RE = re.compile(r'<table[^>]*>', re.IGNORECASE)
_BLOCKQUOTE_RE = re.compile(r'<blockquote[^>]*>', re.IGNORECASE)
_IMG_RE = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
_H2_RE = re.compile(r'<h2[^>]*>', re.IGNORECASE)
_H3_RE = re.compile(r'<h3[^>]*>', re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')

# Quick Answer box uses purple tones from SITE_STYLES.quick_answer
# Match either the border color (#9c27b0) or background (#f3e5f5)
_QUICK_ANSWER_RE = re.compile(
    r'<div[^>]*(?:#9c27b0|#f3e5f5)[^>]*>',
    re.IGNORECASE,
)

# Schema types found in JSON-LD scripts
_JSONLD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_SCHEMA_TYPE_RE = re.compile(r'"@type"\s*:\s*"([^"]+)"')


@dataclass
class ElementCounts:
    callouts: int = 0
    tables: int = 0
    blockquotes: int = 0
    images: int = 0
    quick_answer_present: bool = False
    schema_types: list[str] = field(default_factory=list)
    h2_count: int = 0
    h3_count: int = 0
    word_count: int = 0


def count_visual_elements(html: str) -> ElementCounts:
    """Count visual elements in article HTML.

    All counts are non-decreasing across enhancement (enforced by
    article_enhancer.enhance_with_regression_guard).
    """
    if not html:
        return ElementCounts()
    counts = ElementCounts()
    counts.callouts = len(_CALLOUT_RE.findall(html))
    counts.tables = len(_TABLE_RE.findall(html))
    counts.blockquotes = len(_BLOCKQUOTE_RE.findall(html))
    counts.images = len(_IMG_RE.findall(html))
    counts.h2_count = len(_H2_RE.findall(html))
    counts.h3_count = len(_H3_RE.findall(html))
    counts.quick_answer_present = bool(_QUICK_ANSWER_RE.search(html))

    schema_types: list[str] = []
    for m in _JSONLD_RE.finditer(html):
        for tm in _SCHEMA_TYPE_RE.finditer(m.group(1)):
            t = tm.group(1)
            if t not in schema_types:
                schema_types.append(t)
    counts.schema_types = schema_types

    plain = _TAG_RE.sub(" ", html)
    counts.word_count = len(plain.split())
    return counts


def visual_regressions(before: ElementCounts, after: ElementCounts) -> list[str]:
    """Return list of regressions. Empty list = OK to proceed."""
    issues: list[str] = []
    if after.callouts < before.callouts:
        issues.append(f"callouts: {before.callouts} -> {after.callouts}")
    if after.tables < before.tables:
        issues.append(f"tables: {before.tables} -> {after.tables}")
    if after.blockquotes < before.blockquotes:
        issues.append(f"blockquotes: {before.blockquotes} -> {after.blockquotes}")
    if after.images < before.images:
        issues.append(f"images: {before.images} -> {after.images}")
    if before.quick_answer_present and not after.quick_answer_present:
        issues.append("quick_answer dropped")
    for st in before.schema_types:
        if st not in after.schema_types:
            issues.append(f"schema {st} dropped")
    return issues
