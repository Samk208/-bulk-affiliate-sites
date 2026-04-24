"""
post_pillars_to_wp.py — Post specific pillar articles to LocalWP as drafts
==========================================================================
Run this from your computer (not from Cowork sandbox) since LocalWP is local.

Usage:
    python scripts/post_pillars_to_wp.py
    python scripts/post_pillars_to_wp.py --niche dog-comfort --status draft
    python scripts/post_pillars_to_wp.py --slugs dog-separation-anxiety-guide dog-bed-buying-guide

Requirements: requests
    pip install requests
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WP_URL   = "http://localhost:10040"
WP_USER  = "skonneh18"
WP_PASS  = "Q4Ab UFTA Jk90 nPO2 Sbaz mJDG"  # App password (dev 2) — generated 2026-04-12

# ── Pillar definitions (pending WP posting) ───────────────────────────────────
PILLARS = {
    "dog-comfort": [
        {
            "slug": "dog-separation-anxiety-guide",
            "title": "Dog Separation Anxiety: The Complete Guide",
            "category": "Dog Behavior",
            "tags": ["separation anxiety", "dog anxiety", "dog behavior"]
        },
        {
            "slug": "dog-joint-health-mobility-guide",
            "title": "Dog Joint Health & Mobility: The Complete Guide",
            "category": "Dog Health",
            "tags": ["joint health", "dog arthritis", "dog mobility"]
        },
        {
            "slug": "crate-training-complete-guide",
            "title": "Crate Training: The Complete Guide for Puppies and Adult Dogs",
            "category": "Dog Training",
            "tags": ["crate training", "puppy training", "dog training"]
        },
        {
            "slug": "dog-car-travel-safety-guide",
            "title": "Dog Car & Travel Safety: The Complete Guide",
            "category": "Dog Travel",
            "tags": ["dog car safety", "traveling with dogs", "dog restraints"]
        },
        {
            "slug": "dog-grooming-skin-care-guide",
            "title": "Dog Grooming & Skin Care: The Complete Guide",
            "category": "Dog Grooming",
            "tags": ["dog grooming", "dog skin care", "dog bathing"]
        },
        {
            "slug": "dog-bed-buying-guide",
            "title": "Dog Bed Buying Guide: How to Choose the Right Bed for Your Dog",
            "category": "Dog Comfort",
            "tags": ["dog bed", "orthopedic dog bed", "buying guide"]
        },
    ]
}


def get_auth_header(user: str, password: str) -> str:
    """Return Basic auth header value."""
    import base64
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def wp_request(endpoint: str, data: dict, method: str = "POST") -> dict:
    """Make an authenticated WP REST API request."""
    url = f"{WP_URL}/wp-json/wp/v2/{endpoint}"
    payload = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": get_auth_header(WP_USER, WP_PASS),
            "Content-Type": "application/json"
        },
        method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  ❌ HTTP {e.code}: {body[:200]}")
        return {}
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        print(f"     Is LocalWP running? Is '{WP_URL}' the correct URL?")
        return {}


def get_or_create_category(name: str) -> int:
    """Get category ID, creating it if it doesn't exist."""
    # Check existing
    url = f"{WP_URL}/wp-json/wp/v2/categories?search={urllib.parse.quote(name)}&per_page=5"
    req = urllib.request.Request(url, headers={"Authorization": get_auth_header(WP_USER, WP_PASS)})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            cats = json.loads(resp.read().decode("utf-8"))
            for cat in cats:
                if cat["name"].lower() == name.lower():
                    return cat["id"]
    except:
        pass

    # Create
    result = wp_request("categories", {"name": name})
    return result.get("id", 1)


def post_article(niche: str, pillar: dict, status: str = "draft", base_dir: Path = None) -> bool:
    """Post a single article to WordPress."""
    slug = pillar["slug"]
    html_path = base_dir / "outputs" / niche / "articles" / f"{slug}.html"

    if not html_path.exists():
        print(f"  ⚠ File not found: {html_path}")
        return False

    content = html_path.read_text(encoding="utf-8")

    print(f"\n  → Posting: {pillar['title']}")

    # Get or create category
    cat_id = get_or_create_category(pillar.get("category", "Uncategorized"))

    post_data = {
        "title": pillar["title"],
        "slug": slug,
        "content": content,
        "status": status,
        "categories": [cat_id],
        "tags": pillar.get("tags", [])
    }

    result = wp_request("posts", post_data)

    if result.get("id"):
        print(f"  ✓ Posted: ID {result['id']} | Status: {result.get('status')} | URL: {result.get('link')}")

        # Update JSON with WP ID
        json_path = base_dir / "outputs" / niche / "articles" / f"{slug}.json"
        if json_path.exists():
            schema = json.loads(json_path.read_text())
            schema["wpId"] = result["id"]
            schema["wpStatus"] = status
            schema["wpUrl"] = result.get("link", "")
            json_path.write_text(json.dumps(schema, indent=2))

        return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Post pillar articles to LocalWP")
    parser.add_argument("--niche", default="dog-comfort")
    parser.add_argument("--status", default="draft", choices=["draft", "publish", "pending"])
    parser.add_argument("--slugs", nargs="*", help="Specific slugs to post (posts all if omitted)")
    args = parser.parse_args()

    # Find project root
    base_dir = Path(__file__).parent.parent

    pillars = PILLARS.get(args.niche, [])
    if not pillars:
        print(f"No pillar definitions found for niche: {args.niche}")
        sys.exit(1)

    if args.slugs:
        pillars = [p for p in pillars if p["slug"] in args.slugs]

    print(f"\n{'='*60}")
    print(f"Posting to LocalWP: {args.niche} ({len(pillars)} articles)")
    print(f"Status: {args.status}")
    print(f"{'='*60}")

    # Test connection
    try:
        req = urllib.request.Request(
            f"{WP_URL}/wp-json/wp/v2/posts?per_page=1",
            headers={"Authorization": get_auth_header(WP_USER, WP_PASS)}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✓ Connected to LocalWP at {WP_URL}")
    except Exception as e:
        print(f"❌ Cannot connect to LocalWP at {WP_URL}")
        print(f"   Error: {e}")
        print(f"   Make sure LocalWP is running and the site is started.")
        sys.exit(1)

    results = {"posted": [], "failed": []}
    for pillar in pillars:
        success = post_article(args.niche, pillar, args.status, base_dir)
        if success:
            results["posted"].append(pillar["slug"])
        else:
            results["failed"].append(pillar["slug"])

    print(f"\n{'='*60}")
    print(f"DONE: {len(results['posted'])} posted, {len(results['failed'])} failed")
    if results["failed"]:
        print(f"Failed: {results['failed']}")
    print(f"{'='*60}")
    print(f"View drafts at: {WP_URL}/wp-admin/edit.php?post_status=draft&post_type=post")


if __name__ == "__main__":
    main()
