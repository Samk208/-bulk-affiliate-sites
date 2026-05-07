# Bulk Affiliate Sites — Project Instructions

## Session Start Protocol
1. Read this file first
2. **Read `HANDOVER-2026-05-04.md`** — current state, article counts, next steps (THIS IS THE ONE TO READ)
3. Read `PILLAR-SELECTION.md` for content tiering strategy
4. Read `SITE-LAUNCH-PLAN.md` if working on WordPress / site launch
5. Read `IMAGE-GENERATION-PLAN.md` if working on image generation

> Previous handovers (stale, for history only): HANDOVER-2026-04-13.md, HANDOVER-2026-04-12.md, HANDOVER-2026-04-11.md

---

## Project Overview
14 affiliate niches, ~1,145 informational articles + ~1,700 roundup titles.
All title files DONE. Article generation pipeline built and tested.

### 14 Niches
1-10 (Amazon affiliate): Dog Comfort, Camping Gear, Cat Care, Home Coffee, Men's Grooming, Oral Care, Home Cleaning, Healthy Cooking, Home Office, Water & Air Quality
11-14 (Business-connected): Korean Skincare, Makeup & Beauty, Korean Medical Tourism, Korean Used Cars & Parts

---

## Content Tiering Strategy (CRITICAL — READ THIS)

### Tier 1 — Pillar Posts (Cowork Inline)
- **15-20 per niche** (~210-280 total)
- Full SERP research via WebSearch + competitor gap analysis + unique angles
- Written by Cowork (Opus quality) at $0 subscription
- 2,500+ words, visually rich, differentiated content
- **Phase A (launch):** 8-10 pillars per niche before site launch
- **Phase B (ongoing):** Remaining 7-10 added over first 4-6 weeks
- See `PILLAR-SELECTION.md` for exact articles per niche

### Tier 2 — Supporting Posts (Perplexity Sonar + Kimi K2.5)
- All remaining posts (~865-935 total)
- Perplexity Sonar research for factual grounding (needs PERPLEXITY_API_KEY in .env.cowork)
- Kimi K2.5 generation via OpenRouter ($0.015/article)
- 1,500-2,000 words

### Total estimated cost: ~$22-23 for all 1,145 articles

---

## Article Quality Rules (MANDATORY)

### 1. SKINNY PARAGRAPHS (HARD RULE)
- Maximum 2-3 sentences per paragraph
- **HARD LIMIT: 50 words per paragraph** — no exceptions
- One-sentence paragraphs are encouraged
- Break any paragraph over 50 words into two
- This is the #1 readability factor for mobile and SEO

### 2. Quick Answer Box Format
- Bullet list (3-4 `<li>` items), NOT paragraph text
- Styled purple box at very top of article
- This is what AI search engines (ChatGPT, Perplexity) cite

### 3. No Fabricated Data
- Only use verifiable facts, real brand names, real organizations
- Reference AKC, AVMA, VCA, PetMD, manufacturer specs — NOT invented studies
- Never fabricate expert quotes, statistics, or percentages
- If you can't verify it, use general consensus language ("veterinarians recommend...")

### 4. SERP Differentiation (Tier 1 only)
- Before writing any Tier 1 article, WebSearch the target keyword
- Identify what top 5-10 ranking articles cover
- Find GAPS — what they ALL miss
- Write the article to fill those gaps (this is the unique angle)
- Examples: apartment training for puppies, pathogen-specific disinfection, fear period training

### 5. Visual Elements (all tiers)
- Styled HTML callout boxes: Pro Tip (green), Warning (orange), Key Takeaway (blue)
- Quick Answer box (purple) with bullet list
- Expert quote blockquotes (gray)
- Styled tables with navy headers
- Use 2-3 Pro Tips, 1 Warning, 1-2 expert quotes, 1-2 tables per article
- All visual HTML is inline-styled for WordPress compatibility
- **IMPORTANT**: Callouts MUST be wrapped in styled `<div>` containers, not bare `<strong>` tags
- Kimi K2.5 often outputs bare callouts — `article_enhancer.py` fixes this automatically
- After generation, ALWAYS run `article_enhancer.py` then `article_qa.py` to verify

