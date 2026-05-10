#!/usr/bin/env python3
"""
article_generator.py -- Generate informational articles via Kimi K2.5 (OpenRouter).

Model routing:
  Primary:  Kimi K2.5 via OpenRouter ($0.45/$2.20 per 1M tokens)
  Fallback: Claude Sonnet via Anthropic ($3/$15 per 1M tokens)

Usage:
    python scripts/article_generator.py <niche-slug>                # Full niche
    python scripts/article_generator.py <niche-slug> --limit 5      # Test batch
    python scripts/article_generator.py --all                        # All niches
    python scripts/article_generator.py --all --limit 5              # 5 per niche
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ALL_NICHES, NICHE_NAMES, MAX_CONCURRENT, RETRY_ATTEMPTS, RETRY_DELAY,
    OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
    PRIMARY_MODEL, PRIMARY_MAX_TOKENS,
    get_niche_dir, get_articles_dir,
)
from article_template import SYSTEM_PROMPT, build_prompt, build_schema


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


def load_product_context(niche_dir: Path) -> str:
    pu_path = niche_dir / "product-universe.md"
    if pu_path.exists():
        return pu_path.read_text(encoding="utf-8")[:2000]
    return ""


def load_progress(articles_dir: Path) -> dict:
    progress_path = articles_dir / "progress.json"
    if progress_path.exists():
        data = json.loads(progress_path.read_text(encoding="utf-8"))
        # Ensure required keys exist (progress file may have been written by scheduled task)
        data.setdefault("completed", [])
        data.setdefault("failed", [])
        data.setdefault("started_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        return data
    return {"completed": [], "failed": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def save_progress(articles_dir: Path, progress: dict):
    progress_path = articles_dir / "progress.json"
    progress["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    progress_path.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")


def _openrouter_post(payload: dict) -> dict:
    """Synchronous OpenRouter POST using stdlib urllib (no third-party deps)."""
    import json as _json
    import urllib.request
    data = _json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claudecowork.local",
            "X-Title": "Bulk Affiliate Article Generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return _json.loads(resp.read())


async def call_openrouter(user_prompt: str) -> tuple[str, int, int, str]:
    """Call DeepSeek V4 Flash via OpenRouter. Returns (content, in_tokens, out_tokens, model_used)."""
    payload = {
        "model": PRIMARY_MODEL,
        "max_tokens": PRIMARY_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = await asyncio.to_thread(_openrouter_post, payload)
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    in_tok = usage.get("prompt_tokens", 0)
    out_tok = usage.get("completion_tokens", 0)
    model_used = data.get("model", PRIMARY_MODEL)
    return content, in_tok, out_tok, model_used


    # No Sonnet API fallback — Cowork (Claude Code session) handles failures
    # at $0 cost via subscription. See cowork-queue.json after each run.


async def generate_article(
    entry: dict,
    niche_slug: str,
    niche_name: str,
    related_links: list[dict],
    product_context: str,
    articles_dir: Path,
    semaphore: asyncio.Semaphore,
    serp_context: str = "",
) -> dict:
    """Generate a single article with primary/fallback model routing."""
    slug = entry["slug"]
    html_path = articles_dir / f"{slug}.html"
    schema_path = articles_dir / f"{slug}.json"

    if html_path.exists() and schema_path.exists():
        return {"slug": slug, "status": "skipped", "reason": "already exists"}

    user_prompt = build_prompt(
        title=entry["title"],
        outline_focus=entry["outline_focus"],
        slug=slug,
        category=entry["category"],
        niche_name=niche_name,
        related_links=related_links,
        product_context=product_context,
        serp_context=serp_context,
        niche_slug=niche_slug,
    )

    async with semaphore:
        html_content = None
        model_used = "none"

        # Try primary model (DeepSeek V4 Flash via OpenRouter)
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                html_content, in_tok, out_tok, model_used = await call_openrouter(user_prompt)
                break
            except Exception as e:
                err_str = str(e)
                if attempt < RETRY_ATTEMPTS:
                    wait = RETRY_DELAY * attempt
                    print(f"    DeepSeek retry {attempt} on {slug}: {err_str[:80]}")
                    await asyncio.sleep(wait)
                else:
                    print(f"    DeepSeek failed on {slug}, queuing for Cowork fallback...")

        # If DeepSeek failed entirely, mark for Cowork fallback (zero cost)
        if html_content is None:
            return {"slug": slug, "status": "needs_cowork", "error": "DeepSeek failed, queued for Cowork"}

        # Check for truncation — if under 800 words, mark for Cowork redo
        if len(html_content.split()) < 800:
            print(f"    {slug} truncated ({len(html_content.split())}w), marking for Cowork...")
            return {"slug": slug, "status": "needs_cowork", "error": f"Truncated at {len(html_content.split())}w"}

        # Save HTML
        html_path.write_text(html_content, encoding="utf-8")

        # Generate and save schema (with entity enrichment)
        description = entry["outline_focus"] or entry["title"]
        schema = build_schema(
            title=entry["title"],
            slug=slug,
            category=entry["category"],
            description=description,
            html_content=html_content,
            niche_name=niche_name,
            niche_slug=niche_slug,
        )
        schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "slug": slug,
            "status": "success",
            "model": model_used,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "word_count": len(html_content.split()),
        }


def _build_serp_context(dfs_data: dict, perplexity_research: str, keyword: str) -> str:
    """Merge DataForSEO real SERP snapshot with Perplexity research into one prompt block.

    DataForSEO gives real competitor URLs, snippets, and PAA questions.
    Perplexity gives synthesised facts, stats, and content gaps.
    Together they give Kimi K2.5 everything it needs to outrank the top 10.
    """
    parts = []

    # --- DataForSEO block (real SERP) ---
    if dfs_data and dfs_data.get("organic"):
        organic = dfs_data["organic"]
        features = dfs_data.get("serp_features", [])
        paa = dfs_data.get("paa_questions", [])
        total = dfs_data.get("total_results", 0)

        lines = [f'REAL SERP DATA (live Google results for: "{keyword}")']

        if total:
            lines.append(f"Total results: {total:,}")

        if features:
            feature_labels = {
                "featured_snippet": "Featured Snippet (★ CLAIM THIS — answer the query in first 40-60 words)",
                "people_also_ask":  "People Also Ask (cover ALL PAA questions below)",
                "knowledge_graph":  "Knowledge Graph (strong entity signals required)",
                "local_pack":       "Local Pack",
                "video_carousel":   "Video Carousel",
                "image_pack":       "Image Pack",
                "top_stories":      "Top Stories (news freshness factor)",
            }
            lines.append("\nSERP FEATURES PRESENT:")
            for f in features:
                lines.append(f"  - {feature_labels.get(f, f)}")

        lines.append(f"\nTOP {len(organic)} RANKING PAGES (beat these):")
        for r in organic:
            lines.append(f"  {r['position']}. {r['title']}")
            lines.append(f"     URL: {r['url']}")
            if r.get("snippet"):
                lines.append(f"     Snippet: {r['snippet'][:180]}")

        if paa:
            lines.append("\nPEOPLE ALSO ASK (cover every one of these — they become H3 subheadings):")
            for q in paa:
                lines.append(f"  - {q}")

        lines.append("\nCOMPETITOR STRATEGY:")
        lines.append("  - Study what the top 3 URLs cover (their snippets reveal their structure).")
        lines.append("  - Your article MUST cover everything they cover, PLUS fill the gaps.")
        lines.append("  - The article that answers MORE questions = the article that ranks.")
        if "featured_snippet" in features:
            lines.append("  - A Featured Snippet is live — write a 40-60 word direct answer RIGHT AFTER your first H2.")

        parts.append("\n".join(lines))

    # --- Perplexity research block ---
    if perplexity_research:
        parts.append(
            "PERPLEXITY SERP RESEARCH (synthesized facts, data points, content gaps):\n"
            + perplexity_research
        )

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)


async def run_niche(niche_slug: str, limit: int | None = None):
    """Generate all informational articles for a niche."""
    niche_dir = get_niche_dir(niche_slug)
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    articles_dir = get_articles_dir(niche_slug)

    print(f"\n{'='*60}")
    print(f"GENERATING: {niche_name}")
    print(f"Primary: {PRIMARY_MODEL} | Fallback: Cowork (session)")
    print(f"Output: {articles_dir}")
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

    print(f"  Articles to generate: {len(entries)}")

    # Load link map
    link_map_path = niche_dir / "link-map.json"
    link_map = {}
    if link_map_path.exists():
        link_map = json.loads(link_map_path.read_text(encoding="utf-8"))
        print(f"  Link map loaded: {len(link_map)} mappings")
    else:
        print(f"  WARNING: No link-map.json -- run link-mapper.py first")

    product_context = load_product_context(niche_dir)

    # Load SERP research (from serp_researcher.py — Perplexity Sonar)
    serp_path = niche_dir / "serp-research.json"
    serp_research = {}
    if serp_path.exists():
        serp_research = json.loads(serp_path.read_text(encoding="utf-8"))
        print(f"  SERP research loaded: {len(serp_research)} topics (Perplexity)")
    else:
        print(f"  NOTE: No serp-research.json -- run serp_researcher.py for better quality")

    # Load DataForSEO real SERP data (from serp_dataforseo.py)
    dfs_path = niche_dir / "serp-dataforseo.json"
    serp_dataforseo = {}
    if dfs_path.exists():
        serp_dataforseo = json.loads(dfs_path.read_text(encoding="utf-8"))
        print(f"  DataForSEO SERP loaded: {len(serp_dataforseo)} keywords")

    progress = load_progress(articles_dir)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    start_time = time.time()
    total_input = 0
    total_output = 0
    success = 0
    skipped = 0
    failed = 0
    needs_cowork = 0
    models_used = {}
    cowork_queue = []  # Slugs for Cowork to handle

    tasks = []
    for entry in entries:
        related_links = link_map.get(entry["slug"], [])

        # Build combined SERP context: DataForSEO real SERP first, then Perplexity research
        dfs_data = serp_dataforseo.get(entry["slug"], {})
        perplexity_research = serp_research.get(entry["slug"], {}).get("research", "")
        topic_research = _build_serp_context(dfs_data, perplexity_research, entry["title"])

        tasks.append(
            generate_article(
                entry=entry,
                niche_slug=niche_slug,
                niche_name=niche_name,
                related_links=related_links,
                product_context=product_context,
                articles_dir=articles_dir,
                semaphore=semaphore,
                serp_context=topic_research,
            )
        )

    done_count = 0
    for coro in asyncio.as_completed(tasks):
        result = await coro
        slug = result["slug"]
        status = result["status"]
        done_count += 1

        if status == "success":
            success += 1
            total_input += result.get("input_tokens", 0)
            total_output += result.get("output_tokens", 0)
            model = result.get("model", "unknown")
            models_used[model] = models_used.get(model, 0) + 1
            progress["completed"].append(slug)
            print(f"  [{done_count}/{len(entries)}] {slug} -- {result.get('word_count', '?')}w [{model.split('/')[-1][:12]}]")
        elif status == "skipped":
            skipped += 1
        elif status == "needs_cowork":
            needs_cowork += 1
            cowork_queue.append(slug)
            print(f"  [{done_count}/{len(entries)}] {slug} -- QUEUED FOR COWORK: {result.get('error', '')[:60]}")
        elif status == "failed":
            failed += 1
            progress["failed"].append(slug)
            print(f"  [{done_count}/{len(entries)}] {slug} -- FAILED: {result.get('error', '?')[:60]}")

        if (success + failed + needs_cowork) % 10 == 0:
            save_progress(articles_dir, progress)

    # Save cowork queue if any
    if cowork_queue:
        progress["cowork_queue"] = cowork_queue
    save_progress(articles_dir, progress)

    # Save cowork queue as separate file for easy pickup
    if cowork_queue:
        cowork_path = articles_dir / "cowork-queue.json"
        cowork_path.write_text(json.dumps({
            "niche": niche_slug,
            "slugs": cowork_queue,
            "reason": "DeepSeek V4 Flash failed or truncated -- Cowork generates these at $0 cost",
        }, indent=2), encoding="utf-8")

    elapsed = time.time() - start_time
    print(f"\n{'-'*40}")
    print(f"  RESULTS: {niche_name}")
    print(f"  Success:     {success} (DeepSeek V4 Flash)")
    print(f"  Cowork queue: {needs_cowork} (free fallback)")
    print(f"  Skipped:     {skipped}")
    print(f"  Failed:      {failed}")
    print(f"  Time:        {elapsed:.0f}s ({elapsed/max(success,1):.1f}s/article)")
    print(f"  Tokens:      {total_input:,} in / {total_output:,} out")
    print(f"  Models:      {models_used}")

    # Cost estimate (DeepSeek V4 Flash via OpenRouter -- Cowork fallback is $0)
    ds_in = total_input * 0.14 / 1_000_000
    ds_out = total_output * 0.28 / 1_000_000
    print(f"  Est cost:    ${ds_in + ds_out:.4f} (DeepSeek V4 Flash -- Cowork = $0)")
    if cowork_queue:
        print(f"  Cowork TODO: {len(cowork_queue)} articles saved to cowork-queue.json")
    print(f"{'-'*40}")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/article_generator.py <niche-slug> [--limit N]")
        print("       python scripts/article_generator.py --all [--limit N]")
        sys.exit(1)

    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    if sys.argv[1] == "--all":
        niches = ALL_NICHES
    else:
        niches = [sys.argv[1]]

    for niche in niches:
        niche_dir = get_niche_dir(niche)
        if not niche_dir.exists():
            print(f"SKIP: {niche} -- directory not found")
            continue
        await run_niche(niche, limit)

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
