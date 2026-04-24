"""
keyword_researcher.py -- Improved keyword research pipeline using DataForSEO MCP.

Workflow:
  1. DISCOVERY   -- keyword_suggestions with multiple seed types (transactional + informational)
  2. CLUSTERING  -- related_keywords for SERP overlap grouping
  3. INTENT      -- search_intent batch classification
  4. FILTERING   -- KD filter for DA-0 sites, dedup synonyms via core_keyword
  5. OUTPUT      -- keywords-researched.json with full metadata per keyword

Usage:
  python keyword_researcher.py <niche> --seeds "seed1,seed2,seed3"
  python keyword_researcher.py <niche> --seeds-file seeds.txt
  python keyword_researcher.py <niche> --auto  # Use niche config seeds

Requires: DataForSEO credentials in .env.cowork (DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD)
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

# -- Config -------------------------------------------------------------------
from config import PROJECT_ROOT, OUTPUTS_DIR, NICHE_NAMES
from entity_library import NICHE_ENTITIES, ENTITY_RELATIONSHIPS

# DataForSEO credentials -- check BOTH env files (project has OpenRouter/Perplexity,
# global has DataForSEO). Load ALL env files without skip-if-exists.
_project_env = PROJECT_ROOT / ".env.cowork"
_global_env = PROJECT_ROOT.parent.parent / "_global" / ".env.cowork"

for _env_file in [_global_env, _project_env]:  # Global first, project overrides
    if _env_file.exists():
        for line in _env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                k, v = key.strip(), value.strip()
                if v:
                    os.environ[k] = v

DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN", "")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "")
DATAFORSEO_BASE = "https://api.dataforseo.com/v3"

LOCATION_CODE = 2840  # United States
LANGUAGE_CODE = "en"

# KD thresholds for DA-0 sites
KD_MAX_TIER1 = 30      # Pillars can target up to KD 30
KD_MAX_TIER2 = 15      # Supporting articles should be KD ≤ 15
KD_MAX_ABSOLUTE = 40   # Drop anything above this entirely

# Volume minimums
VOL_MIN = 50            # Drop keywords below 50 monthly searches

# -- Niche Seed Keywords (informational + transactional mix) ------------------
NICHE_SEEDS = {
    "dog-comfort": {
        "transactional": [
            "best dog bed",
            "best dog crate",
            "best cooling dog bed",
            "best orthopedic dog bed",
            "best dog anxiety vest",
        ],
        "informational": [
            "how to make dog comfortable",
            "dog sleeping position meaning",
            "dog separation anxiety help",
            "how to crate train dog",
            "dog joint pain signs",
        ],
    },
    "camping-gear": {
        "transactional": [
            "best camping tent",
            "best camping stove",
            "best sleeping bag",
            "best camping chair",
            "best backpacking gear",
        ],
        "informational": [
            "how to set up camp",
            "camping tips for beginners",
            "how to stay warm camping",
            "campfire cooking tips",
            "hiking trail safety",
        ],
    },
    "cat-care": {
        "transactional": [
            "best cat food",
            "best cat litter",
            "best cat tree",
            "best cat carrier",
            "best automatic cat feeder",
        ],
        "informational": [
            "how to care for a kitten",
            "cat behavior meaning",
            "how to introduce cats",
            "cat health problems signs",
            "indoor cat enrichment ideas",
        ],
    },
    "home-coffee": {
        "transactional": [
            "best coffee maker",
            "best espresso machine",
            "best coffee grinder",
            "best pour over coffee",
            "best cold brew maker",
        ],
        "informational": [
            "how to make espresso at home",
            "coffee brewing methods compared",
            "how to grind coffee beans",
            "water temperature for coffee",
            "french press vs pour over",
        ],
    },
    "mens-grooming": {
        "transactional": [
            "best beard trimmer",
            "best electric razor",
            "best hair clipper",
            "best men face wash",
            "best men moisturizer",
        ],
        "informational": [
            "how to trim beard properly",
            "men skincare routine",
            "how to prevent razor burn",
            "beard growth tips",
            "how to style hair men",
        ],
    },
    "oral-care": {
        "transactional": [
            "best electric toothbrush",
            "best water flosser",
            "best whitening strips",
            "best toothpaste sensitive teeth",
            "best mouthwash",
        ],
        "informational": [
            "how to whiten teeth naturally",
            "proper brushing technique",
            "how often replace toothbrush",
            "gum disease signs symptoms",
            "flossing vs water flosser",
        ],
    },
    "home-cleaning": {
        "transactional": [
            "best robot vacuum",
            "best steam mop",
            "best laundry detergent",
            "best air purifier",
            "best carpet cleaner",
        ],
        "informational": [
            "how to deep clean house",
            "natural cleaning solutions home",
            "how to remove stains carpet",
            "cleaning schedule weekly",
            "how to organize closet",
        ],
    },
    "healthy-cooking": {
        "transactional": [
            "best air fryer",
            "best blender",
            "best meal prep containers",
            "best non stick pan",
            "best instant pot",
        ],
        "informational": [
            "healthy meal prep ideas",
            "how to cook healthy meals",
            "meal planning for beginners",
            "healthy cooking substitutions",
            "how to meal prep for week",
        ],
    },
    "home-office": {
        "transactional": [
            "best office chair",
            "best standing desk",
            "best monitor",
            "best desk lamp",
            "best keyboard ergonomic",
        ],
        "informational": [
            "how to set up home office",
            "ergonomic desk setup guide",
            "work from home productivity tips",
            "best home office lighting",
            "how to reduce back pain desk",
        ],
    },
    "water-air-quality": {
        "transactional": [
            "best water filter",
            "best air purifier",
            "best humidifier",
            "best water test kit",
            "best dehumidifier",
        ],
        "informational": [
            "how to test water quality home",
            "water filter types compared",
            "how to improve indoor air quality",
            "signs of mold in house",
            "well water vs city water",
        ],
    },
    "korean-skincare": {
        "transactional": [
            "best korean sunscreen",
            "best korean moisturizer",
            "best korean toner",
            "best korean serum",
            "best korean cleanser",
        ],
        "informational": [
            "korean skincare routine steps",
            "glass skin routine korean",
            "double cleansing method",
            "how to layer skincare products",
            "korean skincare for acne",
        ],
    },
    "makeup-beauty": {
        "transactional": [
            "best foundation for oily skin",
            "best concealer",
            "best mascara",
            "best setting spray",
            "best eyeshadow palette",
        ],
        "informational": [
            "makeup routine for beginners",
            "how to contour face",
            "how to apply foundation",
            "makeup for hooded eyes",
            "skincare before makeup",
        ],
    },
    "korean-medical-tourism": {
        "transactional": [
            "best plastic surgery clinic korea",
            "rhinoplasty korea cost",
            "korean dermatologist clinic",
            "korea dental treatment price",
            "korean health checkup package",
        ],
        "informational": [
            "is plastic surgery safe in korea",
            "korea medical tourism guide",
            "how to choose surgeon korea",
            "korea hospital quality standards",
            "recovery after surgery korea",
        ],
    },
    "korean-used-cars": {
        "transactional": [
            "buy used car from korea",
            "korean used car export",
            "cheap korean cars for sale",
            "hyundai used car korea",
            "korean car auction",
        ],
        "informational": [
            "how to import car from korea",
            "korean car inspection process",
            "korean used car market guide",
            "shipping car from korea cost",
            "korean car brands comparison",
        ],
    },
}


# -- API Helpers --------------------------------------------------------------

def _api_request(endpoint: str, payload: dict) -> dict:
    """Make authenticated DataForSEO API request."""
    url = f"{DATAFORSEO_BASE}/{endpoint}"
    resp = requests.post(
        url,
        json=[payload],
        auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD),
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status_code") != 20000:
        raise RuntimeError(f"DataForSEO error: {data.get('status_message')}")
    return data


def fetch_keyword_suggestions(seed: str, limit: int = 100) -> list[dict]:
    """Fetch keyword suggestions for a seed keyword."""
    payload = {
        "keyword": seed,
        "location_code": LOCATION_CODE,
        "language_code": LANGUAGE_CODE,
        "limit": limit,
        "include_seed_keyword": True,
    }
    data = _api_request("dataforseo_labs/google/keyword_suggestions/live", payload)
    items = []
    for task in data.get("tasks", []):
        if task.get("status_code") == 20000 and task.get("result"):
            for result in task["result"]:
                for item in (result.get("items") or []):
                    # keyword_suggestions: item IS the keyword data (no keyword_data wrapper)
                    items.append(_parse_keyword_data(item))
    return items


def fetch_related_keywords(seed: str, limit: int = 30) -> list[dict]:
    """Fetch SERP-overlapping related keywords -- for clustering."""
    payload = {
        "keyword": seed,
        "location_code": LOCATION_CODE,
        "language_code": LANGUAGE_CODE,
        "limit": limit,
    }
    data = _api_request("dataforseo_labs/google/related_keywords/live", payload)
    items = []
    for task in data.get("tasks", []):
        if task.get("status_code") == 20000 and task.get("result"):
            for result in task["result"]:
                for item in (result.get("items") or []):
                    # related_keywords: keyword data is in item["keyword_data"]
                    kw_data = item.get("keyword_data", {})
                    parsed = _parse_keyword_data(kw_data)
                    # Add SERP overlap info
                    parsed["related_keywords"] = item.get("related_keywords", [])
                    parsed["depth"] = item.get("depth", 0)
                    items.append(parsed)
    return items


def fetch_search_intent(keywords: list[str]) -> dict[str, dict]:
    """Batch classify search intent for keywords."""
    # DataForSEO search_intent accepts up to 1000 keywords per request
    results = {}
    batch_size = 1000
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]
        payload = {
            "keywords": batch,
            "location_code": LOCATION_CODE,
            "language_code": LANGUAGE_CODE,
        }
        data = _api_request("dataforseo_labs/google/search_intent/live", payload)
        for task in data.get("tasks", []):
            if task.get("status_code") == 20000 and task.get("result"):
                for result in task["result"]:
                    for item in (result.get("items") or []):
                        kw = item.get("keyword", "")
                        results[kw] = {
                            "intent": item.get("keyword_intent", {}).get("label", "unknown"),
                            "probability": item.get("keyword_intent", {}).get("probability", 0),
                            "secondary_intent": item.get("secondary_keyword_intent"),
                        }
        if i + batch_size < len(keywords):
            time.sleep(0.5)  # Rate limiting between batches
    return results


def _parse_keyword_data(kw_data: dict) -> dict:
    """Parse DataForSEO keyword_data into a flat dict."""
    kw_info = kw_data.get("keyword_info") or {}
    kw_props = kw_data.get("keyword_properties") or {}
    serp_info = kw_data.get("serp_info") or {}
    intent_info = kw_data.get("search_intent_info") or {}
    backlinks_info = kw_data.get("avg_backlinks_info") or {}

    # Monthly trend
    monthly = kw_info.get("monthly_searches") or []
    trend = kw_info.get("search_volume_trend") or {}

    return {
        "keyword": kw_data.get("keyword", ""),
        "volume": kw_info.get("search_volume", 0) or 0,
        "kd": kw_props.get("keyword_difficulty", 0) or 0,
        "cpc": kw_info.get("cpc", 0) or 0,
        "competition": kw_info.get("competition_level", ""),
        "core_keyword": kw_props.get("core_keyword"),  # For dedup
        "intent": intent_info.get("main_intent", "unknown"),
        "serp_features": serp_info.get("serp_item_types", []),
        "has_ai_overview": "ai_overview" in (serp_info.get("serp_item_types") or []),
        "has_paa": "people_also_ask" in (serp_info.get("serp_item_types") or []),
        "serp_results_count": serp_info.get("se_results_count", 0) or 0,
        "avg_backlinks": backlinks_info.get("backlinks", 0) or 0,
        "avg_referring_domains": backlinks_info.get("referring_main_domains", 0) or 0,
        "monthly_trend_quarterly": trend.get("quarterly", 0) or 0,
        "monthly_trend_yearly": trend.get("yearly", 0) or 0,
        "monthly_searches": monthly[:6],  # Last 6 months
    }


# -- Processing ---------------------------------------------------------------

_SYNONYM_MAP = {
    # Size
    "large": "big", "xl": "big", "extra large": "big", "oversized": "big", "jumbo": "big",
    "small": "small", "mini": "small", "compact": "small", "tiny": "small",
    # Age
    "senior": "old", "older": "old", "elderly": "old", "aging": "old", "aged": "old",
    "puppy": "puppy", "puppies": "puppy", "young": "puppy",
    # Quality/Type
    "top": "best", "greatest": "best", "finest": "best", "recommended": "best",
    "inexpensive": "cheap", "affordable": "cheap", "budget": "cheap", "low cost": "cheap",
    "premium": "luxury", "high end": "luxury", "expensive": "luxury",
    # Materials
    "orthopaedic": "orthopedic", "ortho": "orthopedic",
    "memory foam": "foam",
    # Actions
    "purchase": "buy", "shop": "buy",
    "pick": "choose", "select": "choose", "find": "choose",
    # Pet terms
    "canine": "dog", "pup": "dog", "pooch": "dog", "pet": "dog",
    "feline": "cat", "kitty": "cat", "kitten": "cat",
}


_NO_STEM = {"does", "was", "has", "is", "goes", "its", "this", "yes", "plus", "bonus", "us", "bus"}


def _stem_simple(word: str) -> str:
    """Very basic plural stemming — just handles common English plural endings."""
    if word in _NO_STEM:
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"  # puppies -> puppy
    if len(word) > 3 and word.endswith("es") and word[-3] in "shxz":
        return word[:-2]  # brushes -> brush
    if len(word) > 3 and word.endswith("s") and word[-2] not in "su":
        return word[:-1]  # dogs -> dog, beds -> bed
    return word


def _normalize_keyword(kw: str) -> str:
    """Normalize keyword for dedup: stem plurals, remove stop words, map synonyms, dedupe words."""
    stop_words = {"a", "an", "the", "for", "in", "on", "of", "to", "with", "and", "or", "my", "your"}
    words = [w for w in kw.lower().split() if w not in stop_words]
    # Stem plurals first
    words = [_stem_simple(w) for w in words]
    # Map synonyms to canonical forms
    words = [_SYNONYM_MAP.get(w, w) for w in words]
    # Remove duplicate words (e.g., "pet bed dog" -> "dog bed dog" -> keep one "dog")
    seen = set()
    unique = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return " ".join(sorted(unique))


def deduplicate_keywords(keywords: list[dict]) -> list[dict]:
    """
    Deduplicate keywords using:
    1. Exact match dedup
    2. Word-order normalization ("best dog bed" = "dog bed best" = "best bed dog")
    3. core_keyword grouping from DataForSEO
    """
    # Phase 1: Group by normalized form (word-order variants)
    norm_groups = defaultdict(list)  # normalized -> list of entries
    for kw in keywords:
        text = kw["keyword"]
        norm = _normalize_keyword(text)
        norm_groups[norm].append(kw)

    # Phase 2: Pick the best representative from each group
    # Best = highest volume, with preference for natural word order
    seen_keywords = {}
    for norm, group in norm_groups.items():
        # Sort by volume desc, pick highest
        group.sort(key=lambda x: -x["volume"])
        best = group[0]

        # Mark synonyms
        if len(group) > 1:
            best["synonym_count"] = len(group)
            best["synonyms"] = [g["keyword"] for g in group[1:]]
            # Aggregate volume note (for cluster priority)
            best["combined_synonym_volume"] = sum(g["volume"] for g in group)

        # Also check core_keyword from DataForSEO
        core = best.get("core_keyword")
        if core:
            best["core_keyword_group"] = core

        seen_keywords[best["keyword"]] = best

    return list(seen_keywords.values())


def filter_keywords(keywords: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filter keywords by volume and KD thresholds.
    Returns (kept, dropped) for audit trail.
    """
    kept, dropped = [], []
    for kw in keywords:
        if kw["volume"] < VOL_MIN:
            kw["drop_reason"] = f"volume {kw['volume']} < {VOL_MIN}"
            dropped.append(kw)
        elif kw["kd"] > KD_MAX_ABSOLUTE:
            kw["drop_reason"] = f"KD {kw['kd']} > {KD_MAX_ABSOLUTE}"
            dropped.append(kw)
        else:
            # Tag tier eligibility
            if kw["kd"] <= KD_MAX_TIER2:
                kw["tier_eligible"] = "tier2"
            elif kw["kd"] <= KD_MAX_TIER1:
                kw["tier_eligible"] = "tier1_only"
            else:
                kw["tier_eligible"] = "hard"
            kept.append(kw)
    return kept, dropped