### 6. E-E-A-T Signals
- Experience: "After testing X over Y months..." / first-person scenarios
- Expertise: specific measurements, temperatures, ingredients, percentages
- Authority: expert quotes (real people only), cite organizations, "According to..."
- Trust: mention downsides honestly, "The one thing I didn't love...", "Last updated" date
- **Kimi K2.5 gap**: Articles typically score 5.0/10 E-E-A-T without enhancement
- **After enhancement**: ~5.9/10. For 7.0+ target, worst articles may need LLM rewrite pass
- `article_enhancer.py` adds experience + authority + expert quote + trust signals at $0

### 7. GEO Optimization
- Quick Answer box at top (AI search citation target)
- Question-based H3 subheadings
- Answer each H3 in the FIRST sentence
- Include 1+ statistic with source per H2 section
- Use "as of 2026" for temporal data

### 8. Banned Words
delve, tapestry, landscape, crucial, leverage, utilize, cutting-edge, game-changer, revolutionize, seamless, robust, furthermore, moreover, realm, symphony, bustling, innovative, uncover

### 9. Banned Intros
"In today's", "When it comes to", "If you're looking for", "Are you tired of", "In this article", "In today's fast-paced", "Have you ever wondered"

---

## Pipeline Commands

### Tier 1 — Pillar Posts (Cowork generates directly)
```bash
# 1. SERP research (Cowork does this inline via WebSearch)
# 2. Write article (Cowork writes directly to outputs/<niche>/articles/<slug>.html)
# 3. Post to WP as draft for review
```

### Tier 2 — Supporting Posts (automated pipeline)
```bash
python scripts/serp_researcher.py <niche>          # Step 1: Perplexity Sonar research
python scripts/article_generator.py <niche>         # Step 2: Kimi K2.5 generation
python scripts/html_cleanup.py <niche>              # Step 3: Fix Kimi formatting
python scripts/article_enhancer.py <niche>          # Step 4: Add E-E-A-T + visual elements (0 API cost)
python scripts/article_qa.py <niche>                # Step 5: Validate quality
python scripts/wp_importer.py <niche>               # Step 6: WXR XML with drip schedule
```

### Post-Generation Enhancement (MANDATORY — run after every batch)
The `article_enhancer.py` script fixes known Kimi K2.5 output gaps at zero LLM cost:
- **Wraps bare callouts** in styled `<div>` containers (Kimi outputs `<strong>Pro Tip:` without the background div)
- **Adds experience signals** ("After testing...", "In my experience...") — 2 per article
- **Adds authority citations** ("According to...", "Research published in...") where claims lack sourcing
- **Adds expert quotes** (styled `<blockquote>` with name/credentials) if article has none
- **Adds Key Takeaway box** before FAQ if missing
- **Adds "Last updated" date** if missing

Without this step, articles average E-E-A-T 5.0/10 and visuals 1.1/3. After: E-E-A-T ~5.9/10, visuals ~5.8/3.

```bash
python scripts/article_enhancer.py <niche>          # Apply enhancements
python scripts/article_enhancer.py <niche> --dry-run # Preview without saving
python scripts/article_enhancer.py --all             # All niches
```

### Known Kimi K2.5 Quality Gaps (what the enhancer fixes)
1. **Callout divs missing**: Kimi generates `<strong style="color:...">Pro Tip:</strong>` but not the styled `<div>` wrapper → QA can't detect them, WordPress renders them as plain text
2. **Experience signals absent**: Kimi writes in third-person by default, missing first-person "I tested" signals that E-E-A-T scoring requires
3. **Authority citations sparse**: Kimi makes claims without "according to" / research citations
4. **Expert quotes rare**: Most articles have 0 `<blockquote>` expert quotes
5. **Update date missing**: ~30% of articles lack "Last updated" signal

### Utilities
```bash
python scripts/link-mapper.py <niche>               # Internal link maps (DONE for all 14)
python scripts/visual_generator.py <niche>          # Plotly charts + stat cards
python scripts/post_samples.py                      # Post samples to LocalWP
```

---

## Output File Structure (per niche)

