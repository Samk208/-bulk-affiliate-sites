#!/usr/bin/env python3
"""
serp_researcher.py -- Pre-generation SERP research via Perplexity Sonar.

For each article title, queries Perplexity to understand:
- What top-ranking pages cover for this topic
- Key subtopics, data points, products mentioned
- Common questions searchers ask

Saves research as JSON per niche for the article generator to consume.

Usage:
    python scripts/serp_researcher.py <niche-slug>              # Full niche
    python scripts/serp_researcher.py <niche-slug> --limit 5    # Test batch
    python scripts/serp_researcher.py --all                      # All niches

Output:
    outputs/<niche>/serp-research.json
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ALL_NICHES, NICHE_NAMES, RETRY_ATTEMPTS, RETRY_DELAY,
    get_niche_dir, get_articles_dir,
)

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = "sonar"  # Cheaper than sonar-pro, sufficient for SERP grounding
MAX_CONCURRENT = 3  # Perplexity rate limits are tighter

RESEARCH_PROMPT = """Research this topic as if you're preparing to write a comprehensive blog article: "{title}"

The target reader is: {outline_focus}

Tell me:
1. SEARCH INTENT: Is this query informational (how-to, explainer), commercial (comparison, "best X"), transactional (buy/book), or navigational? What does the searcher actually want to DO after reading?
2. CONTENT FORMAT: What format dominates the top results — step-by-step guide, listicle, comparison table, in-depth explainer, FAQ page, or product roundup? What format should our article use?
3. KEY SUBTOPICS: What do the top-ranking articles ALL cover? List 5-8 specific subtopics/sections that appear across multiple results. These are the "must-have" coverage areas.
4. CONTENT GAPS: What do the top 3-5 results FAIL to cover or cover poorly? What questions go unanswered? What subtopics are thin? This is our differentiation opportunity.
5. SPECIFIC DATA: Statistics, measurements, prices, or numbers commonly cited (with sources). Include the year of each stat.
6. PRODUCTS/BRANDS: Specific product names, brands, or tools mentioned across top results.
7. COMMON QUESTIONS: What "People Also Ask" or FAQ questions appear for this topic? List 4-6 exact questions.
8. EXPERT SOURCES: Any experts, organizations, or studies cited in top results. Include names and credentials.
9. CONTENT ANGLE: What angle or hook do the top results use? ("for beginners", "in 2026", "budget-friendly", "complete guide"). What angle is underserved?
10. KEY ENTITIES: What specific named entities (organizations, medical conditions, product types, brands, people, certifications, scientific terms) appear frequently across top-ranking articles? List the 8-10 most important entities that signal topical authority for this topic.
11. ENTITY CONNECTIONS: What relationships between entities do top articles establish? (e.g., "X treats Y", "A is certified by B", "C is a type of D"). List 3-5 key connections.