def cluster_keywords(keywords: list[dict], related_data: list[dict]) -> list[dict]:
    """
    Group keywords into clusters based on SERP overlap from related_keywords data.
    Keywords that share SERPs should be ONE article, not separate articles.
    """
    # Build overlap graph from related_keywords data
    overlap_groups = defaultdict(set)
    for item in related_data:
        seed = item["keyword"]
        for related in (item.get("related_keywords") or []):
            overlap_groups[seed].add(related)
            overlap_groups[related].add(seed)

    # Simple connected components clustering
    kw_set = {kw["keyword"] for kw in keywords}
    assigned = {}
    cluster_id = 0

    for kw in sorted(keywords, key=lambda x: -x["volume"]):
        text = kw["keyword"]
        if text in assigned:
            continue

        # Start new cluster from this keyword (highest unassigned volume)
        cluster_id += 1
        queue = [text]
        while queue:
            current = queue.pop(0)
            if current in assigned:
                continue
            if current in kw_set:
                assigned[current] = cluster_id
            # Add SERP-overlapping keywords to same cluster
            for neighbor in overlap_groups.get(current, set()):
                if neighbor not in assigned and neighbor in kw_set:
                    queue.append(neighbor)

    # Assign cluster IDs to keyword dicts
    for kw in keywords:
        kw["cluster_id"] = assigned.get(kw["keyword"], 0)

    return keywords