```
outputs/<niche>/
├── product-universe.md
├── keywords-raw.csv
├── authority-map.txt
├── informational-titles.txt
├── roundup-titles.txt
├── phase2-titles.txt
├── bulk-combined.txt
├── link-map.json
├── serp-research.json          ← Perplexity Sonar data
├── articles/
│   ├── <slug>.html             ← Article content
│   ├── <slug>.json             ← JSON-LD schema
│   ├── progress.json           ← Generation tracker
│   └── cowork-queue.json       ← Failed articles for Cowork
└── images/                     ← Visual assets (charts, infographics)
```

---

## LocalWP Test Site
- URL: http://localhost:10040
- User: skonneh18
- App Password: Q4Ab UFTA Jk90 nPO2 Sbaz mJDG  ← CURRENT (dev 2, 2026-04-12)
- Theme: GeneratePress (free)
- Plugins: Rank Math SEO, LiteSpeed Cache
- Current drafts: 5 old test articles (IDs 27-31) + 6 new pillar posts (pending import)
- Import pillars: copy `import-pillars.php` to WP root → run `wp eval-file import-pillars.php` in Local Site Shell
- Credentials file: `.env.wp` in project root

---

## Technical Notes
- DataForSEO: `labs_google_keyword_suggestions`, location=2840, en, limit=200
- OpenRouter API key in `_global/.env.cowork` (OPENROUTER_API_KEY)
- Perplexity API key in `.env.cowork` (PERPLEXITY_API_KEY) — verified working 2026-04-12
- Kimi K2.5 model: `moonshotai/kimi-k2.5` via OpenRouter
- Entity library: `scripts/entity_library.py` — Wikipedia sameAs for all 14 niches
- All visual HTML uses inline styles (no external CSS dependency)

---

## Anti-Cannibalization Rules
- No roundup + review double for same product
- No synonym roundups targeting same SERP
- No how-to + buying guide overlap on same topic
- Phase 2 head terms don't conflict with Phase 1 sub-types

## ZimmWriter Title Format
```
Title{outline_focus=buyer persona max 120 chars}{slug=url-slug-max-6-words}{category=Category}
```
Categories: Best Products | Reviews | Buying Guides | Comparisons | How-To Guides | Tips & Care

---

## Stack
- Python 3.13 (system-installed via scoop), no virtual env
- No `requirements.txt` / `pyproject.toml` — deps installed globally
- Key libs: `pytest`, `pyyaml`, `requests`, `anthropic`, `openai`
- LLM access: OpenRouter (Kimi K2.5 primary), Anthropic (Sonnet fallback), Perplexity (research/verification)
- SERP data: DataForSEO (live + on_page/content_parsing endpoints)
- WordPress target: LocalWP at `http://localhost:10040` (dev), VPS at `/opt/bulk-affiliate/` (prod)

## Commands
- Test: `python -m pytest tests/ -q`
- Single test file: `python -m pytest tests/test_<name>.py -v`
- QA on a niche: `python scripts/article_qa.py <niche>`
- Enhance pipeline: `python scripts/enhance_pipeline.py <niche>` (regression-guarded; writes `.bak`)
- Pilot orchestrator: `python scripts/retrofit_pilot.py <niche>` (full E2E with success-criteria check)
- Reference packs: `python scripts/reference_pack_builder.py <niche> --validate`

## Verification
Before declaring work done on pipeline scripts:
1. `python -m pytest tests/ -q` — full suite must pass
2. If touching enhancer / QA / brief / packs: dry-run on `dog-comfort` first (`--dry-run` flag where supported)
3. If touching cost-incurring code (LLM calls, DataForSEO): smoke-test with `--limit 1` before any batch run
4. Briefs/outputs must land in `<project>/outputs/`, NOT `<worktree>/outputs/` — see worktree-aware path pattern in `scripts/config.py::_resolve_outputs_dir`

## Don't touch
- `outputs/` — generated content, gitignored, shared across worktrees via worktree-aware paths
- `outputs/**/*.bak` — pre-enhancement originals kept by regression guard; the enhancer needs them to roll back on score regressions
- `.env.cowork`, `.env.wp` — credentials (never commit, never echo)
- `.claude/settings.local.json` — 600+ organic allow rules; don't try to clean it up without backing up first
- `outputs/**/progress.json` and `cowork-queue.json` — runtime state, machine-specific
