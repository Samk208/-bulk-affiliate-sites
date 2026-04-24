"""
tier1_pillar_generator.py — Tier 1 Pillar Post Generator
==========================================================
Automates Tier 1 article generation using OpenRouter (Claude Opus or Sonnet).
Encodes all quality rules from CLAUDE.md + lessons from 2026-04-12 session.

Usage:
    python scripts/tier1_pillar_generator.py --niche dog-comfort --keyword "dog grooming guide" --slug dog-grooming-skin-care-guide --cluster "Cluster 6: Grooming" --gaps "gap1|gap2|gap3"

    # Or batch from a JSON file:
    python scripts/tier1_pillar_generator.py --from-file scripts/pillar_queue.json

Requirements:
    pip install openai requests --break-system-packages
    OPENROUTER_API_KEY in _global/.env.cowork
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime

# ── Load env ──────────────────────────────────────────────────────────────────
# Check project root first (.env.cowork next to scripts/), then legacy _global path
_project_root_env = Path(__file__).parent.parent / ".env.cowork"
_global_env = Path(__file__).parent.parent.parent.parent / "_global" / ".env.cowork"
ENV_FILE = _project_root_env if _project_root_env.exists() else _global_env
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
if not OPENROUTER_API_KEY:
    sys.exit("ERROR: OPENROUTER_API_KEY not found. Create .env.cowork in project root with OPENROUTER_API_KEY=...")

# ── Quality rules encoded from CLAUDE.md ─────────────────────────────────────
BANNED_WORDS = [
    "delve", "tapestry", "landscape", "crucial", "leverage", "utilize",
    "cutting-edge", "game-changer", "revolutionize", "seamless", "robust",
    "furthermore", "moreover", "realm", "symphony", "bustling", "innovative", "uncover"
]

BANNED_INTROS = [
    "In today's", "When it comes to", "If you're looking for",
    "Are you tired of", "In this article", "In today's fast-paced",
    "Have you ever wondered"
]

VISUAL_HTML = """
PRO TIP BOX:
<div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:16px 20px;margin:20px 0;border-radius:4px;">
<strong style="color:#2e7d32;">Pro Tip:</strong> [tip text]
</div>

WARNING BOX:
<div style="background:#fff3e0;border-left:4px solid #ff9800;padding:16px 20px;margin:20px 0;border-radius:4px;">
<strong style="color:#e65100;">Warning:</strong> [warning text]
</div>

KEY TAKEAWAY:
<div style="background:#e3f2fd;border-left:4px solid #2196f3;padding:16px 20px;margin:20px 0;border-radius:4px;">
<strong style="color:#1565c0;">Key Takeaway:</strong> [takeaway text]
</div>

EXPERT QUOTE:
<blockquote style="background:#f5f5f5;border-left:4px solid #9e9e9e;padding:16px 20px;margin:20px 0;border-radius:4px;font-style:italic;">
"[quote]"
<footer style="margin-top:8px;font-style:normal;color:#616161;">— <strong>[Name]</strong>, [Title], [Year]</footer>
</blockquote>

QUICK ANSWER BOX (top of article):
<div style="background:#f3e5f5;border:2px solid #9c27b0;padding:20px;margin:0 0 24px 0;border-radius:8px;">
<strong style="color:#6a1b9a;font-size:1.1em;">Quick Answer:</strong>
<ul style="margin:10px 0 0 0;padding-left:20px;line-height:1.8;">
<li>[point 1]</li>
<li>[point 2]</li>
<li>[point 3]</li>
<li>[point 4]</li>
</ul>
</div>

STYLED TABLE:
<table style="width:100%;border-collapse:collapse;margin:20px 0;">
<thead><tr style="background:#1a237e;color:white;">
<th style="padding:12px 16px;text-align:left;">Column</th></tr></thead>
<tbody>
<tr style="background:#f5f5f5;"><td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td></tr>
<tr><td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;">Data</td></tr>
</tbody></table>
"""

SYSTEM_PROMPT = f"""You are an expert affiliate blog writer creating Tier 1 pillar posts.