def classify_article_type(kw: dict) -> str:
    """Map search intent to article type/template."""
    intent = kw.get("intent", "unknown").lower()
    keyword_text = kw.get("keyword", "").lower()

    # Check keyword patterns first (more reliable than intent alone)
    # Questions are always informational, even if DataForSEO says "commercial"
    question_starters = ["will ", "does ", "can ", "should ", "is ", "are ", "do ", "could ", "would "]
    if any(keyword_text.startswith(q) for q in question_starters):
        return "explainer"
    if any(p in keyword_text for p in ["best ", "top ", "best-"]):
        return "roundup"  # "Best X" -> product roundup
    if any(p in keyword_text for p in [" vs ", " versus ", " compared", " comparison"]):
        return "comparison"  # X vs Y -> comparison
    if any(p in keyword_text for p in ["how to ", "how do ", "how can "]):
        return "how-to"  # How to X -> step-by-step guide
    if any(p in keyword_text for p in ["what is ", "what are ", "why ", "meaning", "signs", "symptoms"]):
        return "explainer"  # What/Why -> informational explainer
    if any(p in keyword_text for p in ["review", "worth it"]):
        return "review"
    if any(p in keyword_text for p in ["buy ", "price", "cost", "cheap", "affordable", "deal"]):
        return "buyers-guide"

    # Fall back to intent classification
    if intent == "informational":
        return "explainer"
    elif intent in ("commercial", "commercial_investigation"):
        return "roundup"
    elif intent == "transactional":
        return "buyers-guide"
    else:
        return "explainer"  # Default safe


