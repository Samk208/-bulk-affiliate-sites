#!/usr/bin/env python3
"""
wp_push_drafts.py -- Push articles to WordPress as drafts via REST API.

Usage:
    python scripts/wp_push_drafts.py <niche-slug>                    # Push all articles
    python scripts/wp_push_drafts.py <niche-slug> --slugs a,b,c      # Push specific slugs
    python scripts/wp_push_drafts.py <niche-slug> --limit 5           # Push first N
    python scripts/wp_push_drafts.py <niche-slug> --dry-run           # Preview without posting

Requires: LocalWP running at localhost:10040 with REST API enabled.
Credentials from .env.wp in project root.
"""

import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import NICHE_NAMES, get_articles_dir, PROJECT_ROOT

# -- WordPress config -------------------------------------------------------

WP_URL = "http://localhost:10040"
WP_API = f"{WP_URL}/wp-json/wp/v2"

# Load credentials from .env.wp
_env_wp = PROJECT_ROOT / ".env.wp"
WP_USER = ""
WP_APP_PASSWORD = ""
if _env_wp.exists():
    for line in _env_wp.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k == "WP_USER":
            WP_USER = v
        elif k == "WP_APP_PASSWORD":
            WP_APP_PASSWORD = v

if not WP_USER or not WP_APP_PASSWORD:
    # Fallback to hardcoded (from CLAUDE.md)
    WP_USER = "skonneh18"
    WP_APP_PASSWORD = "Q4Ab UFTA Jk90 nPO2 Sbaz mJDG"


def get_or_create_category(name: str, session: requests.Session) -> int:
    """Get category ID by name, or create it."""
    resp = session.get(f"{WP_API}/categories", params={"search": name, "per_page": 10})
    if resp.ok:
        for cat in resp.json():
            if cat["name"].lower() == name.lower():
                return cat["id"]
    # Create
    resp = session.post(f"{WP_API}/categories", json={"name": name})
    if resp.ok:
        return resp.json()["id"]
    return 0


def extract_title_from_html(html: str) -> str:
    """Try to extract title from HTML content."""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def extract_excerpt(html: str) -> str:
    """Extract first paragraph as excerpt."""
    m = re.search(r"<p>(.*?)</p>", html, re.DOTALL)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        return text[:300]
    return ""


def push_article(html_path: Path, schema_path: Path, category_name: str,
                 session: requests.Session, dry_run: bool = False) -> dict:
    """Push a single article to WordPress as a draft."""
    slug = html_path.stem
    html = html_path.read_text(encoding="utf-8")

    # Title from filename or HTML
    title = extract_title_from_html(html) or slug.replace("-", " ").title()
    excerpt = extract_excerpt(html)

    # Load JSON-LD schema if exists
    schema_block = ""
    if schema_path.exists():
        try:
            schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
            schema_json = json.dumps(schema_data, ensure_ascii=False)
            schema_block = f'\n<script type="application/ld+json">\n{schema_json}\n</script>'
        except json.JSONDecodeError:
            pass

    # Full content = article HTML + schema
    content = html + schema_block

    if dry_run:
        print(f"  [DRY] {slug} -- {title[:60]} ({len(html)} chars, cat={category_name})")
        return {"slug": slug, "status": "dry_run"}

    # Get/create category
    cat_id = get_or_create_category(category_name, session)

    post_data = {
        "title": title,
        "slug": slug,
        "content": content,
        "excerpt": excerpt,
        "status": "draft",
        "categories": [cat_id] if cat_id else [],
    }

    resp = session.post(f"{WP_API}/posts", json=post_data)
    if resp.ok:
        post = resp.json()
        print(f"  [OK] {slug} -- ID={post['id']} ({title[:50]})")
        return {"slug": slug, "id": post["id"], "status": "created", "link": post["link"]}
    else:
        error = resp.text[:200]
        print(f"  [FAIL] {slug} -- {resp.status_code}: {error}")
        return {"slug": slug, "status": "failed", "error": error}


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/wp_push_drafts.py <niche-slug> [--slugs a,b,c] [--limit N] [--dry-run]")
        sys.exit(1)

    niche_slug = sys.argv[1]
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    articles_dir = get_articles_dir(niche_slug)
    dry_run = "--dry-run" in sys.argv

    # Filter options
    specific_slugs = None
    limit = None
    if "--slugs" in sys.argv:
        idx = sys.argv.index("--slugs")
        specific_slugs = sys.argv[idx + 1].split(",")
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])

    # Find articles
    html_files = sorted(articles_dir.glob("*.html"))
    if specific_slugs:
        html_files = [f for f in html_files if f.stem in specific_slugs]
    if limit:
        html_files = html_files[:limit]

    if not html_files:
        print(f"No articles found in {articles_dir}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"PUSH TO WORDPRESS: {niche_name} ({len(html_files)} articles)")
    print(f"Target: {WP_URL}")
    print(f"Status: draft")
    if dry_run:
        print("MODE: DRY RUN (no actual posts)")
    print(f"{'='*60}")

    # Map slug to category from titles file
    slug_categories = {}
    titles_path = articles_dir.parent / "titles-v2.txt"
    if not titles_path.exists():
        titles_path = articles_dir.parent / "informational-titles.txt"
    if titles_path.exists():
        for line in titles_path.read_text(encoding="utf-8").splitlines():
            m_sl = re.search(r"\{slug=([^}]+)\}", line)
            m_ca = re.search(r"\{category=([^}]+)\}", line)
            if m_sl and m_ca:
                slug_categories[m_sl.group(1)] = m_ca.group(1)

    session = requests.Session()
    session.auth = (WP_USER, WP_APP_PASSWORD)

    # Test connection
    if not dry_run:
        try:
            resp = session.get(f"{WP_API}/posts?per_page=1")
            if not resp.ok:
                print(f"ERROR: Cannot connect to WordPress API ({resp.status_code})")
                print(f"Is LocalWP running at {WP_URL}?")
                sys.exit(1)
        except requests.ConnectionError:
            print(f"ERROR: Cannot connect to {WP_URL}")
            print("Start LocalWP first.")
            sys.exit(1)

    results = []
    for html_path in html_files:
        schema_path = html_path.with_suffix(".json")
        category = slug_categories.get(html_path.stem, "Uncategorized")
        result = push_article(html_path, schema_path, category, session, dry_run)
        results.append(result)

    created = sum(1 for r in results if r["status"] == "created")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"\n{'-'*40}")
    print(f"  Created: {created}")
    print(f"  Failed:  {failed}")
    if not dry_run and created:
        print(f"  View at: {WP_URL}/wp-admin/edit.php?post_status=draft")
    print(f"{'-'*40}")


if __name__ == "__main__":
    main()
