#!/usr/bin/env python3
"""Post sample articles to LocalWP test site as drafts via REST API."""

import json
import re
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# LocalWP config
WP_URL = "http://localhost:10040"
WP_USER = "skonneh18"
WP_APP_PASS = "VMjn J9Th bBLb 4JeI qIU5 wU6w"

ARTICLES_DIR = Path(__file__).parent.parent / "outputs" / "dog-comfort" / "articles"
TITLES_PATH = Path(__file__).parent.parent / "outputs" / "dog-comfort" / "informational-titles.txt"

# Pick 8 articles: 3 early, 2 middle, 3 end
SAMPLE_SLUGS = [
    # Early
    "best-dog-training-methods",
    "best-sleeping-position-dogs",
    "crate-training-night",
    # Middle
    "how-deodorize-dog-bed",
    "how-help-dog-lose-weight",
    # End
    "why-dog-stretches-after-sleep",
    "why-dogs-sleep-owner-feet",
    "why-separation-anxiety-causes",
]

# Category mapping
CATEGORY_MAP = {
    "How-To Guides": None,
    "Tips & Care": None,
    "Best Products": None,
    "Reviews": None,
    "Buying Guides": None,
    "Comparisons": None,
}


def parse_title_line(line):
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
        "slug": m_sl.group(1) if m_sl else "",
        "category": m_ca.group(1) if m_ca else "Tips & Care",
    }


def get_or_create_category(name, session):
    """Get category ID, create if doesn't exist."""
    if CATEGORY_MAP.get(name):
        return CATEGORY_MAP[name]

    # Check if exists
    r = session.get(f"{WP_URL}/wp-json/wp/v2/categories", params={"search": name})
    if r.ok and r.json():
        cat_id = r.json()[0]["id"]
        CATEGORY_MAP[name] = cat_id
        return cat_id

    # Create
    slug = name.lower().replace(" ", "-").replace("&", "and")
    r = session.post(f"{WP_URL}/wp-json/wp/v2/categories", json={"name": name, "slug": slug})
    if r.ok:
        cat_id = r.json()["id"]
        CATEGORY_MAP[name] = cat_id
        return cat_id

    print(f"  Failed to create category '{name}': {r.text[:100]}")
    return None


def main():
    # Load title metadata
    title_meta = {}
    if TITLES_PATH.exists():
        for line in TITLES_PATH.read_text(encoding="utf-8").splitlines():
            parsed = parse_title_line(line)
            if parsed:
                title_meta[parsed["slug"]] = parsed

    # Setup session with auth
    session = requests.Session()
    session.auth = (WP_USER, WP_APP_PASS)

    print(f"Posting {len(SAMPLE_SLUGS)} sample articles to {WP_URL} as drafts...\n")

    posted = 0
    for slug in SAMPLE_SLUGS:
        html_path = ARTICLES_DIR / f"{slug}.html"
        schema_path = ARTICLES_DIR / f"{slug}.json"

        if not html_path.exists():
            print(f"  SKIP: {slug} — file not found")
            continue

        # Get metadata
        meta = title_meta.get(slug, {"title": slug.replace("-", " ").title(), "category": "Tips & Care"})
        html_content = html_path.read_text(encoding="utf-8")

        # Embed schema if exists
        if schema_path.exists():
            schema = schema_path.read_text(encoding="utf-8")
            html_content += f'\n\n<script type="application/ld+json">\n{schema}\n</script>'

        # Get/create category
        cat_id = get_or_create_category(meta["category"], session)

        # Create post as draft
        post_data = {
            "title": meta["title"],
            "content": html_content,
            "slug": slug,
            "status": "draft",
            "categories": [cat_id] if cat_id else [],
        }

        r = session.post(f"{WP_URL}/wp-json/wp/v2/posts", json=post_data)
        if r.ok:
            post = r.json()
            posted += 1
            print(f"  [{posted}] {meta['title']}")
            print(f"       ID: {post['id']} | Category: {meta['category']} | Status: draft")
            print(f"       Preview: {WP_URL}/?p={post['id']}&preview=true")
        else:
            print(f"  FAILED: {slug} — {r.status_code}: {r.text[:100]}")

    print(f"\nDone. {posted} articles posted as drafts.")
    print(f"View all: {WP_URL}/wp-admin/edit.php")


if __name__ == "__main__":
    main()
