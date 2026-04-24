#!/usr/bin/env python3
"""
wp_importer.py -- Generate WordPress WXR (XML) import files with drip-feed scheduling.

Posts are scheduled 2-3 per day starting from a configurable launch date.
WordPress auto-publishes at each scheduled time (post_status=future).

Usage:
    python scripts/wp_importer.py <niche-slug>                        # Default: starts tomorrow
    python scripts/wp_importer.py <niche-slug> --start 2026-05-01     # Custom start date
    python scripts/wp_importer.py <niche-slug> --pace 3               # 3 posts/day
    python scripts/wp_importer.py <niche-slug> --draft                # All as drafts (no scheduling)
    python scripts/wp_importer.py --all                                # All niches

Output:
    outputs/<niche>/wp-import-<niche>.xml

Import with: wp import wp-import-<niche>.xml --authors=create
"""

import json
import re
import sys
import html
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ALL_NICHES, NICHE_NAMES, CATEGORY_SLUGS,
    get_niche_dir, get_articles_dir,
)

# -- Drip-feed schedule config -------------------------------------------

DEFAULT_POSTS_PER_DAY = 2       # 2-3 posts/day balanced cadence
PUBLISH_HOURS = [8, 11, 15]     # Spread across US timezones (EST morning, lunch, afternoon)
SKIP_SUNDAYS = True             # Real sites rarely publish on Sundays


LAUNCH_BATCH_SIZE = 20  # First N posts published immediately on day 1


