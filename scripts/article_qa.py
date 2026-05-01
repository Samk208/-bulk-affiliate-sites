#!/usr/bin/env python3
"""
article_qa.py -- Enhanced quality checks: E-E-A-T, GEO, visual elements, readability.

Usage:
    python scripts/article_qa.py <niche-slug>
    python scripts/article_qa.py --all

Scoring dimensions:
    1. E-E-A-T (0-10, threshold 7.0)
    2. GEO (0-20, threshold 12)
    3. Visual elements (tables, callouts, quotes -- min 3)
    4. Content quality (word count, headings, links, banned words)
    5. Readability (sentence length, paragraph length)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ALL_NICHES, NICHE_NAMES, BANNED_WORDS, FLUFF_INTROS,
    EEAT_MIN_SCORE, GEO_MIN_SCORE, MIN_VISUAL_ELEMENTS, STATS_DENSITY_TARGET,
    get_articles_dir, get_niche_dir,
)
from entity_library import scan_entity_coverage, NICHE_ENTITIES


# Hedge patterns — case-insensitive EXCEPT "may" (to skip the month "May").
# GEO paper (arXiv:2311.09735): declarative language produces +14% citation lift.
_HEDGE_PATTERNS = [
    (re.compile(r'\bmay\b'),              "may"),             # lowercase-only
    (re.compile(r'\bmight\b',     re.I),  "might"),
    (re.compile(r'\bcould possibly\b', re.I), "could possibly"),
    (re.compile(r'\bperhaps\b',   re.I),  "perhaps"),
    (re.compile(r'\bpotentially\b', re.I), "potentially"),
    (re.compile(r'\barguably\b',  re.I),  "arguably"),
    (re.compile(r'\bmaybe\b',     re.I),  "maybe"),
]

# Quick Answer box recognized by its purple style markers from config.SITE_STYLES
_QUICK_ANSWER_RE = re.compile(
    r'<div[^>]*(?:#9c27b0|#f3e5f5)[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_FIRST_P_AFTER_H2_RE = re.compile(
    r'<h2[^>]*>.*?</h2>\s*<p[^>]*>(.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r'<[^>]+>')


def score_declarative_language(html: str) -> dict:
    """Flag hedging words in AI-citation "answer zones": Quick Answer box and
    first paragraph after each H2. GEO paper reports +14% citation lift for
    declarative over hedged content.

    Returns:
        {
          "hedge_count": int,        # total hedges in answer zones
          "issues":      list[str],  # human-readable per-hedge messages
          "density_per_1kw": float,  # hedges per 1,000 words in zones
        }
    """
    zones: list[str] = []
    qa = _QUICK_ANSWER_RE.search(html)
    if qa:
        zones.append(_TAG_RE.sub(" ", qa.group(1)))
    for m in _FIRST_P_AFTER_H2_RE.finditer(html):
        zones.append(_TAG_RE.sub(" ", m.group(1)))

    zone_text = " ".join(zones)
    issues: list[str] = []
    hedge_count = 0
    for pattern, word in _HEDGE_PATTERNS:
        for _ in pattern.finditer(zone_text):
            issues.append(f"Hedging word '{word}' in answer zone")
            hedge_count += 1

    word_count = len(zone_text.split()) or 1
    density = round((hedge_count / word_count) * 1000, 2)
    return {"hedge_count": hedge_count, "issues": issues, "density_per_1kw": density}


# Perplexity extracts 40-60 word passages. Anything over 60w is hard to extract
# cleanly; the 40-60 window is the sweet spot for AI-search citation.
_CHUNK_LONG_THRESHOLD = 60
_CHUNK_SWEET_MIN = 40
_CHUNK_SWEET_MAX = 60
_P_INSIDE_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL | re.IGNORECASE)


def score_chunk_extractability(html: str) -> dict:
    """Flag answer-zone paragraphs longer than 60 words.

    Answer zones: Quick Answer box <p> tags + first <p> after each <h2>.
    Perplexity's passage extractor prefers 40-60 word chunks; Indig's
    "ski ramp" front-loading finding says these zones capture the
    most AI citations.

    Returns:
        {
          "long_paragraphs":        list[{"word_count": int, "snippet": str}],
          "in_sweet_spot":          int,   # paragraphs with 40-60 words
          "total_answer_paragraphs": int,
          "issues":                 list[str],
        }
    """
    paragraphs: list[str] = []

    qa = _QUICK_ANSWER_RE.search(html)
    if qa:
        paragraphs.extend(m.group(1) for m in _P_INSIDE_RE.finditer(qa.group(1)))
    for m in _FIRST_P_AFTER_H2_RE.finditer(html):
        paragraphs.append(m.group(1))

    long_paras: list[dict] = []
    issues: list[str] = []
    in_sweet = 0

    for p_inner in paragraphs:
        text = _TAG_RE.sub(" ", p_inner).strip()
        words = text.split()
        wc = len(words)
        if wc > _CHUNK_LONG_THRESHOLD:
            snippet = " ".join(words[:10])
            long_paras.append({"word_count": wc, "snippet": snippet})
            issues.append(
                f"Long answer paragraph: {wc} words (target ≤{_CHUNK_LONG_THRESHOLD}) — '{snippet}...'"
            )
        elif _CHUNK_SWEET_MIN <= wc <= _CHUNK_SWEET_MAX:
            in_sweet += 1

    return {
        "long_paragraphs": long_paras,
        "in_sweet_spot": in_sweet,
        "total_answer_paragraphs": len(paragraphs),
        "issues": issues,
    }


# Koray's "Algorithmic Authorship" rule: every H2 should be a user question
# followed by a <=40-word extractive answer. Highest-ROI single structural pattern.
_INTERROGATIVES = {
    "what", "why", "how", "when", "where", "who", "which",
    "is", "are", "does", "do", "can", "should", "will", "would",
}
_FAQ_H2_RE = re.compile(r"frequently\s+asked|^faq$", re.IGNORECASE)
_H2_CAPTURE_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL | re.IGNORECASE)
_FIRST_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_EXTRACTIVE_ANSWER_MAX = 40


def score_algorithmic_authorship(html: str) -> dict:
    """Score H2/answer compliance with Koray's Algorithmic Authorship rule.

    For each non-FAQ H2, check two conditions:
      1. H2 is phrased as a user question (ends with '?' OR starts with an
         interrogative: what/why/how/when/where/who/which/is/are/does/do/can/should)
      2. The immediately following <p> is a <=40-word extractive answer

    Returns:
        {
          "total_h2s":          int,  # non-FAQ H2s
          "question_h2s":       int,
          "extractive_answers": int,
          "score_pct":          float,  # % of H2s meeting BOTH conditions
          "issues":             list[str],
        }
    """
    matches = list(_H2_CAPTURE_RE.finditer(html))
    total = 0
    question_count = 0
    extractive_count = 0
    both_count = 0
    issues: list[str] = []

    for i, m in enumerate(matches):
        h2_text = _TAG_RE.sub(" ", m.group(1)).strip()
        if not h2_text or _FAQ_H2_RE.search(h2_text):
            continue
        total += 1

        # (1) Question detection
        first_word = h2_text.split()[0].lower() if h2_text.split() else ""
        is_question = h2_text.rstrip().endswith("?") or first_word in _INTERROGATIVES

        # (2) Find first <p> between this H2 and the next H2 (or end of doc)
        h2_end = m.end()
        next_h2_start = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        between = html[h2_end:next_h2_start]
        p_match = _FIRST_P_RE.search(between)

        has_extractive = False
        answer_wc = 0
        if p_match:
            answer_text = _TAG_RE.sub(" ", p_match.group(1)).strip()
            answer_wc = len(answer_text.split())
            has_extractive = 0 < answer_wc <= _EXTRACTIVE_ANSWER_MAX

        if is_question:
            question_count += 1
        if has_extractive:
            extractive_count += 1
        if is_question and has_extractive:
            both_count += 1

        if not is_question:
            issues.append(f"H2 '{h2_text}' is not phrased as a question")
        if not has_extractive:
            if not p_match:
                issues.append(f"H2 '{h2_text}' has no answer paragraph")
            else:
                issues.append(
                    f"H2 '{h2_text}' answer is {answer_wc}w (target ≤{_EXTRACTIVE_ANSWER_MAX})"
                )

    score_pct = round(100.0 * both_count / total, 1) if total else 0.0
    return {
        "total_h2s": total,
        "question_h2s": question_count,
        "extractive_answers": extractive_count,
        "score_pct": score_pct,
        "issues": issues,
    }


# Dependent openers that kill AI citation when a passage is extracted out of context.
# GEO/citation research: self-contained passages are cited significantly more often.
_DEPENDENT_OPENERS = re.compile(
    r'^\s*(?:This|These|Those|They|As mentioned|As noted|As described|'
    r'In the above|In this case|In these cases|For this reason|For these reasons)\b',
    re.IGNORECASE,
)


def score_passage_self_containment(html: str) -> dict:
    """Flag answer-zone paragraphs that open with dependent pronouns or back-references.

    Answer zones: Quick Answer box <p> tags + first <p> after each <h2>.
    AI engines extract these passages out of context, so openers like "This helps..."
    or "As mentioned above..." become meaningless citations.

    Returns:
        {
          "dependent_count": int,        # number of flagged openers
          "issues":          list[str],  # one message per flagged paragraph
          "density_per_1kw": float,      # flags per 1,000 words in answer zones
        }
    """
    paragraphs: list[str] = []

    qa = _QUICK_ANSWER_RE.search(html)
    if qa:
        paragraphs.extend(m.group(1) for m in _P_INSIDE_RE.finditer(qa.group(1)))
    for m in _FIRST_P_AFTER_H2_RE.finditer(html):
        paragraphs.append(m.group(1))

    dependent_count = 0
    issues: list[str] = []
    total_words = 0

    for p_inner in paragraphs:
        text = _TAG_RE.sub(" ", p_inner).strip()
        total_words += len(text.split())
        m = _DEPENDENT_OPENERS.match(text)
        if m:
            opener = m.group(0).strip()
            snippet = " ".join(text.split()[:8])
            issues.append(
                f"Dependent opener '{opener}' in answer zone — loses meaning when extracted: '{snippet}...'"
            )
            dependent_count += 1

    density = round((dependent_count / (total_words or 1)) * 1000, 2)
    return {"dependent_count": dependent_count, "issues": issues, "density_per_1kw": density}


# Attribution phrases that can appear before OR after a stat within the same sentence.
# Note: source: and (\d{4}) are outside the \b...\b group — colons and parens are
# non-word characters and cannot satisfy a word boundary anchor.
_ATTRIBUTION_PHRASES = re.compile(
    r'(?:\b(?:according to|per the|per a|from the|from a|data from|'
    r'study by|published in|research by|research from|'
    r'shows that|show that|studies show|research shows|data shows|found that|'
    r'reported by|as reported|cited by)\b'
    r'|source:|\(\d{4}\))',
    re.IGNORECASE,
)

# Stat patterns: percentages, dollar figures, multipliers, counts with units
_STAT_PATTERNS = [
    re.compile(r'\d+(?:\.\d+)?%'),           # 28%
    re.compile(r'\$\d[\d,]*(?:\.\d+)?'),      # $45
    re.compile(r'\d+x\b'),                    # 3x
    re.compile(r'\d[\d,]+\s*(?:million|billion|thousand|people|users|dogs|cats)\b', re.I),
]


def score_stats_attribution(html: str) -> dict:
    """Check whether numeric statistics are accompanied by source attribution.

    For each stat found in the article, scans a ±15-word window (sentence-aware)
    for an attribution phrase (according to, per the, from the, etc.).
    Unattributed stats hurt AI citation quality — AI engines prefer to cite
    evidence that itself cites a primary source.

    Returns:
        {
          "total_stats":      int,
          "attributed_count": int,
          "unattributed_count": int,
          "attribution_rate": float,   # 0.0–1.0
          "issues":           list[str],
        }
    """
    # Split into sentence-level chunks to avoid bleeding context across paragraphs.
    # Replace block-level tags with sentence terminators, then strip remaining tags.
    sentence_html = re.sub(r'</(?:p|li|div|h[1-6]|td|th)>', '. ', html, flags=re.IGNORECASE)
    plain = _TAG_RE.sub(" ", sentence_html)
    # Split into rough sentences on ". " or ".\n"
    sentences = re.split(r'\.[\s]+', plain)

    total = 0
    attributed = 0
    issues: list[str] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        words = sentence.split()

        # Find stat hits within this sentence
        stat_hits: list[tuple[int, str]] = []
        for pattern in _STAT_PATTERNS:
            for m in pattern.finditer(sentence):
                char_pos = m.start()
                approx_word_idx = len(sentence[:char_pos].split())
                stat_hits.append((approx_word_idx, m.group()))

        # De-duplicate hits within 3 words of each other (e.g. "$45 million" matches twice)
        seen: list[int] = []
        deduped: list[tuple[int, str]] = []
        for idx, snippet in sorted(stat_hits):
            if not any(abs(idx - s) <= 3 for s in seen):
                deduped.append((idx, snippet))
                seen.append(idx)

        for word_idx, snippet in deduped:
            total += 1
            # Grab ±15-word window within this sentence
            start = max(0, word_idx - 15)
            end = min(len(words), word_idx + 16)
            window = " ".join(words[start:end])

            if _ATTRIBUTION_PHRASES.search(window):
                attributed += 1
            else:
                issues.append(
                    f"Unattributed stat '{snippet}' — add 'According to [source]' within 15 words"
                )

    unattributed = total - attributed
    rate = round(attributed / total, 2) if total else 1.0

    return {
        "total_stats": total,
        "attributed_count": attributed,
        "unattributed_count": unattributed,
        "attribution_rate": rate,
        "issues": issues,
    }


_LI_RE = re.compile(r'<li[^>]*>', re.IGNORECASE)
_P_IN_BOX_RE = re.compile(r'<p[^>]*>', re.IGNORECASE)


def validate_quick_answer_box(html: str) -> dict:
    """Check that the Quick Answer box (purple) uses bullet list format, not paragraphs.

    CLAUDE.md rule: Quick Answer box must have 3-4 <li> items. Paragraph text in
    the box defeats its purpose — AI engines cite structured bullet answers, not
    flowing prose.

    Returns:
        {
          "has_box":      bool,
          "bullet_count": int,
          "issues":       list[str],
        }
    """
    qa_match = _QUICK_ANSWER_RE.search(html)
    if not qa_match:
        return {"has_box": False, "bullet_count": 0, "issues": []}

    box_html = qa_match.group(0)
    bullet_count = len(_LI_RE.findall(box_html))
    para_count = len(_P_IN_BOX_RE.findall(box_html))
    issues: list[str] = []

    if para_count > 0 and bullet_count == 0:
        issues.append(
            "Quick Answer box uses <p> instead of <li> — replace with 3-4 bullet points "
            "for AI citation eligibility"
        )
    elif bullet_count < 3:
        issues.append(
            f"Quick Answer box has only {bullet_count} <li> item(s) — target is 3-4 bullets"
        )

    return {"has_box": True, "bullet_count": bullet_count, "issues": issues}


# -- E-E-A-T regex patterns (from Multi-Agent Engine eeat_validator_agent.py) --

EEAT_PATTERNS = {
    "experience": {
        "personal_testing": (r"(?:i tested|we tested|after testing|my experience|having used|when i first|in my testing|after using)", 3),
        "hands_on_examples": (r"(?:for example|in practice|when i|in my case|i noticed|i found that)", 2),
        "specific_results": (r"(?:resulted in|achieved|improved by|saved|measured|took \d+)", 2),
        "real_scenarios": (r"(?:real-world|actual use|daily use|everyday|in practice)", 1),
    },
    "expertise": {
        "technical_depth": (r"(?:mechanism|process|how it works|temperature|PSI|degrees|concentration)", 2),
        "data_driven": (r"(?:\d+%|statistics|data shows|research indicates|studies show|according to a \d{4} study)", 3),
        "methodology": (r"(?:methodology|approach|framework|process|technique|method)", 1),
        "measurements": (r"(?:\d+\s*(?:mg|ml|oz|lbs?|kg|inches|cm|mm|feet|ft|gallons?|liters?))", 2),
    },
    "authority": {
        "expert_citations": (r"(?:according to|says|states|research by|study by|published in)", 3),
        "credentials": (r"(?:PhD|Dr\.|professor|expert|specialist|certified|veterinarian|dermatologist|dentist)", 2),
        "institution_mention": (r"(?:university|institute|organization|association|foundation|academy|college)", 2),
        "source_links": (r'<a\s+href="https?://', 2),
    },
    "trust": {
        "disclosure": (r"(?:disclosure|affiliate|sponsored|partnership|commission)", 2),
        "update_date": (r"(?:last updated|updated:|as of \d{4}|current as of)", 3),
        "transparency": (r"(?:however|limitation|downside|con:|drawback|not ideal|the tradeoff)", 2),
        "verification": (r"(?:verified|fact-checked|confirmed|validated|tested)", 1),
    },
}


def score_eeat(html: str) -> dict:
    """Score E-E-A-T signals. Returns per-dimension scores and overall."""
    lower = html.lower()
    scores = {}

    for dimension, patterns in EEAT_PATTERNS.items():
        total_weight = 0
        earned_weight = 0
        signals_found = []

        for signal_name, (pattern, weight) in patterns.items():
            total_weight += weight
            matches = re.findall(pattern, lower)
            if matches:
                earned_weight += weight
                signals_found.append(signal_name)

        # Normalize to 0-10 scale
        score = min(10, (earned_weight / max(total_weight, 1)) * 10)
        scores[dimension] = {
            "score": round(score, 1),
            "signals": signals_found,
            "raw": f"{earned_weight}/{total_weight}",
        }

    overall = sum(d["score"] for d in scores.values()) / 4
    return {"dimensions": scores, "overall": round(overall, 1)}


def score_geo(html: str) -> dict:
    """Score GEO optimization. Returns 0-20 score."""
    plain = re.sub(r'<[^>]+>', ' ', html)
    words = plain.split()
    word_count = len(words)

    # 1. Statistics density (0-5)
    stat_patterns = [
        r'\d+(?:\.\d+)?%',          # percentages
        r'\$\d+',                     # dollar amounts
        r'\d+x\b',                    # multipliers
    ]
    stat_keywords = r'\b(?:percent|million|billion|increase|decrease|growth|users|survey|study)\b'
    stat_count = sum(len(re.findall(p, html)) for p in stat_patterns)
    stat_count += len(re.findall(stat_keywords, html.lower()))
    stat_count = max(stat_count, 1)  # avoid div by zero
    density = word_count / stat_count
    stats_score = 5 if 150 <= density <= 250 else (3 if 100 <= density <= 400 else 1)

    # 2. Direct answer window (0-5)
    first_60_words = " ".join(words[:60]).lower()
    # Check if first 60 words contain a direct, specific answer (not a question or intro fluff)
    has_direct = not any(first_60_words.startswith(f) for f in FLUFF_INTROS)
    answer_score = 5 if has_direct else 2

    # 3. Question-based H3s (0-5)
    h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html)
    question_h3s = sum(1 for h in h3_matches if '?' in h or h.strip().lower().startswith(('what', 'how', 'why', 'when', 'can', 'do', 'is', 'should')))
    h3_score = min(5, question_h3s)

    # 4. Citations/sources (0-5)
    citation_patterns = [
        r'according to',
        r'research (?:by|from|shows)',
        r'study (?:by|from|published)',
        r'data from',
        r'source:',
        r'\(\d{4}\)',  # year citations
    ]
    citation_count = sum(len(re.findall(p, html.lower())) for p in citation_patterns)
    citation_score = min(5, citation_count * 2)

    total = stats_score + answer_score + h3_score + citation_score

    return {
        "total": total,
        "stats_score": stats_score,
        "stats_density": round(density, 0),
        "stat_count": stat_count,
        "answer_score": answer_score,
        "question_h3s": question_h3s,
        "h3_score": h3_score,
        "citation_count": citation_count,
        "citation_score": citation_score,
    }


def count_visual_elements(html: str) -> dict:
    """Count visual elements: tables, callouts, expert quotes."""
    tables = len(re.findall(r'<table', html))
    # Pro Tip / Key Takeaway / Warning / Note callouts
    callouts = len(re.findall(r'<strong[^>]*>(?:Pro Tip|Key Takeaway|Warning|Note|Important)[:.]', html))
    # Expert blockquotes (> "quote" -- Name)
    expert_quotes = len(re.findall(r'<blockquote>', html))
    # Ordered/unordered lists
    lists = len(re.findall(r'<(?:ul|ol)>', html))

    return {
        "tables": tables,
        "callouts": callouts,
        "expert_quotes": expert_quotes,
        "lists": lists,
        "total": tables + callouts + expert_quotes,
    }


def check_readability(html: str) -> dict:
    """Check readability: sentence length, paragraph length."""
    plain = re.sub(r'<[^>]+>', '', html)
    sentences = re.split(r'[.!?]+', plain)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    word_counts = [len(s.split()) for s in sentences]
    avg_sentence_len = sum(word_counts) / max(len(word_counts), 1)
    long_sentences = sum(1 for w in word_counts if w > 25)

    paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)
    para_sentence_counts = []
    for p in paragraphs:
        p_plain = re.sub(r'<[^>]+>', '', p)
        p_sentences = [s for s in re.split(r'[.!?]+', p_plain) if len(s.strip()) > 10]
        para_sentence_counts.append(len(p_sentences))

    long_paragraphs = sum(1 for c in para_sentence_counts if c > 4)

    return {
        "avg_sentence_length": round(avg_sentence_len, 1),
        "long_sentences": long_sentences,
        "long_paragraphs": long_paragraphs,
        "total_sentences": len(sentences),
    }


def strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', ' ', text)


def check_article(html_path: Path, schema_path: Path, niche_slug: str = "") -> dict:
    """Run all QA checks on a single article."""
    slug = html_path.stem
    issues = []
    warnings = []

    html = html_path.read_text(encoding="utf-8")
    plain = strip_html(html)
    word_count = len(plain.split())

    # -- Content quality checks --
    if word_count < 1000:
        issues.append(f"TOO SHORT: {word_count} words (min 1000)")
    elif word_count > 3000:
        warnings.append(f"LONG: {word_count} words (target 1500-2500)")

    lower_html = html.lower()
    for word in BANNED_WORDS:
        if word.lower() in lower_html:
            issues.append(f"BANNED WORD: '{word}'")

    if re.search(r'<h1[^>]*>', html):
        issues.append("Contains <h1> tag")

    h2_count = len(re.findall(r'<h2[^>]*>', html))
    h3_count = len(re.findall(r'<h3[^>]*>', html))
    if h2_count < 4:
        warnings.append(f"FEW H2s: {h2_count} (target 5+)")

    internal_links = re.findall(r'<a\s+href="(/[^"]+/)"', html)
    if len(internal_links) < 2:
        issues.append(f"FEW INTERNAL LINKS: {len(internal_links)} (need 2+)")

    # Intro quality
    intro_text = plain[:300].lower().strip()
    for pattern in FLUFF_INTROS:
        if intro_text.startswith(pattern.lower()):
            issues.append(f"FLUFF INTRO: starts with '{pattern}'")

    # Schema validity
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            has_entities = False
            schemas_list = schema if isinstance(schema, list) else [schema]
            for s in schemas_list:
                if "about" in s or "mentions" in s:
                    has_entities = True
                if "@type" not in s:
                    issues.append("Schema entry missing @type")
            if not has_entities:
                warnings.append("Schema has no entity enrichment (about/mentions)")
        except json.JSONDecodeError as e:
            issues.append(f"INVALID JSON SCHEMA: {e}")
    else:
        issues.append("MISSING SCHEMA FILE")

    # -- E-E-A-T scoring --
    eeat = score_eeat(html)
    if eeat["overall"] < EEAT_MIN_SCORE:
        issues.append(f"E-E-A-T LOW: {eeat['overall']}/10 (min {EEAT_MIN_SCORE})")
        for dim, data in eeat["dimensions"].items():
            if data["score"] < 5:
                issues.append(f"  E-E-A-T {dim}: {data['score']}/10 -- missing: {dim} signals")

    # -- GEO scoring --
    geo = score_geo(html)
    if geo["total"] < GEO_MIN_SCORE:
        warnings.append(f"GEO LOW: {geo['total']}/20 (target {GEO_MIN_SCORE})")

    # -- Visual elements --
    visuals = count_visual_elements(html)
    if visuals["total"] < MIN_VISUAL_ELEMENTS:
        warnings.append(f"FEW VISUALS: {visuals['total']} (min {MIN_VISUAL_ELEMENTS}: tables={visuals['tables']}, callouts={visuals['callouts']}, quotes={visuals['expert_quotes']})")

    # -- Readability --
    readability = check_readability(html)
    if readability["avg_sentence_length"] > 22:
        warnings.append(f"LONG SENTENCES: avg {readability['avg_sentence_length']} words (target <20)")

    # FAQ and Related Articles presence
    has_faq = bool(re.search(r'<h2[^>]*>.*?(?:FAQ|Frequently Asked)', html, re.IGNORECASE))
    has_related = bool(re.search(r'<h2[^>]*>.*?Related\s+Article', html, re.IGNORECASE))
    has_updated = bool(re.search(r'[Ll]ast updated', html))

    if not has_faq:
        warnings.append("No FAQ section")
    if not has_related:
        warnings.append("No Related Articles section")
    if not has_updated:
        warnings.append("No 'Last updated' date")

    # -- Entity coverage scoring --
    entity_data = {}
    if niche_slug and niche_slug in NICHE_ENTITIES:
        ec = scan_entity_coverage(niche_slug, html)
        entity_data = {
            "coverage_pct": ec["coverage_pct"],
            "entity_count": len(ec["found"]),
            "total_entities": len(ec["found"]) + len(ec["missing"]),
            "total_mentions": ec["total_mentions"],
            "density_per_1k": ec["density_per_1k"],
            "in_headings": sum(1 for f in ec["found"] if f["in_heading"]),
            "in_intro": sum(1 for f in ec["found"] if f["first_pos"] < len(html) * 0.2),
            "missing": ec["missing"],
            "top_entities": [{"name": f["name"], "count": f["count"], "salience": f["salience"]}
                            for f in ec["found"][:5]],
        }
        if ec["coverage_pct"] < 50:
            issues.append(f"ENTITY COVERAGE LOW: {ec['coverage_pct']:.0f}% ({len(ec['found'])}/{len(ec['found'])+len(ec['missing'])} entities)")
        elif ec["coverage_pct"] < 70:
            warnings.append(f"Entity coverage moderate: {ec['coverage_pct']:.0f}% (target 70%+)")
        if ec["density_per_1k"] < 5:
            issues.append(f"ENTITY DENSITY LOW: {ec['density_per_1k']}/1000w")
        elif ec["density_per_1k"] < 10:
            warnings.append(f"Entity density moderate: {ec['density_per_1k']}/1000w (target 15+)")
        entities_in_h = sum(1 for f in ec["found"] if f["in_heading"])
        if entities_in_h == 0:
            issues.append("No entities in H2/H3 headings")
        elif entities_in_h < 3:
            warnings.append(f"Only {entities_in_h} entities in headings (target 3+)")

    # -- GEO-paper scorers: declarative language, chunk extractability, algorithmic authorship --
    declarative = score_declarative_language(html)
    if declarative["hedge_count"] > 0:
        warnings.append(
            f"HEDGING in answer zones: {declarative['hedge_count']} hedges "
            f"({declarative['density_per_1kw']}/1kw) -- hurts AI citation lift"
        )

    chunk = score_chunk_extractability(html)
    if chunk["long_paragraphs"]:
        warnings.append(
            f"LONG ANSWER PARAS: {len(chunk['long_paragraphs'])} paragraph(s) >60w in answer zones "
            f"(Perplexity prefers 40-60w chunks)"
        )

    algo = score_algorithmic_authorship(html)
    if algo["total_h2s"] > 0:
        q_rate = 100 * algo["question_h2s"] / algo["total_h2s"]
        if q_rate < 60:
            issues.append(
                f"H2 QUESTION-FORM LOW: {algo['question_h2s']}/{algo['total_h2s']} "
                f"({q_rate:.0f}%, target 80%+)"
            )
        elif q_rate < 80:
            warnings.append(
                f"H2 question-form moderate: {algo['question_h2s']}/{algo['total_h2s']} "
                f"({q_rate:.0f}%, target 80%+)"
            )

    self_contained = score_passage_self_containment(html)
    if self_contained["dependent_count"] > 0:
        warnings.append(
            f"SELF-REF OPENERS: {self_contained['dependent_count']} dependent opener(s) in answer zones "
            f"(e.g. 'This', 'These', 'As mentioned') — AI extracts these out of context"
        )

    stats_attr = score_stats_attribution(html)
    if stats_attr["total_stats"] > 0 and stats_attr["attribution_rate"] < 0.5:
        warnings.append(
            f"STATS UNATTRIBUTED: {stats_attr['unattributed_count']}/{stats_attr['total_stats']} stats "
            f"lack a source — attributed stats are cited by AI more often"
        )

    qa_box = validate_quick_answer_box(html)
    if not qa_box["has_box"]:
        issues.append("MISSING QUICK ANSWER BOX — add purple bullet-list box at top for AI citation")
    elif qa_box["issues"]:
        for qa_issue in qa_box["issues"]:
            issues.append(f"QUICK ANSWER BOX: {qa_issue}")

    return {
        "slug": slug,
        "word_count": word_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "internal_links": len(internal_links),
        "eeat_score": eeat["overall"],
        "eeat_details": eeat["dimensions"],
        "geo_score": geo["total"],
        "geo_details": geo,
        "visuals": visuals,
        "entity": entity_data,
        "readability": readability,
        "has_faq": has_faq,
        "has_related": has_related,
        "has_updated": has_updated,
        "declarative": declarative,
        "chunk": chunk,
        "algo_authorship": algo,
        "self_contained": self_contained,
        "stats_attribution": stats_attr,
        "quick_answer_box": qa_box,
        "issues": issues,
        "warnings": warnings,
    }


def run_qa(niche_slug: str):
    """Run QA on all articles in a niche."""
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    articles_dir = get_articles_dir(niche_slug)

    html_files = sorted(articles_dir.glob("*.html"))
    if not html_files:
        print(f"  No articles found in {articles_dir}")
        return

    print(f"\n{'='*60}")
    print(f"QA CHECK: {niche_name} ({len(html_files)} articles)")
    print(f"{'='*60}")

    total_issues = 0
    total_warnings = 0
    word_counts = []
    eeat_scores = []
    geo_scores = []
    visual_counts = []
    results = []

    for html_path in html_files:
        schema_path = html_path.with_suffix(".json")
        result = check_article(html_path, schema_path, niche_slug=niche_slug)
        results.append(result)
        word_counts.append(result["word_count"])
        eeat_scores.append(result["eeat_score"])
        geo_scores.append(result["geo_score"])
        visual_counts.append(result["visuals"]["total"])

        if result["issues"]:
            total_issues += len(result["issues"])
            print(f"\n  {result['slug']}:")
            for iss in result["issues"]:
                print(f"    ISSUE: {iss}")
        if result["warnings"]:
            total_warnings += len(result["warnings"])
            for w in result["warnings"]:
                print(f"    WARN:  {w}")

    n = len(results)
    avg = lambda lst: sum(lst) / max(len(lst), 1)

    articles_with_issues = sum(1 for r in results if r["issues"])
    articles_clean = n - articles_with_issues

    print(f"\n{'-'*40}")
    print(f"  SUMMARY: {niche_name}")
    print(f"  Articles:    {n} ({articles_clean} clean, {articles_with_issues} with issues)")
    print(f"  Issues:      {total_issues} | Warnings: {total_warnings}")
    print(f"  Words:       {min(word_counts)}-{max(word_counts)} (avg {avg(word_counts):.0f})")
    print(f"  E-E-A-T:     {min(eeat_scores):.1f}-{max(eeat_scores):.1f} (avg {avg(eeat_scores):.1f}) [min {EEAT_MIN_SCORE}]")
    print(f"  GEO:         {min(geo_scores)}-{max(geo_scores)} (avg {avg(geo_scores):.1f}) [min {GEO_MIN_SCORE}]")
    print(f"  Visuals:     {min(visual_counts)}-{max(visual_counts)} (avg {avg(visual_counts):.1f}) [min {MIN_VISUAL_ELEMENTS}]")
    print(f"  Avg H2/H3:   {avg([r['h2_count'] for r in results]):.1f} / {avg([r['h3_count'] for r in results]):.1f}")
    print(f"  Avg links:   {avg([r['internal_links'] for r in results]):.1f}")
    print(f"  With FAQ:    {sum(1 for r in results if r['has_faq'])}/{n}")
    print(f"  Updated:     {sum(1 for r in results if r['has_updated'])}/{n}")

    # Entity stats
    entity_coverages = [r["entity"]["coverage_pct"] for r in results if r.get("entity")]
    entity_densities = [r["entity"]["density_per_1k"] for r in results if r.get("entity")]
    if entity_coverages:
        print(f"  Entity cov:  {min(entity_coverages):.0f}-{max(entity_coverages):.0f}% (avg {avg(entity_coverages):.0f}%)")
        print(f"  Entity den:  {min(entity_densities):.0f}-{max(entity_densities):.0f}/1kw (avg {avg(entity_densities):.0f}/1kw)")

    # GEO-paper scorer aggregates
    q_rates = [100 * r["algo_authorship"]["question_h2s"] / r["algo_authorship"]["total_h2s"]
               for r in results if r.get("algo_authorship", {}).get("total_h2s", 0) > 0]
    hedge_counts = [r["declarative"]["hedge_count"] for r in results if r.get("declarative")]
    long_para_counts = [len(r["chunk"]["long_paragraphs"]) for r in results if r.get("chunk")]
    if q_rates:
        print(f"  H2 q-form:   {min(q_rates):.0f}-{max(q_rates):.0f}% (avg {avg(q_rates):.0f}%) [target 80%+]")
    if hedge_counts:
        print(f"  Hedges:      {sum(hedge_counts)} total in answer zones (avg {avg(hedge_counts):.1f}/article)")
    if long_para_counts:
        print(f"  Long paras:  {sum(long_para_counts)} total >60w in answer zones (avg {avg(long_para_counts):.1f}/article)")

    self_ref_counts = [r["self_contained"]["dependent_count"] for r in results if r.get("self_contained")]
    if sum(self_ref_counts) > 0:
        print(f"  Self-ref:    {sum(self_ref_counts)} total dependent openers (avg {avg(self_ref_counts):.1f}/article)")

    attr_rates = [r["stats_attribution"]["attribution_rate"] for r in results if r.get("stats_attribution") and r["stats_attribution"]["total_stats"] > 0]
    if attr_rates:
        avg_rate = round(sum(attr_rates) / len(attr_rates), 2)
        print(f"  Stats attr:  {avg_rate:.0%} avg attribution rate (target 50%+)")

    print(f"  VERDICT:     {'PASS' if total_issues == 0 else 'NEEDS FIXES'}")
    print(f"{'-'*40}")

    # Save report
    report_path = articles_dir / "qa-report.json"
    report_path.write_text(
        json.dumps({
            "niche": niche_slug,
            "total_articles": n,
            "clean": articles_clean,
            "with_issues": articles_with_issues,
            "avg_eeat": round(avg(eeat_scores), 1),
            "avg_geo": round(avg(geo_scores), 1),
            "avg_visuals": round(avg(visual_counts), 1),
            "avg_word_count": round(avg(word_counts)),
            "articles": results,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Report: {report_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/article_qa.py <niche-slug>")
        print("       python scripts/article_qa.py --all")
        sys.exit(1)

    niches = ALL_NICHES if sys.argv[1] == "--all" else [sys.argv[1]]

    for niche in niches:
        if not get_niche_dir(niche).exists():
            print(f"SKIP: {niche}")
            continue
        run_qa(niche)

    print("\nDone.")


if __name__ == "__main__":
    main()
