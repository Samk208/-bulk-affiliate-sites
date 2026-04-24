"""
title_deriver.py — Automatically derive article titles from keyword research data.

Takes keywords-researched.json (from keyword_researcher.py) and generates
article titles that are:
  1. Mapped to specific target keywords (with volume, KD, intent)
  2. Routed to correct article template (how-to, roundup, comparison, etc.)
  3. Grouped by keyword cluster (one article per cluster, not per keyword)
  4. Prioritized by opportunity score

Usage:
  python title_deriver.py <niche>                    # Generate titles from keywords-researched.json
  python title_deriver.py <niche> --max-titles 50    # Limit output
  python title_deriver.py <niche> --tier1-only       # Only Tier 1 pillar candidates

Output:
  outputs/<niche>/derived-titles.json   — Full title data with keyword mapping
  outputs/<niche>/titles-v2.txt         — ZimmWriter-compatible title format
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from config import PROJECT_ROOT, OUTPUTS_DIR, NICHE_NAMES, CATEGORY_SLUGS

# -- Title Generation Rules ---------------------------------------------------

# Article type -> ZimmWriter category mapping
TYPE_TO_CATEGORY = {
    "how-to": "How-To Guides",
    "explainer": "Tips & Care",
    "roundup": "Best Products",
    "comparison": "Comparisons",
    "review": "Reviews",
    "buyers-guide": "Buying Guides",
}

# Article type -> title pattern templates
TITLE_PATTERNS = {
    "how-to": [
        "How to {action} ({qualifier})",
        "{action}: Step-by-Step Guide",
        "How to {action} the Right Way",
    ],
    "explainer": [
        "{topic}: What You Need to Know",
        "{topic} Explained ({year})",
        "{topic}: Complete Guide",
    ],
    "roundup": [
        "Best {product} in {year} ({qualifier})",
        "{count} Best {product} for {audience}",
        "Best {product}: Top Picks Reviewed",
    ],
    "comparison": [
        "{product_a} vs {product_b}: Which Is Better?",
        "{product_a} vs {product_b} Compared ({year})",
    ],
    "review": [
        "{product} Review: Is It Worth It? ({year})",
        "Honest {product} Review After {timeframe}",
    ],
    "buyers-guide": [
        "How to Choose the Best {product} ({year} Guide)",
        "{product} Buying Guide: What to Look For",
    ],
}


def keyword_to_title(keyword: str, article_type: str, niche_name: str) -> str:
    """
    Convert a keyword into a natural article title.
    Uses keyword patterns to generate readable, non-keyword-stuffed titles.
    """
    kw = keyword.lower().strip()
    year = "2026"

    # Direct pattern matching for common keyword shapes
    # "best X" -> roundup title
    if kw.startswith("best "):
        product = kw[5:]
        return f"Best {_title_case(product)} in {year}"

    # "X vs Y" -> comparison
    if " vs " in kw:
        parts = kw.split(" vs ", 1)
        return f"{_title_case(parts[0])} vs {_title_case(parts[1])}: Which Is Better?"

    # "how to X" -> how-to
    if kw.startswith("how to "):
        action = kw[7:]
        return f"How to {_title_case(action)}"

    if kw.startswith("how do "):
        # "how do you X" -> "How to X"
        action = re.sub(r"^(you |i |we )", "", kw[7:])
        return f"How to {_title_case(action)}"

    if kw.startswith("how can "):
        action = re.sub(r"^(you |i |we )", "", kw[8:])
        return f"How to {_title_case(action)}"

    # "what is X" / "what are X" -> explainer
    if kw.startswith("what is ") or kw.startswith("what are "):
        topic = re.sub(r"^what (is|are) ", "", kw)
        return f"{_title_case(topic)}: What You Need to Know"

    # "why X" -> explainer
    if kw.startswith("why "):
        topic = kw[4:]
        return f"Why {_title_case(topic)}: Explained"

    # "X meaning" -> explainer
    if kw.endswith(" meaning"):
        topic = kw[:-8]
        return f"{_title_case(topic)} Meaning: Complete Guide"

    # "X signs" / "X symptoms" -> explainer
    if any(kw.endswith(f" {w}") for w in ["signs", "symptoms", "causes"]):
        return f"{_title_case(kw)}: What to Watch For"

    # "X tips" -> tips article
    if kw.endswith(" tips"):
        return f"{_title_case(kw)} That Actually Work"

    # "X cost" / "X price" -> buyers guide
    if any(kw.endswith(f" {w}") for w in ["cost", "price", "prices"]):
        return f"{_title_case(kw)}: What to Expect in {year}"

    # Generic: capitalize and add context
    if article_type == "roundup":
        return f"Best {_title_case(kw)} in {year}"
    elif article_type == "how-to":
        return f"How to {_title_case(kw)}: Complete Guide"
    elif article_type == "comparison":
        return f"{_title_case(kw)}: Full Comparison"
    elif article_type == "buyers-guide":
        return f"{_title_case(kw)}: Buying Guide"
    else:
        return f"{_title_case(kw)}: What You Need to Know"


def _title_case(text: str) -> str:
    """Smart title case — capitalize important words, keep small words lowercase."""
    small_words = {"a", "an", "the", "and", "but", "or", "for", "nor",
                   "on", "at", "to", "by", "in", "of", "up", "as", "is",
                   "it", "if", "with", "from", "into", "your", "my"}
    words = text.split()
    result = []
    for i, word in enumerate(words):
        if i == 0 or word.lower() not in small_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    return " ".join(result)


def keyword_to_slug(keyword: str) -> str:
    """Convert keyword to URL slug (max 6 words)."""
    slug = re.sub(r"[^a-z0-9\s]", "", keyword.lower())
    words = slug.split()[:6]
    return "-".join(words)


def derive_cluster_title(cluster: dict) -> dict:
    """
    Derive one article title from a keyword cluster.
    Uses the highest-volume keyword as primary target,
    with other cluster members as secondary keywords.
    """
    keywords = cluster.get("keywords_data", [])
    if not keywords:
        return None

    # Primary keyword = highest volume in cluster
    primary = max(keywords, key=lambda x: x["volume"])

    # Generate title from primary keyword
    title = keyword_to_title(
        primary["keyword"],
        primary.get("article_type", "explainer"),
        ""
    )
    slug = keyword_to_slug(primary["keyword"])
    category = TYPE_TO_CATEGORY.get(primary.get("article_type", "explainer"), "Tips & Care")

    # Build outline_focus from keyword intent
    intent = primary.get("intent", "unknown")
    if intent == "informational":
        outline_focus = f"Readers wanting to understand {primary['keyword']}"
    elif intent in ("commercial", "commercial_investigation"):
        outline_focus = f"Buyers researching {primary['keyword']} before purchasing"
    elif intent == "transactional":
        outline_focus = f"Ready-to-buy shoppers looking for {primary['keyword']}"
    else:
        outline_focus = f"People searching for {primary['keyword']}"

    # Trim outline_focus to 120 chars
    if len(outline_focus) > 120:
        outline_focus = outline_focus[:117] + "..."

    # Secondary keywords (rest of cluster)
    secondary = [kw["keyword"] for kw in keywords if kw["keyword"] != primary["keyword"]]

    return {
        "title": title,
        "slug": slug,
        "category": category,
        "article_type": primary.get("article_type", "explainer"),
        "outline_focus": outline_focus,
        "primary_keyword": primary["keyword"],
        "primary_volume": primary["volume"],
        "primary_kd": primary["kd"],
        "primary_cpc": primary["cpc"],
        "primary_intent": intent,
        "secondary_keywords": secondary[:5],  # Max 5
        "total_cluster_volume": sum(kw["volume"] for kw in keywords),
        "cluster_id": cluster.get("cluster_id", 0),
        "tier_eligible": primary.get("tier_eligible", "tier2"),
        "priority_score": primary.get("priority_score", 0),
        "has_ai_overview": primary.get("has_ai_overview", False),
    }


def run_derivation(niche_slug: str, max_titles: int = 200, tier1_only: bool = False):
    """Run title derivation from keyword research data."""
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    output_dir = OUTPUTS_DIR / niche_slug

    # Load keyword research
    research_path = output_dir / "keywords-researched.json"
    if not research_path.exists():
        print(f"ERROR: {research_path} not found. Run keyword_researcher.py first.")
        sys.exit(1)

    keywords = json.loads(research_path.read_text(encoding="utf-8"))

    # Dedup keywords and re-classify article types (handles synonyms/plurals + classification fixes)
    try:
        from keyword_researcher import deduplicate_keywords, classify_article_type
        before = len(keywords)
        keywords = deduplicate_keywords(keywords)
        # Re-classify article types using latest logic
        for kw in keywords:
            kw["article_type"] = classify_article_type(kw)
        dedup_msg = f" (deduped {before} -> {len(keywords)})" if before != len(keywords) else ""
    except ImportError:
        dedup_msg = ""

    print(f"\n{'='*60}")
    print(f"TITLE DERIVATION: {niche_name}")
    print(f"{'='*60}")
    print(f"\nLoaded {len(keywords)} keywords from research{dedup_msg}")

    # Group keywords by cluster
    clusters = defaultdict(list)
    unclustered = []
    for kw in keywords:
        cid = kw.get("cluster_id", 0)
        if cid > 0:
            clusters[cid].append(kw)
        else:
            unclustered.append(kw)

    print(f"Clustered keywords: {sum(len(v) for v in clusters.values())} across {len(clusters)} clusters")
    print(f"Unclustered keywords: {len(unclustered)}")

    # Derive one title per cluster
    derived = []
    for cid, members in clusters.items():
        cluster_data = {
            "cluster_id": cid,
            "keywords_data": members,
        }
        title_data = derive_cluster_title(cluster_data)
        if title_data:
            derived.append(title_data)

    # Also derive titles for high-volume unclustered keywords
    for kw in unclustered:
        if kw["volume"] >= 100:  # Only worthwhile unclustered keywords
            title_data = derive_cluster_title({
                "cluster_id": 0,
                "keywords_data": [kw],
            })
            if title_data:
                derived.append(title_data)

    # Sort by priority score
    derived.sort(key=lambda x: -x["priority_score"])

    # Filter tier1 if requested
    if tier1_only:
        derived = [d for d in derived if d["tier_eligible"] in ("tier1_only", "tier2")]

    # Limit titles
    if len(derived) > max_titles:
        derived = derived[:max_titles]

    # Deduplicate titles (same slug = same article)
    seen_slugs = set()
    unique_derived = []
    for d in derived:
        if d["slug"] not in seen_slugs:
            seen_slugs.add(d["slug"])
            unique_derived.append(d)
    derived = unique_derived

    # Summary
    print(f"\n--- DERIVED TITLES: {len(derived)} ---\n")

    type_counts = defaultdict(int)
    tier_counts = defaultdict(int)
    for d in derived:
        type_counts[d["article_type"]] += 1
        tier_counts[d["tier_eligible"]] += 1

    print("By article type:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    print("\nBy tier eligibility:")
    for t, c in sorted(tier_counts.items()):
        print(f"  {t}: {c}")

    print(f"\nTop 20 titles:")
    print(f"{'Title':<55} {'Keyword':<30} {'Vol':>5} {'KD':>4} {'Type':<10}")
    print("-" * 110)
    for d in derived[:20]:
        print(f"{d['title'][:55]:<55} {d['primary_keyword'][:30]:<30} {d['primary_volume']:>5} {d['primary_kd']:>4} {d['article_type']:<10}")

    # Save outputs
    # Full JSON with all metadata
    json_path = output_dir / "derived-titles.json"
    json_path.write_text(json.dumps(derived, indent=2), encoding="utf-8")
    print(f"\nOK {json_path} ({len(derived)} titles)")

    # ZimmWriter-compatible format
    txt_path = output_dir / "titles-v2.txt"
    lines = []
    for d in derived:
        line = (
            f"{d['title']}"
            f"{{outline_focus={d['outline_focus']}}}"
            f"{{slug={d['slug']}}}"
            f"{{category={d['category']}}}"
        )
        lines.append(line)
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK {txt_path}")

    # Keyword-title mapping CSV for audit
    mapping_path = output_dir / "keyword-title-mapping.csv"
    import csv
    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "slug", "primary_keyword", "volume", "kd",
                         "cpc", "intent", "article_type", "tier", "secondary_keywords"])
        for d in derived:
            writer.writerow([
                d["title"], d["slug"], d["primary_keyword"],
                d["primary_volume"], d["primary_kd"], d["primary_cpc"],
                d["primary_intent"], d["article_type"], d["tier_eligible"],
                "; ".join(d["secondary_keywords"][:3]),
            ])
    print(f"OK {mapping_path}")

    print(f"\nOK Title derivation complete for {niche_name}")
    print(f"   Next: Review titles, then run content pipeline")

    return derived


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Derive titles from keyword research")
    parser.add_argument("niche", help="Niche slug")
    parser.add_argument("--max-titles", type=int, default=200)
    parser.add_argument("--tier1-only", action="store_true")
    args = parser.parse_args()

    if args.niche not in NICHE_NAMES:
        print(f"Unknown niche: {args.niche}. Available: {', '.join(NICHE_NAMES.keys())}")
        sys.exit(1)

    run_derivation(args.niche, args.max_titles, args.tier1_only)