Be specific and factual. Include actual numbers, names, and data points — not vague summaries."""


def parse_title_line(line: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith("===") or line.startswith("#"):
        return None
    m_of = re.search(r'\{outline_focus=([^}]+)\}', line)
    m_sl = re.search(r'\{slug=([^}]+)\}', line)
    m_ca = re.search(r'\{category=([^}]+)\}', line)
    title = line.split('{')[0].strip()
    if not title:
        return None
    return {
        "title": title,
        "outline_focus": m_of.group(1) if m_of else "",
        "slug": m_sl.group(1) if m_sl else "",
        "category": m_ca.group(1) if m_ca else "Tips & Care",
    }


async def research_topic(title: str, outline_focus: str, semaphore: asyncio.Semaphore) -> dict:
    """Query Perplexity Sonar for SERP-grounded research on a topic."""
    import openai

    client = openai.AsyncOpenAI(
        api_key=PERPLEXITY_API_KEY,
        base_url="https://api.perplexity.ai",
    )

    prompt = RESEARCH_PROMPT.format(title=title, outline_focus=outline_focus)

    async with semaphore:
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                response = await client.chat.completions.create(
                    model=PERPLEXITY_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a research assistant. Provide factual, specific information from current web sources. Include real data points, product names, and source references."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2000,
                )
                content = response.choices[0].message.content
                tokens = response.usage.total_tokens if response.usage else 0
                return {
                    "research": content,
                    "tokens": tokens,
                    "model": PERPLEXITY_MODEL,
                }
            except Exception as e:
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY * attempt)
                else:
                    return {"research": "", "error": str(e), "tokens": 0}

    return {"research": "", "error": "max retries", "tokens": 0}


async def run_niche(niche_slug: str, limit: int | None = None):
    """Research all informational titles for a niche."""
    niche_dir = get_niche_dir(niche_slug)
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)

    print(f"\n{'='*60}")
    print(f"SERP RESEARCH: {niche_name}")
    print(f"Model: {PERPLEXITY_MODEL}")
    print(f"{'='*60}")

    # Load titles — prefer keyword-derived titles-v2.txt, fall back to legacy
    titles_path = niche_dir / "titles-v2.txt"
    if not titles_path.exists():
        titles_path = niche_dir / "informational-titles.txt"
    if not titles_path.exists():
        print(f"  ERROR: No title file found in {niche_dir}")
        return
    print(f"  Titles: {titles_path.name}")

    entries = []
    for line in titles_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_title_line(line)
        if parsed:
            entries.append(parsed)

    if limit:
        entries = entries[:limit]

    # Check for existing research
    research_path = niche_dir / "serp-research.json"
    existing = {}
    if research_path.exists():
        existing = json.loads(research_path.read_text(encoding="utf-8"))

    # Skip already-researched slugs
    to_research = [e for e in entries if e["slug"] not in existing]
    print(f"  Total titles: {len(entries)}")
    print(f"  Already researched: {len(entries) - len(to_research)}")
    print(f"  To research: {len(to_research)}")

    if not to_research:
        print("  All titles already researched. Skipping.")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    start_time = time.time()
    total_tokens = 0
    success = 0
    failed = 0

    for i, entry in enumerate(to_research):
        result = await research_topic(entry["title"], entry["outline_focus"], semaphore)

        if result.get("research"):
            success += 1
            total_tokens += result.get("tokens", 0)
            existing[entry["slug"]] = {
                "title": entry["title"],
                "research": result["research"],
                "tokens": result.get("tokens", 0),
            }
            print(f"  [{success + failed}/{len(to_research)}] {entry['slug']} -- {result.get('tokens', 0)} tokens")
        else:
            failed += 1
            print(f"  [{success + failed}/{len(to_research)}] {entry['slug']} -- FAILED: {result.get('error', '?')[:60]}")

        # Save progress every 10
        if (success + failed) % 10 == 0:
            research_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    # Final save
    research_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    elapsed = time.time() - start_time
    # Sonar pricing: ~$1 per 1M tokens (input+output combined)
    cost = total_tokens * 1.0 / 1_000_000

    print(f"\n{'-'*40}")
    print(f"  RESULTS: {niche_name}")
    print(f"  Researched: {success}")
    print(f"  Failed:     {failed}")
    print(f"  Time:       {elapsed:.0f}s ({elapsed/max(success,1):.1f}s/topic)")
    print(f"  Tokens:     {total_tokens:,}")
    print(f"  Est cost:   ${cost:.3f}")
    print(f"  Saved:      {research_path}")
    print(f"{'-'*40}")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/serp_researcher.py <niche-slug> [--limit N]")
        print("       python scripts/serp_researcher.py --all [--limit N]")
        sys.exit(1)

    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    niches = ALL_NICHES if sys.argv[1] == "--all" else [sys.argv[1]]

    for niche in niches:
        if not get_niche_dir(niche).exists():
            print(f"SKIP: {niche}")
            continue
        await run_niche(niche, limit)

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
