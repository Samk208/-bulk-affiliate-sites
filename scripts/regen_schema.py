#!/usr/bin/env python3
"""regen_schema.py -- Regenerate JSON-LD schema for existing articles
using the current entity library.

Run after entity_library.py changes to pick up new QIDs, renamed entities,
and corrected sameAs URLs in the about/mentions blocks.

Usage:
    python scripts/regen_schema.py <niche-slug>
    python scripts/regen_schema.py --all
    python scripts/regen_schema.py <niche-slug> --dry-run
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_NICHES, NICHE_NAMES, get_articles_dir
from article_template import build_schema


H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.DOTALL)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def extract_title(html: str) -> str:
    m = H1_RE.search(html)
    return TAG_RE.sub("", m.group(1)).strip() if m else ""


def extract_description(html: str, existing: dict) -> str:
    if existing and existing.get("description"):
        return existing["description"]
    m = P_RE.search(html)
    return TAG_RE.sub("", m.group(1)).strip()[:160] if m else ""


def infer_category(slug: str) -> str:
    s = slug.lower()
    if "how-to" in s or s.startswith("how-"):
        return "How-To Guides"
    if "best-" in s or "top-" in s:
        return "Best Products"
    if "review" in s:
        return "Reviews"
    if "-vs-" in s or "compare" in s or "comparison" in s:
        return "Comparisons"
    if "guide" in s:
        return "Buying Guides"
    return "Tips & Care"


def load_existing(schema_path: Path) -> dict:
    if not schema_path.exists():
        return {}
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return {}


def count_about(schema) -> int:
    root = schema[0] if isinstance(schema, list) else schema
    return len(root.get("about", []))


def regen_niche(niche_slug: str, dry_run: bool = False) -> tuple[int, int]:
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    articles_dir = get_articles_dir(niche_slug)
    html_files = sorted(articles_dir.glob("*.html"))
    if not html_files:
        print(f"  No articles in {articles_dir}")
        return 0, 0

    mode = "DRY" if dry_run else "APPLY"
    print(f"\n{'=' * 50}")
    print(f"REGEN SCHEMA: {niche_name} ({len(html_files)} articles)")
    print(f"Mode: {mode}")
    print(f"{'=' * 50}")

    regenerated = 0
    total_entities = 0
    for html_path in html_files:
        slug = html_path.stem
        html = html_path.read_text(encoding="utf-8")
        title = extract_title(html) or slug.replace("-", " ").title()
        schema_path = html_path.with_suffix(".json")
        existing = load_existing(schema_path)
        description = extract_description(html, existing)
        category = infer_category(slug)

        new_schema = build_schema(
            title=title,
            slug=slug,
            category=category,
            description=description,
            html_content=html,
            niche_name=niche_name,
            niche_slug=niche_slug,
        )

        if not dry_run:
            schema_path.write_text(
                json.dumps(new_schema, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        n_about = count_about(new_schema)
        total_entities += n_about
        regenerated += 1

    avg = total_entities / regenerated if regenerated else 0
    print(f"  Regenerated: {regenerated}/{len(html_files)} schemas")
    print(f"  Avg about-entities: {avg:.1f} per article")
    return regenerated, total_entities


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/regen_schema.py <niche-slug|--all> [--dry-run]")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    target = sys.argv[1]

    if target == "--all":
        totals = [0, 0]
        for niche in ALL_NICHES:
            r, t = regen_niche(niche, dry_run)
            totals[0] += r
            totals[1] += t
        print(f"\n{'=' * 50}")
        print(f"TOTAL: {totals[0]} schemas regenerated, {totals[1]} about-entities")
        print(f"{'=' * 50}")
    else:
        regen_niche(target, dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
