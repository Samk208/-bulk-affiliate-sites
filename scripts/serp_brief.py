"""Normalized SERP brief: schema validator, builder, loader, saver.

The SERP brief is the durable interface between SERP research and downstream
generation/enhancement. It captures: top-5 heading trees, median/target word
count (SERP-driven), AI Overview presence, PAA, common topics, format signature.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import urlparse


class BriefValidationError(ValueError):
    pass


# ---- Schema --------------------------------------------------------------

REQUIRED_FIELDS = (
    "query", "intent", "intent_source",
    "ai_overview_present", "ai_overview_citations",
    "featured_snippet_url", "paa_questions", "related_searches",
    "top_results",
    "median_word_count", "target_word_count",
    "min_word_count", "max_word_count",
    "common_h2_topics", "missing_h2_topics",
    "format_signature", "do_not_copy", "fetched_at",
)

REQUIRED_RESULT_FIELDS = (
    "rank", "url", "domain", "title", "h1",
    "h2_tree", "h3_tree",
    "word_count", "schema_types",
    "internal_links", "external_links",
)

# Word-count guardrails (mirror _global/length-policy.md)
GLOBAL_FLOOR = 1200
GLOBAL_CEILING = 4500
DEFAULT_MULTIPLIER = 1.10
YMYL_MULTIPLIER = 1.20

# Niche default word counts (used when SERP brief incomplete)
NICHE_DEFAULT_TARGET = {
    "dog-comfort": 1800,
    "camping-gear": 1800,
    "cat-care": 1800,
    "home-coffee": 1800,
    "mens-grooming": 1800,
    "oral-care": 1800,
    "home-cleaning": 1800,
    "healthy-cooking": 1800,
    "home-office": 1800,
    "water-air-quality": 1800,
    "korean-skincare": 2000,
    "makeup-beauty": 2000,
    "korean-medical-tourism": 2400,
    "korean-used-cars": 2000,
}

YMYL_NICHES = {"korean-medical-tourism"}


def validate_brief(brief: dict[str, Any]) -> None:
    """Raise BriefValidationError if brief is malformed."""
    for field in REQUIRED_FIELDS:
        if field not in brief:
            raise BriefValidationError(f"missing required field: {field}")

    for wc_field in ("median_word_count", "target_word_count",
                     "min_word_count", "max_word_count"):
        v = brief[wc_field]
        if not isinstance(v, int) or v <= 0:
            raise BriefValidationError(
                f"{wc_field} must be positive int, got {v!r}"
            )

    if brief["min_word_count"] > brief["max_word_count"]:
        raise BriefValidationError(
            f"min_word_count ({brief['min_word_count']}) must be <= "
            f"max_word_count ({brief['max_word_count']})"
        )

    if not isinstance(brief["top_results"], list):
        raise BriefValidationError("top_results must be a list")

    for i, r in enumerate(brief["top_results"]):
        if not isinstance(r, dict):
            raise BriefValidationError(f"top_results[{i}] must be a dict")
        for f in REQUIRED_RESULT_FIELDS:
            if f not in r:
                raise BriefValidationError(
                    f"top_results[{i}] missing field: {f}"
                )


# ---- Load / Save ---------------------------------------------------------

def _default_outputs_dir() -> Path:
    """Use config.OUTPUTS_DIR (worktree-aware). Fallback to <scripts>/../outputs."""
    try:
        from config import OUTPUTS_DIR
        return OUTPUTS_DIR
    except Exception:
        return Path(__file__).resolve().parent.parent / "outputs"


def load_brief(niche: str, slug: str,
               outputs_dir: Path | None = None,
               project_root: Path | None = None) -> dict | None:
    """Load brief for an article. Returns None if missing.

    `outputs_dir` is the preferred argument. `project_root` kept for backwards
    compatibility — when given, brief resolves under `<project_root>/outputs`.
    Default uses config.OUTPUTS_DIR which detects worktrees and points at the
    parent project's shared outputs/ directory.
    """
    base = _resolve_base(outputs_dir, project_root)
    brief_path = base / niche / "serp-brief" / f"{slug}.json"
    if not brief_path.exists():
        return None
    return json.loads(brief_path.read_text(encoding="utf-8"))


def save_brief(niche: str, slug: str, brief: dict,
               outputs_dir: Path | None = None,
               project_root: Path | None = None) -> Path:
    """Save brief, validating first.

    See `load_brief` for arg semantics. Default uses config.OUTPUTS_DIR which
    is worktree-aware so briefs land in the parent project's outputs/, not the
    worktree's.
    """
    validate_brief(brief)
    base = _resolve_base(outputs_dir, project_root)
    brief_dir = base / niche / "serp-brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief_path = brief_dir / f"{slug}.json"
    brief_path.write_text(
        json.dumps(brief, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return brief_path


def _resolve_base(outputs_dir: Path | None, project_root: Path | None) -> Path:
    if outputs_dir is not None:
        return Path(outputs_dir)
    if project_root is not None:
        return Path(project_root) / "outputs"
    return _default_outputs_dir()


# ---- Builder -------------------------------------------------------------

def build_brief_from_data(
    query: str,
    intent: str,
    intent_source: str,
    serp_data: dict,
    page_contents: list[dict],
    is_ymyl: bool = False,
) -> dict:
    """Construct normalized SERP brief from DataForSEO + page-content data.

    Args:
        query: target keyword
        intent: detected intent label (informational/commercial/transactional)
        intent_source: where intent came from (dataforseo, perplexity, agree, default)
        serp_data: dict with 'organic', 'paa_questions', 'serp_features',
                   'related_searches' (from serp_dataforseo.py)
        page_contents: list of dicts from fetch_top_pages_content (top-5 URLs)
        is_ymyl: apply YMYL multiplier (1.20 vs 1.10)

    Returns:
        Validated brief dict.
    """
    organic = serp_data.get("organic", []) or []
    paa = serp_data.get("paa_questions", []) or []
    features = serp_data.get("serp_features", []) or []

    # Align organic results with page contents (same order, top-5)
    top_results = []
    for i in range(min(5, len(organic), len(page_contents))):
        org = organic[i]
        pc = page_contents[i] if i < len(page_contents) else {}
        if "error" in pc:
            # Skip this result; don't include malformed entries
            continue
        url = org.get("url", "")
        top_results.append({
            "rank": org.get("position", i + 1),
            "url": url,
            "domain": _extract_domain(url),
            "title": org.get("title", ""),
            "h1": pc.get("h1", ""),
            "h2_tree": pc.get("h2_tree", []) or [],
            "h3_tree": pc.get("h3_tree", []) or [],
            "word_count": pc.get("word_count", 0) or 0,
            "schema_types": pc.get("schema_types", []) or [],
            "internal_links": pc.get("internal_links", 0) or 0,
            "external_links": pc.get("external_links", 0) or 0,
        })

    # Median word count from valid results (>300 words filter)
    valid_wcs = [r["word_count"] for r in top_results if r["word_count"] > 300]
    if valid_wcs:
        median_wc = int(median(valid_wcs))
    else:
        median_wc = 1500

    multiplier = YMYL_MULTIPLIER if is_ymyl else DEFAULT_MULTIPLIER
    target = int(median_wc * multiplier)
    target = max(GLOBAL_FLOOR, min(GLOBAL_CEILING, target))
    min_wc = max(GLOBAL_FLOOR, int(target * 0.85))
    max_wc = min(GLOBAL_CEILING, int(target * 1.20))

    # Common H2 topics: present in >=ceil(N/2) of top results
    h2_counter: dict[str, int] = {}
    for r in top_results:
        seen = set()
        for h2 in r["h2_tree"]:
            norm = _normalize_topic(h2)
            if norm and norm not in seen:
                h2_counter[norm] = h2_counter.get(norm, 0) + 1
                seen.add(norm)
    threshold = max(2, (len(top_results) + 1) // 2)  # at least 2, else ceil(n/2)
    common_h2 = sorted([t for t, n in h2_counter.items() if n >= threshold])

    return {
        "query": query,
        "intent": intent,
        "intent_source": intent_source,
        "ai_overview_present": "ai_overview" in features,
        "ai_overview_citations": [],
        "featured_snippet_url": None,
        "paa_questions": paa,
        "related_searches": serp_data.get("related_searches", []) or [],
        "top_results": top_results,
        "median_word_count": median_wc,
        "target_word_count": target,
        "min_word_count": min_wc,
        "max_word_count": max_wc,
        "common_h2_topics": common_h2,
        "missing_h2_topics": [],
        "format_signature": _detect_format(top_results),
        "do_not_copy": [],
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def get_word_count_target(niche: str, brief: dict | None) -> tuple[int, int, int]:
    """Return (target, min, max) word counts.

    Falls back to NICHE_DEFAULT_TARGET when brief is missing.
    """
    if brief and "target_word_count" in brief:
        target = brief["target_word_count"]
        min_w = max(brief.get("min_word_count", int(target * 0.85)), GLOBAL_FLOOR)
        max_w = min(brief.get("max_word_count", int(target * 1.20)), GLOBAL_CEILING)
        return target, min_w, max_w

    target = NICHE_DEFAULT_TARGET.get(niche, 1800)
    if niche in YMYL_NICHES:
        # Already factored into NICHE_DEFAULT_TARGET (2400 for medical)
        pass
    target = max(GLOBAL_FLOOR, min(GLOBAL_CEILING, target))
    min_w = max(GLOBAL_FLOOR, int(target * 0.85))
    max_w = min(GLOBAL_CEILING, int(target * 1.20))
    return target, min_w, max_w


# ---- Helpers -------------------------------------------------------------

def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def _normalize_topic(text: str) -> str:
    return " ".join((text or "").lower().split())[:80]


def _detect_format(results: list[dict]) -> str:
    if not results:
        return "guide"
    titles = " ".join(r.get("title", "").lower() for r in results)
    h1s = " ".join(r.get("h1", "").lower() for r in results)
    haystack = f"{titles} {h1s}"
    if any(t in haystack for t in (" best ", "best ", "top ", " vs ", "-vs-", "compared", "comparison")):
        return "comparison_list"
    if any(t in haystack for t in ("how to ", "step by step", "step-by-step", "tutorial")):
        return "how_to_guide"
    if any(t in haystack for t in ("what is", "what are", "definition", "meaning", "explained")):
        return "explainer"
    if any(t in haystack for t in (" review", " test", "tested")):
        return "review"
    return "guide"
