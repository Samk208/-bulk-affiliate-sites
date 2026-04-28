#!/usr/bin/env python3
"""
serp_dataforseo.py -- Real SERP data via DataForSEO API.

Pulls live Google SERP for each article title:
- Top 10 organic results (position, URL, title, snippet)
- SERP features present (Featured Snippet, PAA, Knowledge Graph, etc.)
- People Also Ask questions (up to 8)

This gives Kimi K2.5 real competitor context to beat, not just
Perplexity's summary. Costs ~$0.003/keyword.

Usage:
    python scripts/serp_dataforseo.py <niche-slug>              # Full niche
    python scripts/serp_dataforseo.py <niche-slug> --limit 5    # Test batch
    python scripts/serp_dataforseo.py --all                      # All niches

Output:
    outputs/<niche>/serp-dataforseo.json
"""

import asyncio
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ALL_NICHES, NICHE_NAMES, RETRY_ATTEMPTS, RETRY_DELAY,
    get_niche_dir,
)

# -- DataForSEO credentials (loaded from .env.cowork by config.py) ----------
DFS_LOGIN    = os.environ.get("DATAFORSEO_LOGIN", "")
DFS_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "")
DFS_BASE_URL = "https://api.dataforseo.com/v3"

# -- API settings -----------------------------------------------------------
LOCATION_CODE  = 2840   # United States
LANGUAGE_CODE  = "en"
DEPTH          = 10     # Top 10 organic results
MAX_CONCURRENT = 3      # DataForSEO rate: ~5 rps on live endpoint
COST_PER_TASK  = 0.003  # USD per live/advanced SERP task (DataForSEO pricing)