HARD RULES — VIOLATIONS WILL FAIL QA:
1. PARAGRAPH LENGTH: Maximum 2-3 sentences, HARD LIMIT 50 words. One-sentence paragraphs encouraged. Break any paragraph over 50 words into two.
2. NO FABRICATED DATA: Only real facts, real brands, real organizations. Use AKC, AVMA, VCA, PetMD, university research. Never invent statistics, quotes, or study results.
3. BANNED WORDS (never use): {', '.join(BANNED_WORDS)}
4. BANNED INTRO PHRASES: {', '.join(BANNED_INTROS)}
5. QUICK ANSWER BOX: Must be a bullet list (3-4 items), NOT paragraph text. Purple box at very top.

MANDATORY VISUAL ELEMENTS (use these HTML formats exactly):
{VISUAL_HTML}

VISUAL ELEMENT COUNTS PER ARTICLE:
- Quick Answer box: 1 (very top)
- Pro Tip boxes (green): 2-3
- Warning box (orange): 1
- Key Takeaway boxes (blue): 1-2
- Expert quotes (gray blockquote): 1-2 (REAL people/orgs only)
- Styled tables (navy header): 1-2

E-E-A-T SIGNALS:
- Experience: "After testing X..." / first-person testing scenarios
- Expertise: specific numbers, temperatures, dosages, percentages
- Authority: cite organizations, link to real studies
- Trust: mention downsides honestly

GEO OPTIMIZATION:
- Quick Answer box at top (AI citation target)
- Question-based H3 subheadings
- Answer each H3 in the FIRST sentence
- Include 1+ statistic with source per H2
- Use "as of 2026" for temporal data

ARTICLE STRUCTURE:
- Quick Answer box (purple) — FIRST element
- Opening paragraph (no banned intros) — establish the problem or gap
- 5-7 H2 sections with H3 subsections
- FAQ section at the end (5+ questions, real questions people search)
- Word count target: 2,500-3,000 words

OUTPUT: HTML only. No markdown. No explanatory text before or after. Start with the Quick Answer div, end with the last FAQ answer closing tag.
"""

# ── Gap analysis prompt ───────────────────────────────────────────────────────
GAP_PROMPT_TEMPLATE = """You are analyzing SERP results to find content gaps for a Tier 1 affiliate article.

TARGET KEYWORD: {keyword}
NICHE: {niche}

TOP SERP RESULTS COVER:
{serp_summary}

YOUR TASK:
1. Identify 3-5 specific things the top 5-10 articles ALL miss or handle superficially
2. State the unique angle this article will take
3. List 5 key statistics or facts to anchor the article (from real sources: AKC, AVMA, VCA, PetMD, universities)
4. List 5 FAQ questions people actually search (use question-intent keywords)

Format your response as JSON:
{{
  "gaps": ["gap1", "gap2", "gap3"],
  "unique_angle": "one sentence describing what makes this article different",
  "key_facts": [
    {{"fact": "...", "source": "..."}},
    ...
  ],
  "faq_questions": ["Q1?", "Q2?", "Q3?", "Q4?", "Q5?"]
}}
"""

# ── Article generation prompt ─────────────────────────────────────────────────
ARTICLE_PROMPT_TEMPLATE = """Write a complete Tier 1 pillar article for the following:

KEYWORD: {keyword}
NICHE: {niche}
SLUG: {slug}
CLUSTER: {cluster}

UNIQUE ANGLE (what makes this different from everything ranking):
{unique_angle}

KEY GAPS TO FILL (content competitors miss):
{gaps}

