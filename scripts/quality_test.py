#!/usr/bin/env python3
"""
quality_test.py -- A/B test: Haiku vs Kimi K2.5 on the same 3 titles.

Generates 3 articles with each model, saves side-by-side for manual comparison.
Output: outputs/<niche>/quality-test/
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
    PRIMARY_MODEL, PRIMARY_MAX_TOKENS,
    get_niche_dir,
)
from article_template import SYSTEM_PROMPT, build_prompt

# Test titles — 1 How-To, 1 Tips & Care, 1 breed guide
TEST_TITLES = [
    {
        "title": "How to Help Dog Joint Pain",
        "outline_focus": "Owners combining bedding, supplements, and mobility aids",
        "slug": "how-help-joint-pain",
        "category": "How-To Guides",
    },
    {
        "title": "Dog Skin Allergies Relief",
        "outline_focus": "Owners identifying allergens and implementing soothing strategies",
        "slug": "dog-skin-allergies-relief",
        "category": "Tips & Care",
    },
    {
        "title": "Labrador Comfort Guide Large",
        "outline_focus": "Large breed owners managing joint health for active retrievers",
        "slug": "labrador-comfort-guide",
        "category": "How-To Guides",
    },
]

# Related links (same for both models)
RELATED_LINKS = [
    {"slug": "best-orthopedic-dog-bed", "title": "Best Orthopedic Dog Bed"},
    {"slug": "best-senior-dog-bed", "title": "Best Senior Dog Bed"},
    {"slug": "best-dog-bed-under-50", "title": "Best Dog Bed Under $50"},
]


async def generate_with_kimi(prompt: str) -> tuple[str, int, int]:
    import openai
    client = openai.AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
    resp = await client.chat.completions.create(
        model=PRIMARY_MODEL,
        max_tokens=PRIMARY_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        extra_headers={"HTTP-Referer": "https://claudecowork.local", "X-Title": "Quality Test"},
    )
    content = resp.choices[0].message.content
    return content, resp.usage.prompt_tokens or 0, resp.usage.completion_tokens or 0


async def generate_with_haiku(prompt: str) -> tuple[str, int, int]:
    import anthropic
    client = anthropic.AsyncAnthropic()
    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.content[0].text
    return content, resp.usage.input_tokens, resp.usage.output_tokens


async def main():
    niche_slug = "dog-comfort"
    niche_dir = get_niche_dir(niche_slug)
    test_dir = niche_dir / "quality-test"
    test_dir.mkdir(parents=True, exist_ok=True)

    product_context = ""
    pu_path = niche_dir / "product-universe.md"
    if pu_path.exists():
        product_context = pu_path.read_text(encoding="utf-8")[:2000]

    print("=" * 60)
    print("QUALITY TEST: Haiku vs Kimi K2.5")
    print("=" * 60)

    results = []

    for entry in TEST_TITLES:
        prompt = build_prompt(
            title=entry["title"],
            outline_focus=entry["outline_focus"],
            slug=entry["slug"],
            category=entry["category"],
            niche_name="Dog Comfort",
            related_links=RELATED_LINKS,
            product_context=product_context,
        )

        print(f"\n--- {entry['title']} ---")

        # Generate with Kimi
        print("  Generating with Kimi K2.5...")
        t0 = time.time()
        try:
            kimi_html, kimi_in, kimi_out = await generate_with_kimi(prompt)
            kimi_time = time.time() - t0
            kimi_words = len(kimi_html.split())
            kimi_cost = (kimi_in * 0.45 + kimi_out * 2.20) / 1_000_000
            print(f"  Kimi: {kimi_words}w, {kimi_time:.0f}s, ${kimi_cost:.4f}")
            (test_dir / f"{entry['slug']}-kimi.html").write_text(kimi_html, encoding="utf-8")
        except Exception as e:
            print(f"  Kimi FAILED: {e}")
            kimi_html = ""
            kimi_words = 0
            kimi_time = 0
            kimi_cost = 0

        # Generate with Haiku
        print("  Generating with Haiku...")
        t0 = time.time()
        try:
            haiku_html, haiku_in, haiku_out = await generate_with_haiku(prompt)
            haiku_time = time.time() - t0
            haiku_words = len(haiku_html.split())
            haiku_cost = (haiku_in * 0.80 + haiku_out * 4.00) / 1_000_000
            print(f"  Haiku: {haiku_words}w, {haiku_time:.0f}s, ${haiku_cost:.4f}")
            (test_dir / f"{entry['slug']}-haiku.html").write_text(haiku_html, encoding="utf-8")
        except Exception as e:
            print(f"  Haiku FAILED: {e}")
            haiku_html = ""
            haiku_words = 0
            haiku_time = 0
            haiku_cost = 0

        results.append({
            "title": entry["title"],
            "slug": entry["slug"],
            "kimi": {"words": kimi_words, "time": round(kimi_time, 1), "cost": round(kimi_cost, 4)},
            "haiku": {"words": haiku_words, "time": round(haiku_time, 1), "cost": round(haiku_cost, 4)},
        })

    # Summary
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"{'Title':<35} {'Kimi Words':>10} {'Haiku Words':>11} {'Kimi Cost':>10} {'Haiku Cost':>11}")
    print("-" * 80)
    for r in results:
        print(f"{r['title']:<35} {r['kimi']['words']:>10} {r['haiku']['words']:>11} ${r['kimi']['cost']:>8.4f} ${r['haiku']['cost']:>9.4f}")

    total_kimi = sum(r['kimi']['cost'] for r in results)
    total_haiku = sum(r['haiku']['cost'] for r in results)
    print("-" * 80)
    print(f"{'TOTAL':<35} {'':>10} {'':>11} ${total_kimi:>8.4f} ${total_haiku:>9.4f}")

    print(f"\nFiles saved to: {test_dir}")
    print("Review side-by-side: open *-kimi.html and *-haiku.html in browser")

    # Save results
    (test_dir / "comparison-results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