def _auth_header() -> dict:
    token = base64.b64encode(f"{DFS_LOGIN}:{DFS_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


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


def _extract_serp_data(items: list) -> dict:
    """Parse DataForSEO items array into structured SERP snapshot."""
    organic = []
    paa_questions = []
    serp_features = []

    for item in items:
        item_type = item.get("type", "")

        if item_type == "organic":
            organic.append({
                "position": item.get("rank_absolute", 0),
                "url":      item.get("url", ""),
                "title":    item.get("title", ""),
                "snippet":  (item.get("description") or item.get("snippet") or "").strip(),
            })

        elif item_type == "featured_snippet":
            serp_features.append("featured_snippet")

        elif item_type == "people_also_ask":
            serp_features.append("people_also_ask")
            for q_item in item.get("items", []) or []:
                q = q_item.get("title") or q_item.get("question") or ""
                if q and q not in paa_questions:
                    paa_questions.append(q)

        elif item_type == "knowledge_graph":
            serp_features.append("knowledge_graph")

        elif item_type == "local_pack":
            serp_features.append("local_pack")

        elif item_type == "video":
            serp_features.append("video_carousel")

        elif item_type == "images":
            serp_features.append("image_pack")

        elif item_type == "top_stories":
            serp_features.append("top_stories")

    # Deduplicate features
    serp_features = list(dict.fromkeys(serp_features))

    return {
        "organic":       organic[:10],
        "paa_questions": paa_questions[:8],
        "serp_features": serp_features,
    }


async def fetch_serp(keyword: str, semaphore: asyncio.Semaphore) -> dict:
    """Fetch live SERP for one keyword via DataForSEO."""
    payload = [{
        "keyword":       keyword,
        "location_code": LOCATION_CODE,
        "language_code": LANGUAGE_CODE,
        "device":        "desktop",
        "depth":         DEPTH,
    }]

    async with semaphore:
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(1, RETRY_ATTEMPTS + 1):
                try:
                    resp = await client.post(
                        f"{DFS_BASE_URL}/serp/google/organic/live/advanced",
                        headers=_auth_header(),
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    # Check API-level status
                    status_code = data.get("status_code")
                    if status_code != 20000:
                        msg = data.get("status_message", "unknown error")
                        if attempt < RETRY_ATTEMPTS:
                            await asyncio.sleep(RETRY_DELAY * attempt)
                            continue
                        return {"error": f"API status {status_code}: {msg}"}

                    # Navigate to items
                    tasks = data.get("tasks", [])
                    if not tasks:
                        return {"error": "no tasks in response"}

                    task = tasks[0]
                    task_status = task.get("status_code")
                    if task_status != 20000:
                        return {"error": f"task status {task_status}: {task.get('status_message')}"}

                    result = (task.get("result") or [{}])[0]
                    items = result.get("items", []) or []
                    total_results = result.get("se_results_count", 0)

                    extracted = _extract_serp_data(items)
                    extracted["total_results"] = total_results
                    return extracted

                except httpx.HTTPStatusError as e:
                    if attempt < RETRY_ATTEMPTS:
                        await asyncio.sleep(RETRY_DELAY * attempt)
                    else:
                        return {"error": f"HTTP {e.response.status_code}: {str(e)[:80]}"}
                except Exception as e:
                    if attempt < RETRY_ATTEMPTS:
                        await asyncio.sleep(RETRY_DELAY * attempt)
                    else:
                        return {"error": str(e)[:120]}

    return {"error": "max retries exhausted"}


async def run_niche(niche_slug: str, limit: int | None = None):
    """Fetch SERP data for all titles in a niche."""
    if not DFS_LOGIN or not DFS_PASSWORD:
        print("ERROR: DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD not set in .env.cowork")
        return

    niche_dir = get_niche_dir(niche_slug)
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)

    print(f"\n{'='*60}")
    print(f"DataForSEO SERP FETCH: {niche_name}")
    print(f"Location: US (2840) | Language: en | Depth: {DEPTH}")
    print(f"{'='*60}")

    # Load title file
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

    # Load existing data to skip already-fetched slugs
    output_path = niche_dir / "serp-dataforseo.json"
    existing = {}
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))

    to_fetch = [e for e in entries if e["slug"] not in existing]
    print(f"  Total titles:       {len(entries)}")
    print(f"  Already fetched:    {len(entries) - len(to_fetch)}")
    print(f"  To fetch:           {len(to_fetch)}")
    print(f"  Est cost:           ${len(to_fetch) * COST_PER_TASK:.2f}")

    if not to_fetch:
        print("  All titles already fetched. Skipping.")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    start_time = time.time()
    success = 0
    failed = 0

    for i, entry in enumerate(to_fetch):
        result = await fetch_serp(entry["title"], semaphore)

        if "error" in result:
            failed += 1
            print(f"  [{i+1}/{len(to_fetch)}] {entry['slug'][:50]} -- ERROR: {result['error'][:60]}")
        else:
            success += 1
            organic_count = len(result.get("organic", []))
            paa_count = len(result.get("paa_questions", []))
            features = ", ".join(result.get("serp_features", [])) or "none"
            print(f"  [{i+1}/{len(to_fetch)}] {entry['slug'][:50]} -- {organic_count} results, {paa_count} PAA, [{features}]")

            existing[entry["slug"]] = {
                "title":         entry["title"],
                "keyword":       entry["title"],
                "organic":       result["organic"],
                "paa_questions": result["paa_questions"],
                "serp_features": result["serp_features"],
                "total_results": result.get("total_results", 0),
            }

        # Save every 10
        if (success + failed) % 10 == 0:
            output_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    # Final save
    output_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    elapsed = time.time() - start_time
    cost = success * COST_PER_TASK

    print(f"\n{'-'*40}")
    print(f"  RESULTS: {niche_name}")
    print(f"  Fetched:     {success}")
    print(f"  Failed:      {failed}")
    print(f"  Time:        {elapsed:.0f}s ({elapsed / max(success, 1):.1f}s/keyword)")
    print(f"  Cost:        ${cost:.3f}")
    print(f"  Saved:       {output_path}")
    print(f"{'-'*40}")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/serp_dataforseo.py <niche-slug> [--limit N]")
        print("       python scripts/serp_dataforseo.py --all [--limit N]")
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