KEY FACTS TO ANCHOR (use these, don't fabricate others):
{key_facts}

FAQ QUESTIONS TO ANSWER AT THE END:
{faq_questions}

Remember all hard rules from your system prompt. Start directly with the Quick Answer box HTML.
"""

# ── OpenRouter API call ───────────────────────────────────────────────────────
def call_openrouter(system: str, user: str, model: str = "anthropic/claude-sonnet-4-5") -> str:
    """Call OpenRouter and return the response text."""
    import urllib.request

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": 8000,
        "temperature": 0.7
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://bulk-affiliate-sites.local",
            "X-Title": "Bulk Affiliate Sites"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"]


# ── QA Checks ─────────────────────────────────────────────────────────────────
def qa_check(html: str, keyword: str) -> dict:
    """Run basic QA checks on generated article."""
    issues = []
    warnings = []

    # Check paragraph lengths
    paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)
    long_paras = []
    for i, p in enumerate(paragraphs):
        clean = re.sub(r'<[^>]+>', '', p).strip()
        word_count = len(clean.split())
        if word_count > 50:
            long_paras.append(f"Para {i+1}: {word_count} words")
    if long_paras:
        issues.append(f"PARAGRAPHS OVER 50 WORDS: {long_paras}")

    # Check banned words
    html_lower = html.lower()
    found_banned = [w for w in BANNED_WORDS if w.lower() in html_lower]
    if found_banned:
        issues.append(f"BANNED WORDS FOUND: {found_banned}")

    # Check banned intros
    for intro in BANNED_INTROS:
        if intro.lower() in html_lower:
            issues.append(f"BANNED INTRO FOUND: '{intro}'")

    # Check required elements
    if 'background:#f3e5f5' not in html:
        issues.append("MISSING: Quick Answer box (purple)")
    if 'background:#e8f5e9' not in html:
        warnings.append("MISSING: Pro Tip box (green)")
    if 'background:#fff3e0' not in html:
        warnings.append("MISSING: Warning box (orange)")
    if 'background:#e3f2fd' not in html:
        warnings.append("MISSING: Key Takeaway box (blue)")
    if 'blockquote' not in html:
        warnings.append("MISSING: Expert quote blockquote")
    if '<table' not in html:
        warnings.append("MISSING: Styled table")
    if '<h2>' not in html:
        issues.append("MISSING: H2 headings")

    # Word count estimate
    text = re.sub(r'<[^>]+>', '', html)
    word_count = len(text.split())
    if word_count < 2000:
        issues.append(f"WORD COUNT TOO LOW: {word_count} words (target: 2,500+)")

    return {
        "passed": len(issues) == 0,
        "word_count": word_count,
        "issues": issues,
        "warnings": warnings
    }


# ── Generate one article ───────────────────────────────────────────────────────
def generate_article(
    niche: str,
    keyword: str,
    slug: str,
    cluster: str,
    gaps: list = None,
    unique_angle: str = "",
    key_facts: list = None,
    faq_questions: list = None,
    serp_summary: str = "",
    model: str = "anthropic/claude-sonnet-4-5"
) -> dict:
    """Generate a complete Tier 1 article. Returns dict with html, json, qa."""

    output_dir = Path(__file__).parent.parent / "outputs" / niche / "articles"
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{slug}.html"
    json_path = output_dir / f"{slug}.json"

    # Skip if already exists
    if html_path.exists():
        print(f"  ⏭  Skipping {slug} — already exists")
        return {"skipped": True, "slug": slug}

    print(f"\n{'='*60}")
    print(f"Generating: {keyword}")
    print(f"  Niche: {niche} | Slug: {slug}")
    print(f"{'='*60}")

    # Step 1: Gap analysis (if not pre-supplied)
    if not gaps and serp_summary:
        print("  → Running gap analysis...")
        gap_prompt = GAP_PROMPT_TEMPLATE.format(
            keyword=keyword,
            niche=niche,
            serp_summary=serp_summary
        )
        gap_response = call_openrouter(
            "You are a content strategist who finds gaps in SERP results. Respond only with JSON.",
            gap_prompt,
            model=model
        )
        try:
            gap_data = json.loads(gap_response)
            gaps = gap_data.get("gaps", [])
            unique_angle = gap_data.get("unique_angle", "")
            key_facts = gap_data.get("key_facts", [])
            faq_questions = gap_data.get("faq_questions", [])
            print(f"  ✓ Gaps found: {gaps}")
        except json.JSONDecodeError:
            print("  ⚠ Could not parse gap analysis JSON — using supplied values")

    # Step 2: Generate article
    print("  → Generating article...")
    article_prompt = ARTICLE_PROMPT_TEMPLATE.format(
        keyword=keyword,
        niche=niche,
        slug=slug,
        cluster=cluster,
        unique_angle=unique_angle or "Comprehensive, well-researched guide with unique data points",
        gaps="\n".join(f"- {g}" for g in (gaps or [])),
        key_facts="\n".join(f"- {f.get('fact', f)} ({f.get('source', '')})" if isinstance(f, dict) else f"- {f}" for f in (key_facts or [])),
        faq_questions="\n".join(f"- {q}" for q in (faq_questions or []))
    )

    html_content = call_openrouter(SYSTEM_PROMPT, article_prompt, model=model)

    # Add comment header
    header = f"<!-- PILLAR: {keyword} | Slug: {slug} | Niche: {niche} -->\n<!-- Tier 1 | Phase A | Generated: {datetime.now().strftime('%Y-%m-%d')} -->\n\n"
    html_content = header + html_content

    # Step 3: QA
    print("  → Running QA checks...")
    qa_result = qa_check(html_content, keyword)

    if not qa_result["passed"]:
        print(f"  ⚠ QA ISSUES FOUND:")
        for issue in qa_result["issues"]:
            print(f"    ❌ {issue}")

    if qa_result["warnings"]:
        for warning in qa_result["warnings"]:
            print(f"    ⚠ {warning}")

    print(f"  ✓ Word count: ~{qa_result['word_count']:,}")

    # Step 4: Save
    html_path.write_text(html_content, encoding="utf-8")
    print(f"  ✓ Saved: {html_path}")

    # Step 5: Save JSON-LD
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": keyword,
        "description": f"Complete guide to {keyword.lower()} — {unique_angle}",
        "keywords": keyword,
        "datePublished": datetime.now().strftime("%Y-%m-%d"),
        "dateModified": datetime.now().strftime("%Y-%m-%d"),
        "author": {"@type": "Person", "name": "Dog Comfort Hub"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"/{slug}/"},
        "wordCount": qa_result["word_count"],
        "tier": "1",
        "phase": "A",
        "niche": niche,
        "cluster": cluster,
        "wpStatus": "pending",
        "qaResult": qa_result
    }
    json_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    return {
        "skipped": False,
        "slug": slug,
        "html_path": str(html_path),
        "json_path": str(json_path),
        "qa": qa_result
    }


# ── Batch mode ────────────────────────────────────────────────────────────────
def run_batch(queue_file: str, model: str):
    """Run from a JSON queue file."""
    queue = json.loads(Path(queue_file).read_text())
    results = []

    for item in queue:
        result = generate_article(model=model, **item)
        results.append(result)

        # Save progress
        progress_file = Path(queue_file).parent / "pillar_progress.json"
        progress_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Summary
    completed = [r for r in results if not r.get("skipped")]
    passed = [r for r in completed if r.get("qa", {}).get("passed")]
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {len(completed)} generated, {len(passed)} passed QA")
    print(f"{'='*60}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Tier 1 pillar articles")
    parser.add_argument("--niche", help="Niche folder name (e.g. dog-comfort)")
    parser.add_argument("--keyword", help="Target keyword")
    parser.add_argument("--slug", help="URL slug")
    parser.add_argument("--cluster", help="Cluster name (e.g. Cluster 2: Anxiety)")
    parser.add_argument("--gaps", help="Pipe-separated list of content gaps")
    parser.add_argument("--unique-angle", help="One-line unique angle")
    parser.add_argument("--from-file", help="JSON queue file for batch mode")
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-5",
                       help="OpenRouter model (default: claude-sonnet-4-5)")

    args = parser.parse_args()

    if args.from_file:
        run_batch(args.from_file, args.model)
    elif args.niche and args.keyword and args.slug:
        result = generate_article(
            niche=args.niche,
            keyword=args.keyword,
            slug=args.slug,
            cluster=args.cluster or "",
            gaps=args.gaps.split("|") if args.gaps else [],
            unique_angle=args.unique_angle or "",
            model=args.model
        )
        if result.get("qa", {}).get("passed"):
            print("\n✅ PASSED QA")
        else:
            print("\n❌ FAILED QA — review issues above")
    else:
        parser.print_help()
