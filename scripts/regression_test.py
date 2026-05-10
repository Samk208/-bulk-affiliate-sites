"""Before/after article diff. Used by retrofit_pilot.py to enforce
the hard regression rule: visual element counts can only go up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from visual_elements import count_visual_elements


@dataclass
class ArticleDiff:
    callout_delta: int = 0
    table_delta: int = 0
    blockquote_delta: int = 0
    image_delta: int = 0
    word_count_delta: int = 0
    quick_answer_lost: bool = False
    schemas_lost: list[str] = field(default_factory=list)
    regressed: bool = False
    regressions: list[str] = field(default_factory=list)


def diff_articles(before_html: str, after_html: str) -> ArticleDiff:
    """Compute element-count deltas. regressed=True if any count decreased."""
    b = count_visual_elements(before_html)
    a = count_visual_elements(after_html)
    d = ArticleDiff()
    d.callout_delta = a.callouts - b.callouts
    d.table_delta = a.tables - b.tables
    d.blockquote_delta = a.blockquotes - b.blockquotes
    d.image_delta = a.images - b.images
    d.word_count_delta = a.word_count - b.word_count
    d.quick_answer_lost = bool(b.quick_answer_present and not a.quick_answer_present)
    for s in b.schema_types:
        if s not in a.schema_types:
            d.schemas_lost.append(s)

    if d.callout_delta < 0:
        d.regressions.append(f"callouts: -{abs(d.callout_delta)}")
    if d.table_delta < 0:
        d.regressions.append(f"tables: -{abs(d.table_delta)}")
    if d.blockquote_delta < 0:
        d.regressions.append(f"blockquotes: -{abs(d.blockquote_delta)}")
    if d.image_delta < 0:
        d.regressions.append(f"images: -{abs(d.image_delta)}")
    if d.quick_answer_lost:
        d.regressions.append("quick_answer dropped")
    if d.schemas_lost:
        d.regressions.append(f"schemas dropped: {d.schemas_lost}")

    d.regressed = bool(d.regressions)
    return d
