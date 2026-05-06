#!/usr/bin/env python3
"""Pilot orchestrator: score baseline → enhance → score post → diff → write report.

Runs the pilot on a niche's local articles. Per spec §8:
  1. Load every <slug>.html (skip .bak files)
  2. Compute baseline QA score
  3. Run enhance_pipeline with hard regression guard
  4. Compute post-enhancement QA score
  5. Diff before/after via regression_test
  6. Aggregate into outputs/<niche>/pilot-report.md

Usage:
    python scripts/retrofit_pilot.py <niche>
    python scripts/retrofit_pilot.py <niche> --limit 10
    python scripts/retrofit_pilot.py <niche> --dry-run    # don't overwrite articles
    python scripts/retrofit_pilot.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_NICHES, NICHE_NAMES, get_articles_dir
from enhance_pipeline import enhance_with_regression_guard
from article_quality_score import score_article
from regression_test import diff_articles
from serp_brief import load_brief


def run_pilot(niche: str, limit: int | None = None,
              dry_run: bool = False) -> dict:
    """Run pilot on one niche. Returns aggregate dict. Writes pilot-report.md."""
    articles_dir = get_articles_dir(niche)
    qa_dir = articles_dir.parent / "qa-reports"
    enhance_dir = articles_dir.parent / "enhance-reports"
    qa_dir.mkdir(parents=True, exist_ok=True)
    enhance_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in articles_dir.glob("*.html")
                   if not p.name.endswith(".bak"))
    if limit:
        files = files[:limit]

    if not files:
        print(f"  No articles found in {articles_dir}")
        return {"error": "no articles", "niche": niche}

    print(f"\n{'='*60}")
    print(f"PILOT: {NICHE_NAMES.get(niche, niche)}")
    print(f"Articles: {len(files)}")
    print(f"Dry run:  {dry_run}")
    print(f"{'='*60}")

    per_article: list[dict] = []
    successes = 0
    regressions_aborted = 0
    score_deltas: list[float] = []
    start = time.time()

    for i, path in enumerate(files, 1):
        slug = path.stem
        before_html = path.read_text(encoding="utf-8")
        brief = load_brief(niche, slug)

        # Score baseline
        baseline_score = score_article(before_html, niche, slug, brief)

        # Run enhancement with regression guard
        after_html, enhance_report = enhance_with_regression_guard(
            before_html, niche, slug, articles_dir,
        )

        # Always write the enhance report
        enhance_path = enhance_dir / f"{slug}.json"
        enhance_path.write_text(
            json.dumps(enhance_report, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

        if enhance_report.get("status") == "regression_aborted":
            regressions_aborted += 1
            per_article.append({
                "slug": slug, "status": "regression_aborted",
                "regressions": enhance_report.get("regressions", []),
                "baseline_score": baseline_score.total,
            })
            print(f"  [{i}/{len(files)}] {slug:50.50} ABORT — "
                  f"{', '.join(enhance_report.get('regressions', []))}")
            continue

        # Score post-enhancement
        post_score = score_article(after_html, niche, slug, brief)

        # Diff
        diff = diff_articles(before_html, after_html)

        # Save QA report
        qa_path = qa_dir / f"{slug}.json"
        qa_path.write_text(json.dumps({
            "baseline_score": asdict(baseline_score),
            "post_score": asdict(post_score),
            "diff": asdict(diff),
            "score_delta": round(post_score.total - baseline_score.total, 2),
        }, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

        # Persist enhanced article (unless dry-run)
        if not dry_run:
            path.write_text(after_html, encoding="utf-8")
        successes += 1
        delta = post_score.total - baseline_score.total
        score_deltas.append(delta)
        per_article.append({
            "slug": slug, "status": "success",
            "baseline_score": baseline_score.total,
            "post_score": post_score.total,
            "delta": round(delta, 2),
            "regressed": diff.regressed,
            "word_count_delta": diff.word_count_delta,
        })

        delta_str = f"{'+' if delta >= 0 else ''}{delta:.2f}"
        print(f"  [{i}/{len(files)}] {slug:50.50} "
              f"{baseline_score.total:.1f} -> {post_score.total:.1f} ({delta_str})")

    elapsed = time.time() - start

    # Aggregate
    avg_delta = sum(score_deltas) / len(score_deltas) if score_deltas else 0.0
    improved_count = sum(1 for d in score_deltas if d >= 0.3)
    regressed_count = sum(1 for d in score_deltas if d < 0)
    n = len(score_deltas) if score_deltas else 1
    improved_pct = improved_count / n
    regressed_pct = regressed_count / n

    summary = {
        "niche": niche,
        "niche_display": NICHE_NAMES.get(niche, niche),
        "total_articles": len(files),
        "successes": successes,
        "regressions_aborted": regressions_aborted,
        "avg_score_delta": round(avg_delta, 2),
        "improved_count": improved_count,
        "improved_pct": round(improved_pct, 3),
        "regressed_count": regressed_count,
        "regressed_pct": round(regressed_pct, 3),
        "elapsed_seconds": round(elapsed, 1),
        "per_article": per_article,
        "dry_run": dry_run,
    }

    # Write per-niche pilot report
    report_path = articles_dir.parent / "pilot-report.md"
    report_path.write_text(_format_pilot_report(summary), encoding="utf-8")

    # Print summary
    print(f"\n{'-'*60}")
    print(f"  RESULTS: {summary['niche_display']}")
    print(f"  Total:               {summary['total_articles']}")
    print(f"  Successes:           {summary['successes']}")
    print(f"  Regression aborts:   {summary['regressions_aborted']}")
    print(f"  Avg score delta:     {summary['avg_score_delta']:+.2f}")
    print(f"  Improved (>=+0.3):    {summary['improved_count']} ({summary['improved_pct']:.0%})")
    print(f"  Regressed:           {summary['regressed_count']} ({summary['regressed_pct']:.0%})")
    print(f"  Elapsed:             {summary['elapsed_seconds']}s")
    print(f"\n  Pilot report: {report_path}")
    print(f"{'-'*60}")

    return summary


def _format_pilot_report(s: dict) -> str:
    lines = [
        f"# Pilot Report — {s['niche_display']}",
        "",
        f"- Niche slug: `{s['niche']}`",
        f"- Total articles: {s['total_articles']}",
        f"- Successes: {s['successes']}",
        f"- Regression aborts: {s['regressions_aborted']}",
        f"- Avg score delta: {s['avg_score_delta']:+.2f}",
        f"- Improved (>=+0.3): {s['improved_count']} ({s['improved_pct']:.0%})",
        f"- Regressed: {s['regressed_count']} ({s['regressed_pct']:.0%})",
        f"- Elapsed: {s['elapsed_seconds']}s",
        f"- Dry run: {s['dry_run']}",
        "",
        "## Success criteria check (per spec §8.3)",
        "",
    ]
    n = s["total_articles"]
    avg_pass = s["avg_score_delta"] >= 0.8
    improved_pass = s["improved_pct"] >= 0.80
    regressed_pass = s["regressed_pct"] <= 0.03
    aborts_pass = s["regressions_aborted"] == 0

    lines.extend([
        f"- avg_delta >= +0.8: **{'PASS' if avg_pass else 'FAIL'}** "
        f"(got {s['avg_score_delta']:+.2f})",
        f"- improved_pct >= 80%: **{'PASS' if improved_pass else 'FAIL'}** "
        f"(got {s['improved_pct']:.0%})",
        f"- regressed_pct ≤ 3%: **{'PASS' if regressed_pass else 'FAIL'}** "
        f"(got {s['regressed_pct']:.0%})",
        f"- regressions_aborted = 0: **{'PASS' if aborts_pass else 'FAIL'}** "
        f"(got {s['regressions_aborted']})",
        "",
        "## Per-article results",
        "",
        "| slug | status | baseline | post | delta | wc Δ |",
        "|---|---|---|---|---|---|",
    ])
    for a in s["per_article"]:
        if a["status"] == "success":
            delta_str = f"{'+' if a['delta'] >= 0 else ''}{a['delta']}"
            lines.append(
                f"| {a['slug']} | ✓ | {a['baseline_score']} | {a['post_score']} "
                f"| {delta_str} | {a.get('word_count_delta', 0):+} |"
            )
        else:
            lines.append(
                f"| {a['slug']} | ✗ {a['status']} | {a.get('baseline_score','-')} "
                f"| - | - | - |"
            )
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("niche", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true",
                   help="Don't overwrite articles; just report")
    args = p.parse_args()

    if args.all:
        for n in ALL_NICHES:
            try:
                run_pilot(n, limit=args.limit, dry_run=args.dry_run)
            except Exception as e:
                print(f"\nNICHE FAIL {n}: {e}\n")
    elif args.niche:
        run_pilot(args.niche, limit=args.limit, dry_run=args.dry_run)
    else:
        p.error("specify niche or --all")


if __name__ == "__main__":
    main()