def tag_keyword_entities(kw: dict, niche_slug: str) -> list[str]:
    """Tag which niche entities are relevant to this keyword.

    Direct match: entity name appears in keyword text.
    Relationship match: entity connected via ENTITY_RELATIONSHIPS to a matched entity.
    """
    entities = NICHE_ENTITIES.get(niche_slug, {})
    relationships = ENTITY_RELATIONSHIPS.get(niche_slug, [])
    kw_text = kw["keyword"].lower()

    matched = set()
    # Direct entity name match (entity name is substring of keyword)
    for name in entities:
        if name.lower() in kw_text:
            matched.add(name)
    # Also check individual words of multi-word entities
    kw_words = set(kw_text.split())
    for name in entities:
        name_words = name.lower().split()
        if len(name_words) >= 2 and all(w in kw_words for w in name_words):
            matched.add(name)
    # Stem-aware: "crate train" matches "crate training", "cleaning" matches "cleaner"
    kw_stems = {w.rstrip("ings").rstrip("ing").rstrip("ed").rstrip("er") for w in kw_words if len(w) > 3}
    for name in entities:
        name_stems = {w.rstrip("ings").rstrip("ing").rstrip("ed").rstrip("er")
                      for w in name.lower().split() if len(w) > 3}
        if name_stems and name_stems.issubset(kw_stems):
            matched.add(name)

    # Relationship expansion: if keyword mentions entity A, also tag entity B if A--B linked
    direct = set(matched)
    for subj, verb, obj in relationships:
        if subj.lower() in kw_text and obj in entities:
            matched.add(obj)
        elif obj.lower() in kw_text and subj in entities:
            matched.add(subj)

    return list(matched)


