#!/usr/bin/env python3
"""
qa-check.py — Step 5 automated QA for bulk affiliate title files.

Usage:
    python scripts/qa-check.py <niche-slug>
    python scripts/qa-check.py korean-skincare

Runs all 5 QA passes on outputs/<niche-slug>/bulk-combined.txt
Prints a pass/fail report with specific issues to fix.

Requires:
    - outputs/<slug>/bulk-combined.txt
    - outputs/<slug>/phase2-titles.txt  (to separate Phase 1 count)
"""

import re
import sys
import os
from collections import Counter
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────

STOP_WORDS = {'a', 'the', 'for', 'of', 'in', 'on', 'to', 'and', 'or', 'is', 'with', 'your', 'my'}
EXEMPT_PREFIXES = ('how-to-', 'what-is-', 'what-are-', 'what-causes-', 'what-does-', 'do-', 'does-')
# NOTE: 'is-*' slugs are NOT exempt — rewrite to remove the 'is' (e.g. is-air-frying-healthy → air-frying-healthy)
VALID_CATEGORIES = {'Best Products', 'Reviews', 'Buying Guides', 'Comparisons', 'How-To Guides', 'Tips & Care'}
ROUNDUP_CATS = {'Best Products', 'Reviews', 'Buying Guides', 'Comparisons'}
INFO_CATS = {'How-To Guides', 'Tips & Care'}
OF_MAX_LEN = 120
SLUG_MAX_WORDS = 6
COUNT_MIN = 150  # Phase 1 floor
COUNT_MAX = 270  # Phase 1 ceiling
ROUNDUP_MIN_PCT = 55
ROUNDUP_MAX_PCT = 65

# Known cannibalization patterns (title fragment pairs that likely share a SERP)
CANNIBAL_PAIRS = [
    ('buying guide', 'how to choose'),
    ('how to clean', 'cleaning tips'),
    ('how to use', 'tips for using'),
    ('how to care for', 'care tips'),
    ('vs ', 'comparison'),
]

# ── Helpers ─────────────────────────────────────────────────────────────────

def parse_line(line):
    """Extract title, outline_focus, slug, category from a ZimmWriter format line."""
    line = line.strip()
    if not line:
        return None
    m_of = re.search(r'\{outline_focus=([^}]+)\}', line)
    m_sl = re.search(r'\{slug=([^}]+)\}', line)
    m_ca = re.search(r'\{category=([^}]+)\}', line)
    title = line.split('{')[0].strip()
    return {
        'raw': line,
        'title': title,
        'outline_focus': m_of.group(1) if m_of else None,
        'slug': m_sl.group(1) if m_sl else None,
        'category': m_ca.group(1) if m_ca else None,
    }

def slug_word_count(slug):
    """Count effective words in slug, exempt prefix counts as 1."""
    parts = slug.split('-')
    for prefix in EXEMPT_PREFIXES:
        prefix_parts = prefix.rstrip('-').split('-')
        if slug.startswith(prefix):
            remainder = parts[len(prefix_parts):]
            return len(remainder) + 1  # prefix = 1 word
    return len(parts)

