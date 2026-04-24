#!/usr/bin/env python3
"""
link-mapper.py — Pre-compute internal links between informational and roundup articles.

Usage:
    python scripts/link-mapper.py <niche-slug>       # Single niche
    python scripts/link-mapper.py --all               # All 14 niches

Output:
    outputs/<niche>/link-map.json

Maps each informational article slug to 2-3 related roundup article slugs
based on cluster proximity in the authority map.
"""

import json
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    OUTPUTS_DIR, ALL_NICHES, INFO_CATEGORIES, ROUNDUP_CATEGORIES,
    get_niche_dir, NICHE_NAMES,
)


def parse_title_line(line: str) -> dict | None:
    """Parse a ZimmWriter format title line."""
    line = line.strip()
    if not line or line.startswith("===") or line.startswith("#"):
        return None
    m_sl = re.search(r'\{slug=([^}]+)\}', line)
    m_ca = re.search(r'\{category=([^}]+)\}', line)
    title = line.split('{')[0].strip()
    if not title:
        return None
    return {
        "title": title,
        "slug": m_sl.group(1) if m_sl else title.lower().replace(" ", "-")[:50],
        "category": m_ca.group(1) if m_ca else "Unknown",
    }


def load_titles(filepath: Path) -> list[dict]:
    """Load and parse all titles from a file."""
    if not filepath.exists():
        return []
    entries = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        parsed = parse_title_line(line)
        if parsed:
            entries.append(parsed)
    return entries


def parse_authority_map(filepath: Path) -> dict[str, list[str]]:
    """
    Parse authority-map.txt into clusters.
    Returns: {cluster_name: [slug1, slug2, ...]}
    """
    if not filepath.exists():
        return {}

    clusters = {}
    current_cluster = None
    text = filepath.read_text(encoding="utf-8")

    for line in text.splitlines():
        line_stripped = line.strip()
        # Detect cluster headers like "CLUSTER 1: DOG BEDS (Core)"
        cluster_match = re.match(r'CLUSTER\s+\d+:\s*(.+)', line_stripped, re.IGNORECASE)
        if cluster_match:
            current_cluster = cluster_match.group(1).strip()
            clusters[current_cluster] = []
            continue

        # Detect spoke entries like "-> Best Large Dog Bed large-dog-bed"
        spoke_match = re.match(r'\s*->\s+.+?\s+([a-z0-9-]+)\s', line_stripped)
        if not spoke_match:
            # Try: "-> Title slug (vol, KD)" format
            spoke_match = re.match(r'\s*->\s+(.+?)\s+([a-z][a-z0-9-]+)\s+\(', line_stripped)
        if spoke_match and current_cluster:
            slug = spoke_match.group(spoke_match.lastindex)
            clusters[current_cluster].append(slug)
            continue

        # Detect hub entries like "HUB: Dog Bed Types & Styles best-dog-bed"
        hub_match = re.match(r'\s*HUB:\s+.+?\s+([a-z0-9-]+)', line_stripped)
        if hub_match and current_cluster:
            clusters[current_cluster].append(hub_match.group(1))

    return clusters


def keyword_overlap(slug_a: str, slug_b: str) -> float:
    """Score how related two slugs are by word overlap."""
    words_a = set(slug_a.split("-"))
    words_b = set(slug_b.split("-"))
    # Remove common stop-ish words from comparison
    stop = {"how", "to", "what", "is", "are", "best", "top", "for", "the", "a", "and", "or"}
    words_a -= stop
    words_b -= stop
    if not words_a or not words_b:
        return 0.0
    overlap = words_a & words_b
    return len(overlap) / min(len(words_a), len(words_b))


def title_similarity(title_a: str, title_b: str) -> float:
    """Score title similarity using SequenceMatcher."""
    return SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()


def find_related_roundups(
    info_entry: dict,
    roundup_entries: list[dict],
    clusters: dict[str, list[str]],
    max_links: int = 3,
) -> list[dict]:
    """
    Find the best 2-3 roundup articles to link from an informational article.

    Strategy:
    1. Same cluster matches (highest priority)
    2. Slug keyword overlap
    3. Title similarity as tiebreaker
    """
    info_slug = info_entry["slug"]
    info_title = info_entry["title"]

    # Find which cluster this info article belongs to
    info_cluster = None
    for cluster_name, slugs in clusters.items():
        if info_slug in slugs:
            info_cluster = cluster_name
            break

    scored = []
    for roundup in roundup_entries:
        r_slug = roundup["slug"]
        r_title = roundup["title"]

        # Score components
        same_cluster = 0.0
        if info_cluster:
            for cluster_name, slugs in clusters.items():
                if r_slug in slugs and cluster_name == info_cluster:
                    same_cluster = 1.0
                    break

        slug_score = keyword_overlap(info_slug, r_slug)
        title_score = title_similarity(info_title, r_title)

        # Weighted composite
        total = (same_cluster * 3.0) + (slug_score * 2.0) + (title_score * 1.0)
        if total > 0.1:  # Skip completely unrelated
            scored.append({
                "slug": r_slug,
                "title": r_title,
                "score": round(total, 3),
            })

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_links]


def build_link_map(niche_slug: str) -> dict:
    """Build the complete link map for a niche."""
    niche_dir = get_niche_dir(niche_slug)

    # Load titles
    info_entries = load_titles(niche_dir / "informational-titles.txt")
    roundup_entries = load_titles(niche_dir / "roundup-titles.txt")

    if not info_entries:
        print(f"  WARNING: No informational titles found for {niche_slug}")
        return {}
    if not roundup_entries:
        print(f"  WARNING: No roundup titles found for {niche_slug}")
        return {}

    # Parse authority map for cluster context
    clusters = parse_authority_map(niche_dir / "authority-map.txt")

    # Build map
    link_map = {}
    for info in info_entries:
        related = find_related_roundups(info, roundup_entries, clusters)
        if related:
            link_map[info["slug"]] = [
                {"slug": r["slug"], "title": r["title"]}
                for r in related
            ]
        else:
            # Fallback: grab the top 2 roundups by title similarity alone
            fallback = sorted(
                roundup_entries,
                key=lambda r: title_similarity(info["title"], r["title"]),
                reverse=True,
            )[:2]
            link_map[info["slug"]] = [
                {"slug": r["slug"], "title": r["title"]}
                for r in fallback
            ]

    return link_map


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/link-mapper.py <niche-slug>")
        print("       python scripts/link-mapper.py --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        niches = ALL_NICHES
    else:
        niches = [sys.argv[1]]

    for niche in niches:
        niche_dir = get_niche_dir(niche)
        if not niche_dir.exists():
            print(f"SKIP: {niche} — directory not found")
            continue

        name = NICHE_NAMES.get(niche, niche)
        print(f"\n{'='*50}")
        print(f"LINK MAP: {name}")
        print(f"{'='*50}")

        link_map = build_link_map(niche)
        output_path = niche_dir / "link-map.json"
        output_path.write_text(
            json.dumps(link_map, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Stats
        total_info = len(link_map)
        avg_links = sum(len(v) for v in link_map.values()) / max(total_info, 1)
        no_links = sum(1 for v in link_map.values() if not v)

        print(f"  Info articles: {total_info}")
        print(f"  Avg links/article: {avg_links:.1f}")
        print(f"  Articles with no links: {no_links}")
        print(f"  Saved: {output_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