def prioritize_keywords(keywords: list[dict]) -> list[dict]:
    """
    Score and sort keywords by a composite priority score.
    Factors: volume, low KD, intent variety, trend, CPC (affiliate value).
    """
    for kw in keywords:
        vol_score = min(kw["volume"] / 1000, 10)  # Cap at 10
        kd_score = max(0, (40 - kw["kd"]) / 4)    # 0-10, lower KD = higher
        cpc_score = min(kw["cpc"], 5)               # Higher CPC = more affiliate value
        trend_score = max(0, min(kw.get("monthly_trend_yearly", 0) / 50, 3))  # Growing trends
        aio_penalty = -2 if kw.get("has_ai_overview") else 0  # AI Overview = harder to rank

        kw["priority_score"] = round(
            vol_score * 0.35 +
            kd_score * 0.30 +
            cpc_score * 0.15 +
            trend_score * 0.10 +
            aio_penalty * 0.10,
            2
        )

    return sorted(keywords, key=lambda x: -x["priority_score"])


# -- Main Pipeline ------------------------------------------------------------

def run_research(niche_slug: str, custom_seeds: list[str] | None = None):
    """Run the full keyword research pipeline for a niche."""
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    output_dir = OUTPUTS_DIR / niche_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"KEYWORD RESEARCH: {niche_name}")
    print(f"{'='*60}\n")

    # -- Step 1: Determine seeds --
    if custom_seeds:
        seeds_t = custom_seeds[:5]
        seeds_i = custom_seeds[5:]
    elif niche_slug in NICHE_SEEDS:
        seeds_t = NICHE_SEEDS[niche_slug]["transactional"]
        seeds_i = NICHE_SEEDS[niche_slug]["informational"]
    else:
        print(f"ERROR: No seeds configured for niche '{niche_slug}'")
        sys.exit(1)

    all_seeds = seeds_t + seeds_i
    print(f"Seeds ({len(all_seeds)} total):")
    for s in seeds_t:
        print(f"  [T] {s}")
    for s in seeds_i:
        print(f"  [I] {s}")

    # -- Step 2: Discovery via keyword_suggestions --
    print(f"\n--- STEP 1: Keyword Discovery ---")
    all_keywords = []
    for seed in all_seeds:
        print(f"  Fetching suggestions for: {seed}")
        try:
            results = fetch_keyword_suggestions(seed, limit=100)
            print(f"    -> {len(results)} keywords")
            all_keywords.extend(results)
            time.sleep(0.3)  # Rate limiting
        except Exception as e:
            print(f"    X Error: {e}")

    print(f"\n  Total raw keywords: {len(all_keywords)}")

    # -- Step 3: Related keywords for clustering (top 5 seeds by likely volume) --
    print(f"\n--- STEP 2: SERP Overlap Analysis ---")
    related_data = []
    cluster_seeds = all_seeds[:6]  # First 6 seeds for clustering
    for seed in cluster_seeds:
        print(f"  Fetching related for: {seed}")
        try:
            results = fetch_related_keywords(seed, limit=20)
            print(f"    -> {len(results)} related keywords")
            related_data.extend(results)
            # Also add the related keywords to our pool
            all_keywords.extend(results)
            time.sleep(0.3)
        except Exception as e:
            print(f"    X Error: {e}")

    # -- Step 4: Deduplicate --
    print(f"\n--- STEP 3: Deduplication ---")
    deduped = deduplicate_keywords(all_keywords)
    print(f"  Before: {len(all_keywords)} -> After: {len(deduped)}")

    # -- Step 5: Filter by volume and KD --
    print(f"\n--- STEP 4: Filtering (vol >= {VOL_MIN}, KD <= {KD_MAX_ABSOLUTE}) ---")
    kept, dropped = filter_keywords(deduped)
    print(f"  Kept: {len(kept)}")
    print(f"  Dropped: {len(dropped)}")

    # -- Step 6: Classify article type --
    print(f"\n--- STEP 5: Article Type Classification + Entity Tagging ---")
    type_counts = defaultdict(int)
    entity_tagged = 0
    for kw in kept:
        kw["article_type"] = classify_article_type(kw)
        type_counts[kw["article_type"]] += 1
        kw["entities"] = tag_keyword_entities(kw, niche_slug)
        if kw["entities"]:
            entity_tagged += 1
    for atype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {atype}: {count}")
    print(f"  Keywords with entity tags: {entity_tagged}/{len(kept)}")

    # -- Step 7: Cluster keywords --
    print(f"\n--- STEP 6: SERP Overlap Clustering ---")
    kept = cluster_keywords(kept, related_data)
    cluster_counts = defaultdict(int)
    for kw in kept:
        cluster_counts[kw["cluster_id"]] += 1
    print(f"  Clusters formed: {len(cluster_counts)}")
    print(f"  Avg keywords/cluster: {len(kept)/max(len(cluster_counts),1):.1f}")

    # -- Step 8: Prioritize --
    print(f"\n--- STEP 7: Priority Scoring ---")
    kept = prioritize_keywords(kept)

    # -- Step 9: Summary stats --
    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")

    intent_dist = defaultdict(int)
    tier_dist = defaultdict(int)
    aio_count = 0
    for kw in kept:
        intent_dist[kw["intent"]] += 1
        tier_dist[kw.get("tier_eligible", "unknown")] += 1
        if kw.get("has_ai_overview"):
            aio_count += 1

    print(f"\nTotal keywords: {len(kept)}")
    print(f"\nIntent distribution:")
    for intent, count in sorted(intent_dist.items(), key=lambda x: -x[1]):
        print(f"  {intent}: {count} ({count/len(kept)*100:.0f}%)")
    print(f"\nTier eligibility:")
    for tier, count in sorted(tier_dist.items()):
        print(f"  {tier}: {count}")
    print(f"\nAI Overview SERPs: {aio_count}")

    print(f"\nTop 20 keywords by priority:")
    print(f"{'Keyword':<50} {'Vol':>6} {'KD':>4} {'CPC':>5} {'Intent':<15} {'Type':<12} {'Score':>5}")
    print("-" * 100)
    for kw in kept[:20]:
        print(f"{kw['keyword'][:50]:<50} {kw['volume']:>6} {kw['kd']:>4} {kw['cpc']:>5.2f} {kw['intent']:<15} {kw['article_type']:<12} {kw['priority_score']:>5.2f}")

    # -- Step 10: Save outputs --
    print(f"\n--- Saving outputs ---")

    # Full research data (JSON)
    research_path = output_dir / "keywords-researched.json"
    # Remove non-serializable data and monthly_searches to keep file manageable
    save_data = []
    for kw in kept:
        save_kw = {k: v for k, v in kw.items() if k != "monthly_searches"}
        save_data.append(save_kw)
    research_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
    print(f"  OK {research_path} ({len(save_data)} keywords)")

    # Dropped keywords (audit trail)
    dropped_path = output_dir / "keywords-dropped.json"
    dropped_path.write_text(json.dumps(
        [{"keyword": d["keyword"], "volume": d["volume"], "kd": d["kd"],
          "reason": d.get("drop_reason", "unknown")} for d in dropped],
        indent=2
    ), encoding="utf-8")
    print(f"  OK {dropped_path} ({len(dropped)} dropped)")

    # Cluster summary
    clusters = defaultdict(list)
    for kw in kept:
        clusters[kw["cluster_id"]].append(kw)

    cluster_summary = []
    for cid, members in sorted(clusters.items()):
        top = max(members, key=lambda x: x["volume"])
        cluster_summary.append({
            "cluster_id": cid,
            "primary_keyword": top["keyword"],
            "primary_volume": top["volume"],
            "primary_kd": top["kd"],
            "primary_intent": top["intent"],
            "article_type": top["article_type"],
            "member_count": len(members),
            "total_volume": sum(m["volume"] for m in members),
            "keywords": [m["keyword"] for m in members],
        })

    cluster_path = output_dir / "keyword-clusters.json"
    cluster_path.write_text(json.dumps(
        sorted(cluster_summary, key=lambda x: -x["total_volume"]),
        indent=2
    ), encoding="utf-8")
    print(f"  OK {cluster_path} ({len(cluster_summary)} clusters)")

    # CSV for quick review (compatible with old keywords-raw.csv format + extras)
    csv_path = output_dir / "keywords-v2.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "keyword", "volume", "kd", "cpc", "intent",
            "article_type", "tier_eligible", "cluster_id",
            "has_ai_overview", "priority_score",
        ])
        writer.writeheader()
        for kw in kept:
            writer.writerow({
                "keyword": kw["keyword"],
                "volume": kw["volume"],
                "kd": kw["kd"],
                "cpc": kw["cpc"],
                "intent": kw["intent"],
                "article_type": kw["article_type"],
                "tier_eligible": kw.get("tier_eligible", ""),
                "cluster_id": kw.get("cluster_id", 0),
                "has_ai_overview": kw.get("has_ai_overview", False),
                "priority_score": kw.get("priority_score", 0),
            })
    print(f"  OK {csv_path}")

    print(f"\nDONE: Research complete for {niche_name}")
    print(f"   Next step: python title_deriver.py {niche_slug}")

    return kept


# -- CLI ----------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Keyword research pipeline")
    parser.add_argument("niche", help="Niche slug (e.g., dog-comfort)")
    parser.add_argument("--seeds", help="Comma-separated seed keywords")
    parser.add_argument("--seeds-file", help="File with one seed per line")
    parser.add_argument("--auto", action="store_true", help="Use built-in niche seeds")
    parser.add_argument("--limit", type=int, default=100, help="Results per seed")
    args = parser.parse_args()

    if args.niche not in NICHE_NAMES:
        print(f"Unknown niche: {args.niche}")
        print(f"Available: {', '.join(NICHE_NAMES.keys())}")
        sys.exit(1)

    custom = None
    if args.seeds:
        custom = [s.strip() for s in args.seeds.split(",")]
    elif args.seeds_file:
        custom = Path(args.seeds_file).read_text().strip().splitlines()

    run_research(args.niche, custom)