def slug_stop_words(slug):
    """Return list of stop words found in non-exempt slug positions."""
    # Compound product tokens exempt from stop-word check (e.g. 2-in-1, clip-on, over-sink)
    COMPOUND_EXEMPT = {'2-in-1', 'clip-on', 'over-sink', 'built-in', 'plug-in', 'all-in-1', 'all-in-one', 'all-on-4', 'all-on-6'}
    for compound in COMPOUND_EXEMPT:
        if compound in slug:
            slug = slug.replace(compound, compound.replace('-', '_'))  # temporarily mask
    parts = slug.split('-')
    for prefix in EXEMPT_PREFIXES:
        prefix_parts = prefix.rstrip('-').split('-')
        if slug.startswith(prefix):
            check_parts = parts[len(prefix_parts):]
            return [p for p in check_parts if p in STOP_WORDS and '_' not in p]
    return [p for p in parts if p in STOP_WORDS and '_' not in p]

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/qa-check.py <niche-slug>")
        print("Example: python scripts/qa-check.py korean-skincare")
        sys.exit(1)

    slug_arg = sys.argv[1]
    base = Path(__file__).parent.parent
    combined_path = base / 'outputs' / slug_arg / 'bulk-combined.txt'
    phase2_path   = base / 'outputs' / slug_arg / 'phase2-titles.txt'

    if not combined_path.exists():
        print(f"ERROR: {combined_path} not found. Run Steps 0–4 first.")
        sys.exit(1)

    lines_raw = combined_path.read_text(encoding='utf-8').splitlines()
    entries = [parse_line(l) for l in lines_raw if l.strip()]
    entries = [e for e in entries if e]  # remove None

    # Load phase2 titles for count separation
    phase2_titles = set()
    if phase2_path.exists():
        for l in phase2_path.read_text(encoding='utf-8').splitlines():
            t = l.split('{')[0].strip()
            if t:
                phase2_titles.add(t)

    phase1 = [e for e in entries if e['title'] not in phase2_titles]
    phase2 = [e for e in entries if e['title'] in phase2_titles]

    issues = {1: [], 2: [], 3: [], 4: [], 5: []}
    fixes  = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # ── Pass 1: Format ──────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("PASS 1 — FORMAT CHECK")
    print("="*60)
    for i, e in enumerate(entries, 1):
        if e['outline_focus'] is None:
            issues[1].append(f"  Line {i}: missing outline_focus — {e['raw'][:80]}")
        if e['slug'] is None:
            issues[1].append(f"  Line {i}: missing slug — {e['raw'][:80]}")
        if e['category'] is None:
            issues[1].append(f"  Line {i}: missing category — {e['raw'][:80]}")
        elif e['category'] not in VALID_CATEGORIES:
            issues[1].append(f"  Line {i}: invalid category '{e['category']}' — {e['title']}")
        if '{{' in e['raw']:
            issues[1].append(f"  Line {i}: double-brace error — {e['raw'][:80]}")
    if issues[1]:
        print(f"❌  {len(issues[1])} format issues:")
        for iss in issues[1]: print(iss)
    else:
        print(f"✅  All {len(entries)} lines pass format check")

    # ── Pass 2: Deduplication ───────────────────────────────────────────────
    print("\n" + "="*60)
    print("PASS 2 — DEDUPLICATION")
    print("="*60)
    slugs = [e['slug'] for e in entries if e['slug']]
    slug_counts = Counter(slugs)
    dupe_slugs = [(s, c) for s, c in slug_counts.items() if c > 1]
    titles_lower = [e['title'].lower() for e in entries]
    title_counts = Counter(titles_lower)
    dupe_titles = [(t, c) for t, c in title_counts.items() if c > 1]
    if dupe_slugs:
        issues[2].append(f"  {len(dupe_slugs)} duplicate slugs:")
        for s, c in dupe_slugs:
            issues[2].append(f"    '{s}' appears {c}x")
    if dupe_titles:
        issues[2].append(f"  {len(dupe_titles)} duplicate titles:")
        for t, c in dupe_titles:
            issues[2].append(f"    '{t}' appears {c}x")
    if issues[2]:
        print(f"❌  Duplicates found:")
        for iss in issues[2]: print(iss)
    else:
        print(f"✅  No duplicate slugs or titles ({len(slugs)} slugs checked)")

    # ── Pass 3: Cannibalization ─────────────────────────────────────────────
    print("\n" + "="*60)
    print("PASS 3 — CANNIBALIZATION CHECK")
    print("="*60)
    titles_lower_list = [(i, e['title'].lower()) for i, e in enumerate(entries)]
    found_pairs = []
    for frag1, frag2 in CANNIBAL_PAIRS:
        hits1 = [(i, t) for i, t in titles_lower_list if frag1 in t]
        hits2 = [(i, t) for i, t in titles_lower_list if frag2 in t]
        if hits1 and hits2:
            # Check they're not the same line
            idx1 = {i for i, t in hits1}
            idx2 = {i for i, t in hits2}
            if idx1 != idx2:
                found_pairs.append((frag1, frag2, hits1[:2], hits2[:2]))
    # Check roundup + review doubles
    best_titles = {e['title'].lower().replace('best ', '') for e in entries
                   if e['title'].lower().startswith('best ')}
    review_titles = {e['title'].lower().replace(' reviews', '').replace(' review', '')
                     for e in entries
                     if 'review' in e['title'].lower() and not e['title'].lower().startswith('best ')}
    overlap = best_titles & review_titles
    for o in overlap:
        issues[3].append(f"  ROUNDUP+REVIEW double: 'Best {o}' AND '{o} Reviews/Review'")
    for frag1, frag2, hits1, hits2 in found_pairs:
        issues[3].append(f"  CHECK '{frag1}' vs '{frag2}':")
        for i, t in hits1[:1]: issues[3].append(f"    [{i+1}] {t[:70]}")
        for i, t in hits2[:1]: issues[3].append(f"    [{i+1}] {t[:70]}")
    if issues[3]:
        print(f"⚠️   {len(issues[3])} potential cannibalization flags (review manually):")
        for iss in issues[3]: print(iss)
    else:
        print(f"✅  No cannibalization patterns detected")

    # ── Pass 4: Slug Quality ────────────────────────────────────────────────
    print("\n" + "="*60)
    print("PASS 4 — SLUG QUALITY")
    print("="*60)
    of_over = []
    for e in entries:
        if e['slug']:
            wc = slug_word_count(e['slug'])
            sw = slug_stop_words(e['slug'])
            if wc > SLUG_MAX_WORDS:
                issues[4].append(f"  TOO LONG ({wc}w): {e['slug']}")
            for w in sw:
                issues[4].append(f"  STOP WORD '{w}': {e['slug']}")
        if e['outline_focus'] and len(e['outline_focus']) > OF_MAX_LEN:
            of_over.append(f"  outline_focus {len(e['outline_focus'])}c: {e['title'][:60]}")
    if issues[4]:
        print(f"❌  {len(issues[4])} slug issues:")
        for iss in issues[4][:20]: print(iss)
        if len(issues[4]) > 20: print(f"  ... and {len(issues[4])-20} more")
    else:
        print(f"✅  All slugs pass (max 6 words, no stop words)")
    if of_over:
        print(f"❌  {len(of_over)} outline_focus fields exceed {OF_MAX_LEN} chars:")
        for iss in of_over[:10]: print(iss)
        print(f"  Fix: run trim script or re-trim manually to last word ≤{OF_MAX_LEN}c")
    else:
        print(f"✅  All outline_focus fields ≤{OF_MAX_LEN} chars")

    # ── Pass 5: Count & Split ───────────────────────────────────────────────
    print("\n" + "="*60)
    print("PASS 5 — COUNT & SPLIT")
    print("="*60)
    p1_roundup = [e for e in phase1 if e['category'] in ROUNDUP_CATS]
    p1_info    = [e for e in phase1 if e['category'] in INFO_CATS]
    total_p1   = len(phase1)
    r_pct = (len(p1_roundup) / total_p1 * 100) if total_p1 else 0
    i_pct = (len(p1_info) / total_p1 * 100) if total_p1 else 0

    count_ok = COUNT_MIN <= total_p1 <= COUNT_MAX
    split_ok = ROUNDUP_MIN_PCT <= r_pct <= ROUNDUP_MAX_PCT

    print(f"  Phase 1 titles : {total_p1}  (target {COUNT_MIN}–{COUNT_MAX})  {'✅' if count_ok else '❌'}")
    print(f"  Roundup        : {len(p1_roundup)} ({r_pct:.1f}%)  (target {ROUNDUP_MIN_PCT}–{ROUNDUP_MAX_PCT}%)  {'✅' if ROUNDUP_MIN_PCT <= r_pct <= ROUNDUP_MAX_PCT else '❌'}")
    print(f"  Informational  : {len(p1_info)} ({i_pct:.1f}%)  (target 35–45%)  {'✅' if 35 <= i_pct <= 45 else '❌'}")
    print(f"  Phase 2 deferred: {len(phase2)}")
    print(f"  Total in file  : {len(entries)}")

    if not count_ok:
        if total_p1 < COUNT_MIN:
            issues[5].append(f"  Too few Phase 1 titles ({total_p1}). Need {COUNT_MIN - total_p1} more.")
        else:
            issues[5].append(f"  Too many Phase 1 titles ({total_p1}). Cut {total_p1 - COUNT_MAX} or move to Phase 2.")
    if not split_ok:
        if r_pct > ROUNDUP_MAX_PCT:
            issues[5].append(f"  Roundup % too high ({r_pct:.1f}%). Add ~{int((r_pct - ROUNDUP_MAX_PCT)/100 * total_p1)} info titles or cut roundup.")
        else:
            issues[5].append(f"  Roundup % too low ({r_pct:.1f}%). Add ~{int((ROUNDUP_MIN_PCT - r_pct)/100 * total_p1)} roundup titles or cut info.")

    # ── Summary ─────────────────────────────────────────────────────────────
    # Pass 3 is SOFT (review manually) — does not count toward hard fail verdict
    hard_issues = sum(len(v) for k, v in issues.items() if k != 3) + len(of_over)
    soft_warnings = len(issues[3])
    total_issues = hard_issues + soft_warnings

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    verdict = "GO ✅" if hard_issues == 0 else "NEEDS FIXES ❌"
    print(f"  Niche:          {slug_arg}")
    print(f"  Hard issues:    {hard_issues}  (must fix before import)")
    print(f"  Soft warnings:  {soft_warnings}  (Pass 3 — review manually)")
    print(f"  VERDICT:        {verdict}")
    if hard_issues > 0:
        print("\n  Hard issues by pass:")
        for p, iss in issues.items():
            if p != 3 and iss:
                print(f"    Pass {p}: {len(iss)} issue(s)")
        if of_over:
            print(f"    Pass 4: {len(of_over)} outline_focus length issue(s)")
    print()
    return 0 if hard_issues == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