def generate_schedule(num_posts: int, start_date: datetime, posts_per_day: int = DEFAULT_POSTS_PER_DAY) -> list[datetime]:
    """
    Generate a drip-feed publishing schedule with launch batch.

    Strategy:
    - Day 1: Publish first 20 articles immediately (site launch batch)
    - Day 2+: Drip-feed 2-3 per day, skipping Sundays

    Returns list of datetime objects, one per post.
    """
    schedule = []
    post_idx = 0

    # PHASE 1: Launch batch — first 20 articles on day 1
    launch_count = min(LAUNCH_BATCH_SIZE, num_posts)
    for i in range(launch_count):
        # Stagger across 6am-6pm on launch day (1 every ~36 min for 20 posts)
        hour = 6 + (i * 12 // launch_count)
        minute = random.randint(0, 55)
        publish_time = start_date.replace(hour=hour, minute=minute, second=0)
        schedule.append(publish_time)
        post_idx += 1

    # PHASE 2: Drip-feed remaining articles at 2-3/day
    current_date = start_date + timedelta(days=1)

    while post_idx < num_posts:
        # Skip Sundays
        if SKIP_SUNDAYS and current_date.weekday() == 6:
            current_date += timedelta(days=1)
            continue

        # Vary between posts_per_day and posts_per_day+1 for natural feel
        today_count = posts_per_day if random.random() < 0.6 else posts_per_day + 1
        today_count = min(today_count, num_posts - post_idx)

        # Pick publish hours for today
        hours = random.sample(PUBLISH_HOURS, min(today_count, len(PUBLISH_HOURS)))
        hours.sort()

        for h in hours[:today_count]:
            minute = random.randint(0, 55)
            publish_time = current_date.replace(hour=h, minute=minute, second=0)
            schedule.append(publish_time)
            post_idx += 1

        current_date += timedelta(days=1)

    return schedule


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


def build_wxr(niche_slug: str, articles: list[dict], schedule: list[datetime] | None = None, use_draft: bool = False) -> str:
    """Build a WordPress WXR XML file with optional drip-feed scheduling."""
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Collect categories
    categories = set()
    for a in articles:
        categories.add(a["category"])

    cat_xml = ""
    for cat in sorted(categories):
        cat_slug = CATEGORY_SLUGS.get(cat, cat.lower().replace(" ", "-").replace("&", "and"))
        cat_xml += f"""    <wp:category>
      <wp:term_id>0</wp:term_id>
      <wp:category_nicename><![CDATA[{cat_slug}]]></wp:category_nicename>
      <wp:category_parent></wp:category_parent>
      <wp:cat_name><![CDATA[{cat}]]></wp:cat_name>
    </wp:category>\n"""

    items_xml = ""
    for i, article in enumerate(articles):
        title_escaped = escape(article["title"])
        slug = article["slug"]
        category = article["category"]
        cat_slug = CATEGORY_SLUGS.get(category, category.lower().replace(" ", "-").replace("&", "and"))
        content = article["html_content"]
        schema_json = article.get("schema_content", "")

        if schema_json:
            content += f'\n\n<script type="application/ld+json">\n{schema_json}\n</script>'

        meta_desc = article.get("outline_focus", "")[:160]

        # Determine post status and date
        if use_draft or schedule is None:
            post_status = "draft"
            post_date = now_str
        else:
            post_status = "future"
            post_date = schedule[i].strftime("%Y-%m-%d %H:%M:%S")

        items_xml += f"""    <item>
      <title>{title_escaped}</title>
      <link>/{slug}/</link>
      <pubDate>{post_date}</pubDate>
      <dc:creator><![CDATA[samkonneh]]></dc:creator>
      <guid isPermaLink="false">/{slug}/</guid>
      <description></description>
      <content:encoded><![CDATA[{content}]]></content:encoded>
      <excerpt:encoded><![CDATA[{html.escape(meta_desc)}]]></excerpt:encoded>
      <wp:post_id>{i + 1}</wp:post_id>
      <wp:post_date>{post_date}</wp:post_date>
      <wp:post_date_gmt>{post_date}</wp:post_date_gmt>
      <wp:post_modified>{post_date}</wp:post_modified>
      <wp:post_modified_gmt>{post_date}</wp:post_modified_gmt>
      <wp:comment_status>closed</wp:comment_status>
      <wp:ping_status>closed</wp:ping_status>
      <wp:post_name><![CDATA[{slug}]]></wp:post_name>
      <wp:status>{post_status}</wp:status>
      <wp:post_parent>0</wp:post_parent>
      <wp:menu_order>0</wp:menu_order>
      <wp:post_type>post</wp:post_type>
      <wp:post_password></wp:post_password>
      <wp:is_sticky>0</wp:is_sticky>
      <category domain="category" nicename="{cat_slug}"><![CDATA[{category}]]></category>
      <wp:postmeta>
        <wp:meta_key>rank_math_focus_keyword</wp:meta_key>
        <wp:meta_value><![CDATA[{article["title"].lower()}]]></wp:meta_value>
      </wp:postmeta>
      <wp:postmeta>
        <wp:meta_key>rank_math_description</wp:meta_key>
        <wp:meta_value><![CDATA[{meta_desc}]]></wp:meta_value>
      </wp:postmeta>
    </item>\n"""

    wxr = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"
  xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:wfw="http://wellformedweb.org/CommentAPI/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:wp="http://wordpress.org/export/1.2/"
>
  <channel>
    <title>{escape(niche_name)}</title>
    <link>https://example.com</link>
    <description>{escape(niche_name)} - Informational Articles</description>
    <language>en-US</language>
    <wp:wxr_version>1.2</wp:wxr_version>
    <wp:base_site_url>https://example.com</wp:base_site_url>
    <wp:base_blog_url>https://example.com</wp:base_blog_url>
    <wp:author>
      <wp:author_id>1</wp:author_id>
      <wp:author_login><![CDATA[samkonneh]]></wp:author_login>
      <wp:author_email><![CDATA[admin@example.com]]></wp:author_email>
      <wp:author_display_name><![CDATA[Sam Konneh]]></wp:author_display_name>
    </wp:author>
{cat_xml}
{items_xml}
  </channel>
</rss>"""

    return wxr


def generate_import(niche_slug: str, start_date: datetime | None = None, posts_per_day: int = DEFAULT_POSTS_PER_DAY, use_draft: bool = False):
    """Generate WXR import file for a niche with drip-feed scheduling."""
    niche_dir = get_niche_dir(niche_slug)
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    articles_dir = get_articles_dir(niche_slug)

    # Load title metadata
    titles_path = niche_dir / "informational-titles.txt"
    if not titles_path.exists():
        print(f"  ERROR: {titles_path} not found")
        return

    title_entries = {}
    for line in titles_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_title_line(line)
        if parsed:
            title_entries[parsed["slug"]] = parsed

    # Match with generated HTML files
    html_files = sorted(articles_dir.glob("*.html"))
    if not html_files:
        print(f"  No articles found in {articles_dir}")
        return

    print(f"\n{'='*50}")
    print(f"WP IMPORT: {niche_name}")
    print(f"{'='*50}")

    articles = []
    for html_path in html_files:
        slug = html_path.stem
        schema_path = html_path.with_suffix(".json")

        meta = title_entries.get(slug, {
            "title": slug.replace("-", " ").title(),
            "outline_focus": "",
            "category": "Tips & Care",
        })

        html_content = html_path.read_text(encoding="utf-8")
        schema_content = ""
        if schema_path.exists():
            schema_content = schema_path.read_text(encoding="utf-8")

        articles.append({
            "title": meta["title"],
            "slug": slug,
            "outline_focus": meta.get("outline_focus", ""),
            "category": meta["category"],
            "html_content": html_content,
            "schema_content": schema_content,
        })

    # Shuffle articles so categories are mixed (not all How-To then all Tips)
    random.shuffle(articles)

    # Generate schedule
    schedule = None
    if not use_draft:
        if start_date is None:
            start_date = datetime.now() + timedelta(days=1)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        schedule = generate_schedule(len(articles), start_date, posts_per_day)
        end_date = schedule[-1] if schedule else start_date
        duration = (end_date - start_date).days + 1

    # Build WXR
    wxr = build_wxr(niche_slug, articles, schedule, use_draft)
    output_path = niche_dir / f"wp-import-{niche_slug}.xml"
    output_path.write_text(wxr, encoding="utf-8")

    print(f"  Articles:    {len(articles)}")
    print(f"  File size:   {output_path.stat().st_size / 1024:.1f} KB")

    if use_draft:
        print(f"  Mode:        All drafts (no scheduling)")
    else:
        launch_count = min(LAUNCH_BATCH_SIZE, len(articles))
        drip_count = len(articles) - launch_count
        print(f"  Launch day:  {launch_count} articles published immediately")
        print(f"  Drip-feed:   {drip_count} articles at {posts_per_day}-{posts_per_day+1}/day")
        print(f"  Starts:      {start_date.strftime('%Y-%m-%d')}")
        print(f"  Ends:        {end_date.strftime('%Y-%m-%d')}")
        print(f"  Duration:    {duration} days (~{duration // 7} weeks)")
        print(f"  Skips Sun:   {'Yes' if SKIP_SUNDAYS else 'No'}")
        # Show first week preview
        print(f"\n  Schedule preview:")
        day_groups = {}
        for dt in schedule:
            day_key = dt.strftime("%a %Y-%m-%d")
            day_groups.setdefault(day_key, []).append(dt.strftime("%H:%M"))
        for day, times in list(day_groups.items())[:8]:
            label = " [LAUNCH]" if day == list(day_groups.keys())[0] else ""
            print(f"    {day}: {len(times)} posts{label}")

    print(f"\n  Output:      {output_path}")
    print(f"  Import cmd:  wp import {output_path.name} --authors=create")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/wp_importer.py <niche-slug> [options]")
        print("       python scripts/wp_importer.py --all [options]")
        print("\nOptions:")
        print("  --start YYYY-MM-DD   Start date (default: tomorrow)")
        print("  --pace N             Posts per day (default: 2)")
        print("  --draft              All as drafts (no scheduling)")
        sys.exit(1)

    # Parse args
    start_date = None
    posts_per_day = DEFAULT_POSTS_PER_DAY
    use_draft = "--draft" in sys.argv

    if "--start" in sys.argv:
        idx = sys.argv.index("--start")
        if idx + 1 < len(sys.argv):
            start_date = datetime.strptime(sys.argv[idx + 1], "%Y-%m-%d")

    if "--pace" in sys.argv:
        idx = sys.argv.index("--pace")
        if idx + 1 < len(sys.argv):
            posts_per_day = int(sys.argv[idx + 1])

    niches = ALL_NICHES if sys.argv[1] == "--all" else [sys.argv[1]]

    for niche in niches:
        if not get_niche_dir(niche).exists():
            print(f"SKIP: {niche}")
            continue
        generate_import(niche, start_date, posts_per_day, use_draft)

    print("\nDone.")


if __name__ == "__main__":
    main()
