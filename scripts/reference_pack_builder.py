"""Reference pack builder.

Initializes the directory + template files for a niche's reference pack.
Templates contain TBD markers that Cowork (Claude Code session) fills in
based on existing project artifacts.

Usage:
    python scripts/reference_pack_builder.py <niche> --init        # create templates
    python scripts/reference_pack_builder.py <niche> --validate    # validate existing pack
    python scripts/reference_pack_builder.py <niche> --verify-stats # verify stats via Perplexity
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from reference_pack_loader import load_pack, PackValidationError
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


from reference_pack_loader import _default_styles_root
STYLES_ROOT = _default_styles_root()


# ---- Templates -----------------------------------------------------------

VOICE_TEMPLATE = """---
niche: {niche}
first_person: TBD                 # allowed | third_only | mixed
gender_coded: TBD                 # male | female | any | none
authority_voices:
  - "..."
  - "..."
forbidden_voices: []
default_attribution_pattern: "according to {{authority_voice}}"
sentence_rhythm:
  short_sentence_ratio: 0.30
  paragraph_max_sentences: 3
tone_anchors:
  - calm and direct
  - specific before persuasive
emphasize:
  - real proof points
  - tradeoffs and caveats
avoid:
  - hype
  - hedge phrases
---

# Voice description for {niche}

