"""Enhanced article pipeline — composes new modules + existing enhancer helpers.

This orchestrator runs the 11-step pipeline from the spec:
  1. Load context (per-niche pack, SERP brief, article frontmatter)
  2. Determine voice mode (3-layer logic)
  3. Run regression baseline (count visual elements)
  4. Substitute fabricated stats
  5. Inject stories (matched to voice mode)
  6. Inject voice signatures (existing experience-signal logic, voice-mode-aware)
  7. Apply humor policy
  8. Substitute forbidden phrases (global + niche)
  9. Cross-check SERP brief (H2 coverage, word count, anti-mirror)
 10. Update used-keywords.md
 11. Hard regression check — if any visual element count decreased, abort + restore

Leaves the existing scripts/article_enhancer.py unchanged. This pipeline calls
into existing enhancer helpers where useful (wrap_bare_callouts, add_quick_answer_box,
style_tables, fix_bare_markdown_bold, fix_faq_headings, etc.).
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from reference_pack_loader import (
    ReferencePack, load_pack, parse_forbidden_phrases, PackValidationError,
)
from voice_mode import determine_voice_mode
from serp_brief import load_brief, get_word_count_target
from stat_substitution import find_citable_claim_sentences, match_stat_to_library
from llm_rewriter import apply_llm_rewrite
from visual_elements import count_visual_elements, visual_regressions, ElementCounts


# ---- Helpers extracted from this pipeline ----------------------------------

_TAG_RE = re.compile(r'<[^>]+>')


def extract_article_meta(html: str, slug: str) -> dict:
    """Extract title from H1 (or fall back to slug)."""
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    title = ""
    if m:
        title = _TAG_RE.sub("", m.group(1)).strip()
    if not title:
        title = slug.replace("-", " ").title()
    return {"title": title, "slug": slug}


def detect_post_type(article_meta: dict, slug: str) -> str:
    """Heuristic post-type detection from slug + title."""
    haystack = (slug + " " + article_meta.get("title", "")).lower()

    # Order matters — check specific before generic
    if any(t in haystack for t in (" safety", "-safety", "safety-", "danger", "toxic", "warning")):
        return "safety-guide"
    if any(t in haystack for t in ("clinical", "diagnosis", "treatment-guide")):
        return "clinical-explainer"
    if "side-effect" in haystack or "side effect" in haystack:
        return "side-effects"
    if "ingredient-safety" in haystack or "ingredient safety" in haystack:
        return "ingredient-safety"
    if any(t in haystack for t in ("how-to", "how to", "guide-to", "step-by-step", "step by step")):
        return "how-to"
    if any(t in haystack for t in (" vs ", "-vs-", "compared", "comparison")):
        return "comparison"
    if "review" in haystack:
        return "review"
    if any(t in haystack for t in ("best-", "top-", " best ", " top ")):
        return "buying-guide"
    return "tips"


# ---- Step 4: stat substitution ---------------------------------------------

def apply_stat_substitution(html: str, library: list[dict]) -> tuple[str, dict]:
    """Substitute fabricated stats with vetted entries from stats.md.

    Only sentences that look like attributable factual claims (find_citable_claim_sentences)
    are processed. Methodology, product specs, and plain recommendations are
    left alone — they don't deserve a [unverified] flag.
    """
    plain = _TAG_RE.sub(" ", html)
    sentences = find_citable_claim_sentences(plain)
    substitutions = needs_source = unverified = 0

    if not library:
        # No library — flag every numeric claim as unverified
        for sent in sentences:
            if "[unverified]" in sent or "[needs-source]" in sent:
                continue
            html = html.replace(sent, sent + " [unverified]", 1)
            unverified += 1
        return html, {
            "substitutions": 0,
            "needs_source": 0,
            "unverified": unverified,
        }

    for sent in sentences:
        # Skip already-marked sentences
        if "[unverified]" in sent or "[needs-source]" in sent:
            continue
        match = match_stat_to_library(sent, library)
        if match.action == "substitute" and match.library_entry:
            entry = match.library_entry
            citation = f" (source: {entry.get('source','?')}, {entry.get('year','')})"
            new_sent = sent.rstrip('.') + citation + "."
            html = html.replace(sent, new_sent, 1)
            substitutions += 1
        elif match.action == "mark_needs_source":
            html = html.replace(sent, sent + " [needs-source]", 1)
            needs_source += 1
        elif match.action == "mark_unverified":
            html = html.replace(sent, sent + " [unverified]", 1)
            unverified += 1

    return html, {
        "substitutions": substitutions,
        "needs_source": needs_source,
        "unverified": unverified,
    }


# ---- Step 5: story injection -----------------------------------------------

def inject_stories(html: str, stories: list[dict],
                    voice_mode: str, post_type: str) -> tuple[str, dict]:
    """Inject up to 2 stories from stories.md matching voice_mode + post_type."""
    if not stories:
        return html, {"injected": 0, "reason": "no stories in pack"}

    # Filter candidates
    candidates: list[dict] = []
    for s in stories:
        if not isinstance(s, dict):
            continue
        applicable = s.get("applicable_to_post_types") or []
        if applicable and post_type not in applicable:
            continue
        is_third_person = "attribution" in s
        if voice_mode == "allowed" and not is_third_person:
            candidates.append(s)
        elif voice_mode == "third_only" and is_third_person:
            candidates.append(s)
        elif voice_mode == "mixed":
            candidates.append(s)

    if not candidates:
        return html, {"injected": 0, "reason": "no eligible candidates"}

    chosen = candidates[:2]
    insert_chunks: list[str] = []
    for s in chosen:
        text = s.get("text", "")
        if not text:
            continue
        if voice_mode == "third_only" or s.get("attribution"):
            attr = s.get("attribution", "industry observers")
            insert_chunks.append(
                f'<blockquote style="background:#f5f5f5;border-left:4px solid #9e9e9e;'
                f'padding:16px 20px;margin:20px 0;border-radius:4px;font-style:italic;">'
                f'"{text}"<footer style="margin-top:8px;font-style:normal;color:#616161;">'
                f'— <strong>{attr}</strong></footer></blockquote>'
            )
        else:
            insert_chunks.append(f'<p><em>{text}</em></p>')

    insert_html = "\n".join(insert_chunks) + "\n"

    # Insert before FAQ section if present, else at end of body
    faq_match = re.search(r'<h2[^>]*>\s*(?:FAQ|Frequently Asked|Common Questions)',
                          html, re.IGNORECASE)
    if faq_match:
        idx = faq_match.start()
        html = html[:idx] + insert_html + html[idx:]
    else:
        html = html + "\n" + insert_html

    return html, {"injected": len(chosen), "voice_mode": voice_mode}


# ---- Step 6: voice signatures (refined) ------------------------------------

def apply_voice_mode_constraints(html: str, voice_yaml: dict,
                                  voice_mode: str) -> tuple[str, dict]:
    """Enforce voice mode by stripping forbidden voice phrases."""
    if voice_mode == "third_only":
        forbidden = voice_yaml.get("forbidden_voices", []) or []
        stripped_count = 0
        for phrase in forbidden:
            if not phrase:
                continue
            # Strip the phrase and any trailing space — case-insensitive match
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            new_html, n = pattern.subn("", html)
            if n:
                html = new_html
                stripped_count += n
        return html, {
            "mode": "third_only",
            "first_person_phrases_stripped": stripped_count,
        }
    return html, {"mode": voice_mode}


# ---- Step 7: humor policy --------------------------------------------------

# Patterns of "AI humor" that we strip when humor=never
_HUMOR_STRIP_PATTERNS = [
    re.compile(r'\b(haha|hehe|lol|lmao|rofl)\b', re.IGNORECASE),
    re.compile(r'\b(amirite|bruh|fam)\b', re.IGNORECASE),
]


def apply_humor_policy(html: str, humor: dict, post_type: str) -> tuple[str, dict]:
    """Apply niche+post-type humor level. Strip humor markers if level=never."""
    per_pt = humor.get("per_post_type", {}) or {}
    level = per_pt.get(post_type, {}).get("level") or humor["defaults"]["level"]

    stripped = 0
    if level == "never":
        for pat in _HUMOR_STRIP_PATTERNS:
            new_html, n = pat.subn("", html)
            if n:
                html = new_html
                stripped += n

    return html, {
        "level_applied": level,
        "post_type": post_type,
        "humor_markers_stripped": stripped,
    }


# ---- Step 8: forbidden phrase substitution ---------------------------------

def apply_forbidden_substitution(html: str,
                                  forbidden_text: str) -> tuple[str, dict]:
    """Strip niche-forbidden phrases from forbidden.md."""
    phrases = parse_forbidden_phrases(forbidden_text)
    stripped = 0
    for p in phrases:
        if not p:
            continue
        if p in html:
            html = html.replace(p, "")
            stripped += 1
    return html, {"phrases_stripped": stripped, "phrase_count": len(phrases)}


# ---- Step 9: SERP brief cross-check ----------------------------------------

def cross_check_serp_brief(html: str, brief: dict) -> dict:
    """Compare article against SERP brief: missing topics, word count, anti-mirror."""
    counts = count_visual_elements(html)
    flags: list[str] = []
    missing_topics: list[str] = []

    # Word count vs [min, max]
    if brief.get("min_word_count") and brief.get("max_word_count"):
        if counts.word_count < brief["min_word_count"]:
            flags.append(
                f"word_count_below_min: {counts.word_count} < {brief['min_word_count']}"
            )
        elif counts.word_count > brief["max_word_count"]:
            flags.append(
                f"word_count_above_max: {counts.word_count} > {brief['max_word_count']}"
            )

    # H2 coverage vs common_h2_topics
    article_h2_lower: list[str] = []
    for m in re.finditer(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL):
        h2_text = _TAG_RE.sub("", m.group(1)).strip().lower()
        article_h2_lower.append(h2_text)

    for topic in brief.get("common_h2_topics", []):
        topic_lower = topic.lower()
        # Match if topic appears in any H2 (substring either direction)
        if not any(topic_lower in h2 or h2 in topic_lower for h2 in article_h2_lower):
            missing_topics.append(topic)
    if missing_topics:
        flags.append(f"missing_h2_topics: {missing_topics[:5]}")

    # Anti-mirror: any H2 verbatim match against a top-5 H2
    top_h2s_lower: set[str] = set()
    for r in brief.get("top_results", []):
        for h2 in r.get("h2_tree", []):
            top_h2s_lower.add(h2.strip().lower())
    mirrored = [h2 for h2 in article_h2_lower if h2 in top_h2s_lower]
    if mirrored:
        flags.append(f"h2_anti_mirror: {mirrored[:3]}")

    return {
        "word_count": counts.word_count,
        "target_word_count": brief.get("target_word_count"),
        "flags": flags,
        "missing_topics": missing_topics,
        "mirrored_h2_count": len(mirrored),
    }


# ---- Step 10: used-keywords tracker ----------------------------------------

def update_used_keywords(niche: str, slug: str, primary_keyword: str,
                         secondary_keywords: list[str],
                         styles_root: Path | None = None) -> bool:
    """Append slug to used-keywords.md (CSV) if not already there."""
    if styles_root is None:
        from reference_pack_loader import _default_styles_root
        styles_root = _default_styles_root()
    used_path = Path(styles_root) / niche / "used-keywords.md"
    if not used_path.exists():
        return False
    text = used_path.read_text(encoding="utf-8")
    # Skip if slug already there
    if f"\n{slug}," in text or text.startswith(f"{slug},"):
        return False
    from datetime import date
    secondary = "|".join(secondary_keywords) if secondary_keywords else ""
    new_row = f"{slug},{primary_keyword},{secondary},{date.today().isoformat()}\n"
    if not text.endswith("\n"):
        text += "\n"
    used_path.write_text(text + new_row, encoding="utf-8")
    return True


# ---- The 11-step orchestrator ---------------------------------------------

def run_pipeline(html: str, niche: str, slug: str,
                  styles_root: Path | None = None) -> tuple[str, dict]:
    """Run all 11 steps. Returns (enhanced_html, report).

    Does NOT enforce regression rule — that's enhance_with_regression_guard's job.
    """
    report: dict[str, Any] = {"steps": []}

    # 1. Load context
    try:
        pack = load_pack(niche, styles_root=styles_root)
    except PackValidationError as e:
        report["error"] = f"pack load failed: {e}"
        return html, report

    serp_brief = load_brief(niche, slug)
    report["serp_brief_present"] = serp_brief is not None

    article_meta = extract_article_meta(html, slug)
    post_type = detect_post_type(article_meta, slug)
    report["post_type"] = post_type

    # 2. Determine voice mode
    voice_mode = determine_voice_mode(article_meta, pack.voice, post_type)
    report["voice_mode"] = voice_mode

    # 4. Substitute fabricated stats
    html, stat_rep = apply_stat_substitution(html, pack.stats)
    report["steps"].append({"step": "stats", **stat_rep})

    # 4b. LLM rewrite [unverified]-flagged sentences (Phase γ)
    #     Consumes markers added by step 4. Each flagged sentence is either
    #     rewritten to use a verified stat, paraphrased to non-numeric, or
    #     removed entirely. Never invents new numbers.
    html, rewrite_rep = apply_llm_rewrite(html, pack.stats)
    report["steps"].append({"step": "llm_rewrite", **rewrite_rep})

    # 5. Inject stories
    html, story_rep = inject_stories(html, pack.stories, voice_mode, post_type)
    report["steps"].append({"step": "stories", **story_rep})

    # 6. Voice signatures (mode-aware)
    html, voice_rep = apply_voice_mode_constraints(html, pack.voice, voice_mode)
    report["steps"].append({"step": "voice", **voice_rep})

    # 7. Humor
    html, humor_rep = apply_humor_policy(html, pack.humor, post_type)
    report["steps"].append({"step": "humor", **humor_rep})

    # 8. Forbidden phrases
    html, forb_rep = apply_forbidden_substitution(html, pack.forbidden_text)
    report["steps"].append({"step": "forbidden", **forb_rep})

    # 9. SERP cross-check
    if serp_brief:
        cross = cross_check_serp_brief(html, serp_brief)
        report["steps"].append({"step": "serp_cross_check", **cross})

    # 10. Used keywords (uses keyword from SERP brief if present)
    if serp_brief:
        primary_kw = serp_brief.get("query", "")
        secondary = serp_brief.get("related_searches", [])[:3]
        update_used_keywords(niche, slug, primary_kw, secondary, styles_root)

    return html, report


def enhance_with_regression_guard(html: str, niche: str, slug: str,
                                    articles_dir: Path,
                                    styles_root: Path | None = None,
                                    create_backup: bool = True) -> tuple[str, dict]:
    """Run pipeline with HARD regression rule.

    If post-enhancement counts < baseline counts, restore original from .bak
    and return error report. Otherwise return enhanced HTML.
    """
    backup_path = articles_dir / f"{slug}.html.bak"

    # Create backup once (don't overwrite — preserve true original)
    if create_backup and not backup_path.exists():
        backup_path.write_text(html, encoding="utf-8")

    baseline = count_visual_elements(html)

    enhanced_html, report = run_pipeline(html, niche, slug, styles_root)

    after = count_visual_elements(enhanced_html)
    regressions = visual_regressions(baseline, after)

    if regressions:
        # ABORT — restore original
        if backup_path.exists():
            original = backup_path.read_text(encoding="utf-8")
        else:
            original = html
        return original, {
            "status": "regression_aborted",
            "regressions": regressions,
            "baseline": asdict(baseline),
            "after": asdict(after),
            "pipeline_report": report,
        }

    return enhanced_html, {
        "status": "success",
        "baseline": asdict(baseline),
        "after": asdict(after),
        "pipeline_report": report,
    }