(Cowork: write 200-400 words describing the brand voice for this niche,
drawing from existing articles, niche-validation-report.md, product-universe.md.
Include: persona, tone anchors, sentence rhythm, what to emphasize, what to
avoid. Be specific to this niche — generic voice descriptions don't help.)
"""


HUMOR_TEMPLATE = """defaults:
  level: warm                     # never | low | warm
  per_words: 400
  in_headings: false
  in_safety_content: false
  in_medical_content: false

per_post_type:
  buying-guide: { level: warm }
  review: { level: warm }
  how-to: { level: low }
  safety-guide: { level: never }
  clinical-explainer: { level: never }
  comparison: { level: low }
"""


STATS_TEMPLATE = """# stats.md — pre-vetted statistics for {niche}
# Each entry MUST have a verified source URL.
# Run --verify-stats to re-check entries via Perplexity.
# Format: list of dicts with claim/value/year/source/url/verified_at/applicable_to_*
[]
"""


STORIES_TEMPLATE = """# stories.md — first-person OR third-person attributed stories for {niche}
# Format depends on voice.md.first_person:
#   allowed   -> first-person operator stories (no 'attribution' field)
#   third_only -> third-person attributed (REQUIRED 'attribution' matching voice.md.authority_voices)
[]
"""


FORBIDDEN_TEMPLATE = """# Forbidden phrases for {niche}

Layered on top of `_global/banned-words.md`. Add niche-specific bans here.

## Banned phrases

- (none yet)
"""


USED_KEYWORDS_HEADER = "slug,primary_keyword,secondary_keywords,published_at\n"


FILES = [
    ("voice.md", VOICE_TEMPLATE),
    ("stats.md", STATS_TEMPLATE),
    ("stories.md", STORIES_TEMPLATE),
    ("humor.md", HUMOR_TEMPLATE),
    ("forbidden.md", FORBIDDEN_TEMPLATE),
    ("used-keywords.md", USED_KEYWORDS_HEADER),
]


# ---- Init ----------------------------------------------------------------

def init_pack(niche: str, force: bool = False) -> None:
    """Create the niche folder and template files."""
    niche_dir = STYLES_ROOT / niche
    niche_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nInitializing pack for '{niche}' at {niche_dir}\n")
    for fname, template in FILES:
        path = niche_dir / fname
        if path.exists() and not force:
            print(f"  SKIP {fname} (exists; pass --force to overwrite)")
            continue
        try:
            content = template.format(niche=niche)
        except (KeyError, IndexError):
            content = template
        path.write_text(content, encoding="utf-8")
        print(f"  WROTE {fname}")
    print(f"\nNext: Cowork drafts each file from existing project artifacts.")


# ---- Validate ------------------------------------------------------------

def validate_pack(niche: str) -> bool:
    try:
        pack = load_pack(niche, styles_root=STYLES_ROOT)
    except PackValidationError as e:
        print(f"FAIL: {e}")
        return False
    print(f"OK: pack for '{niche}' loaded successfully")
    print(f"  voice.first_person:  {pack.voice['first_person']}")
    print(f"  voice.gender_coded:  {pack.voice['gender_coded']}")
    print(f"  humor.defaults.level: {pack.humor['defaults']['level']}")
    print(f"  stats:                {len(pack.stats)} entries")
    print(f"  stories:              {len(pack.stories)} entries")
    print(f"  used_keywords:        {len(pack.used_keywords)} rows")
    return True


# ---- Verify stats via Perplexity ----------------------------------------

def verify_stats(niche: str) -> None:
    """For each stat in stats.md, query Perplexity to verify the claim."""
    pack = load_pack(niche, styles_root=STYLES_ROOT)
    if not pack.stats:
        print(f"No stats to verify in {niche}/stats.md")
        return
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set in .env.cowork")
        return

    print(f"\nVerifying {len(pack.stats)} stats for '{niche}' via Perplexity...\n")

    verified: list[dict] = []
    rejected: list[dict] = []
    from datetime import date
    today_iso = date.today().isoformat()

    for i, stat in enumerate(pack.stats, 1):
        claim = stat.get("claim", "")
        value = stat.get("value", "")
        source = stat.get("source", "")
        url = stat.get("url", "")
        prompt = (
            f"Verify this claim: '{claim}: {value}' "
            f"(currently cited as: {source}, {url}).\n\n"
            "Search current web sources. Answer in JSON only:\n"
            '{"verified": true|false, "source_url": "...", '
            '"published": "YYYY-MM-DD", "exact_match": true|false, '
            '"notes": "..."}\n'
        )
        result = _ask_perplexity(prompt)
        if result.get("verified") and result.get("exact_match"):
            stat["verified_at"] = today_iso
            if result.get("source_url"):
                stat["url"] = result["source_url"]
            verified.append(stat)
            print(f"  [{i}/{len(pack.stats)}] OK '{claim[:50]}'")
        else:
            rejected.append({"stat": stat, "perplexity_result": result})
            print(f"  [{i}/{len(pack.stats)}] REJECTED '{claim[:50]}': "
                  f"{result.get('notes', result.get('error', '?'))[:60]}")

    out_path = STYLES_ROOT / niche / "stats.md"
    yaml_dump = yaml.safe_dump(verified, allow_unicode=True, sort_keys=False)
    header = f"# stats.md — pre-vetted statistics for {niche}\n# Verified {today_iso}\n"
    out_path.write_text(header + yaml_dump, encoding="utf-8")

    rejected_path = STYLES_ROOT / niche / "stats-rejected.md"
    rejected_path.write_text(
        json.dumps(rejected, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  Verified: {len(verified)}")
    print(f"  Rejected: {len(rejected)} (see stats-rejected.md)")


def _ask_perplexity(prompt: str) -> dict:
    payload = {
        "model": "perplexity/sonar",
        "max_tokens": 1000,
        "messages": [
            {"role": "system",
             "content": "You verify factual claims against current web sources. "
                        "Reply only with JSON, no markdown fences."},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].lstrip("json").strip()
        return json.loads(content)
    except json.JSONDecodeError as e:
        return {"verified": False, "error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"verified": False, "error": str(e)[:200]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("niche")
    p.add_argument("--init", action="store_true")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--verify-stats", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    if args.init:
        init_pack(args.niche, force=args.force)
    elif args.validate:
        ok = validate_pack(args.niche)
        sys.exit(0 if ok else 1)
    elif args.verify_stats:
        verify_stats(args.niche)
    else:
        p.error("specify --init, --validate, or --verify-stats")


if __name__ == "__main__":
    main()
