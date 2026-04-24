#!/usr/bin/env python3
"""
daily_runner.py -- Automated niche-per-day article generation.

Runs via Windows Task Scheduler. No Claude Code needed.
Handles: Kimi generation → HTML cleanup → QA → email report.

Cowork fallback (failed/truncated articles) handled manually next morning.

Usage:
    python scripts/daily_runner.py                    # Run next pending niche
    python scripts/daily_runner.py --niche dog-comfort # Run specific niche
    python scripts/daily_runner.py --status            # Show schedule status

Schedule file: outputs/generation-schedule.json
"""

import json
import smtplib
import subprocess
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_NICHES, NICHE_NAMES, get_niche_dir, get_articles_dir

PROJECT_ROOT = Path(__file__).parent.parent
SCHEDULE_FILE = PROJECT_ROOT / "outputs" / "generation-schedule.json"

# Email config — loaded from .env.cowork
import os
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "skonneh2020@gmail.com")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")  # Gmail app password

# Generation schedule: which niches run on which day
NICHE_SCHEDULE = [
    {"day": 1, "niches": ["dog-comfort"], "note": "90 articles"},
    {"day": 2, "niches": ["camping-gear"], "note": "76 articles"},
    {"day": 3, "niches": ["cat-care"], "note": "80 articles"},
    {"day": 4, "niches": ["home-coffee"], "note": "82 articles"},
    {"day": 5, "niches": ["mens-grooming"], "note": "94 articles"},
    {"day": 6, "niches": ["oral-care"], "note": "56 articles"},
    {"day": 7, "niches": ["home-cleaning"], "note": "82 articles"},
    {"day": 8, "niches": ["healthy-cooking"], "note": "86 articles"},
    {"day": 9, "niches": ["home-office"], "note": "80 articles"},
    {"day": 10, "niches": ["water-air-quality"], "note": "86 articles"},
    {"day": 11, "niches": ["korean-skincare"], "note": "79 articles"},
    {"day": 12, "niches": ["makeup-beauty"], "note": "74 articles"},
    {"day": 13, "niches": ["korean-medical-tourism"], "note": "113 articles"},
    {"day": 14, "niches": ["korean-used-cars"], "note": "67 articles"},
]


def load_schedule() -> dict:
    """Load or create the generation schedule tracker."""
    if SCHEDULE_FILE.exists():
        return json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    return {
        "created": datetime.now().isoformat(),
        "completed_niches": [],
        "current_day": 0,
        "history": [],
    }


def save_schedule(schedule: dict):
    schedule["last_updated"] = datetime.now().isoformat()
    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")


def get_next_niches(schedule: dict) -> tuple[list[str], int, str]:
    """Get the next niche(s) to run. Returns (niches, day_num, note)."""
    completed = set(schedule.get("completed_niches", []))
    for entry in NICHE_SCHEDULE:
        pending = [n for n in entry["niches"] if n not in completed]
        if pending:
            return pending, entry["day"], entry["note"]
    return [], 0, "All niches complete!"


def run_niche_pipeline(niche_slug: str) -> dict:
    """Run full pipeline for a niche: generate → cleanup → QA. Returns results dict."""
    scripts_dir = PROJECT_ROOT / "scripts"
    result = {
        "niche": niche_slug,
        "name": NICHE_NAMES.get(niche_slug, niche_slug),
        "started": datetime.now().isoformat(),
        "generation": {},
        "cleanup": {},
        "qa": {},
        "errors": [],
    }

    # Step 1: Generate articles via Kimi K2.5
    print(f"\n[1/3] Generating articles for {niche_slug}...")
    try:
        gen_result = subprocess.run(
            [sys.executable, str(scripts_dir / "article_generator.py"), niche_slug],
            capture_output=True, text=True, timeout=7200,  # 2 hour timeout
            cwd=str(PROJECT_ROOT),
        )
        result["generation"]["stdout"] = gen_result.stdout[-2000:]  # Last 2K chars
        result["generation"]["returncode"] = gen_result.returncode
        if gen_result.returncode != 0:
            result["errors"].append(f"Generator failed: {gen_result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        result["errors"].append("Generator timed out after 2 hours")
    except Exception as e:
        result["errors"].append(f"Generator error: {str(e)}")

    # Step 2: HTML cleanup
    print(f"[2/3] Cleaning HTML for {niche_slug}...")
    try:
        cleanup_result = subprocess.run(
            [sys.executable, str(scripts_dir / "html_cleanup.py"), niche_slug],
            capture_output=True, text=True, timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        result["cleanup"]["stdout"] = cleanup_result.stdout[-1000:]
        result["cleanup"]["returncode"] = cleanup_result.returncode
    except Exception as e:
        result["errors"].append(f"Cleanup error: {str(e)}")

    # Step 3: QA validation
    print(f"[3/3] Running QA for {niche_slug}...")
    try:
        qa_result = subprocess.run(
            [sys.executable, str(scripts_dir / "article_qa.py"), niche_slug],
            capture_output=True, text=True, timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        result["qa"]["stdout"] = qa_result.stdout[-1500:]
        result["qa"]["returncode"] = qa_result.returncode
    except Exception as e:
        result["errors"].append(f"QA error: {str(e)}")

    # Check for cowork queue
    cowork_queue_path = get_articles_dir(niche_slug) / "cowork-queue.json"
    if cowork_queue_path.exists():
        queue = json.loads(cowork_queue_path.read_text(encoding="utf-8"))
        result["cowork_needed"] = len(queue.get("slugs", []))
    else:
        result["cowork_needed"] = 0

    # Count results
    articles_dir = get_articles_dir(niche_slug)
    result["articles_generated"] = len(list(articles_dir.glob("*.html")))
    result["finished"] = datetime.now().isoformat()

    return result


def send_email_report(results: list[dict], day_num: int):
    """Send email report of today's generation run."""
    if not SMTP_USER or not SMTP_PASS:
        print("  Email not configured (no SMTP_USER/SMTP_PASS in .env.cowork)")
        print("  Set SMTP_USER and SMTP_PASS (Gmail app password) to enable notifications")
        return

    subject = f"Bulk Affiliate Day {day_num} Complete"

    body_lines = [f"Bulk Affiliate Sites - Day {day_num} Report", f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    total_articles = 0
    total_cowork = 0
    total_errors = 0

    for r in results:
        body_lines.append(f"=== {r['name']} ===")
        body_lines.append(f"  Articles generated: {r['articles_generated']}")
        body_lines.append(f"  Cowork fallback needed: {r['cowork_needed']}")
        if r["errors"]:
            body_lines.append(f"  ERRORS: {len(r['errors'])}")
            for e in r["errors"][:3]:
                body_lines.append(f"    - {e[:100]}")
        # Extract QA summary if available
        qa_out = r.get("qa", {}).get("stdout", "")
        for line in qa_out.split("\n"):
            if "SUMMARY" in line or "E-E-A-T" in line or "GEO" in line or "VERDICT" in line:
                body_lines.append(f"  {line.strip()}")
        body_lines.append("")

        total_articles += r["articles_generated"]
        total_cowork += r["cowork_needed"]
        total_errors += len(r["errors"])

    body_lines.append("--- TOTALS ---")
    body_lines.append(f"Articles: {total_articles}")
    body_lines.append(f"Cowork fallback: {total_cowork}")
    body_lines.append(f"Errors: {total_errors}")

    if total_cowork > 0:
        body_lines.append("")
        body_lines.append("ACTION NEEDED: Open Cowork to handle fallback articles.")
        body_lines.append("Run: python scripts/daily_runner.py --status")

    body = "\n".join(body_lines)

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = NOTIFY_EMAIL

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"  Email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  Email failed: {e}")
        # Save report locally as fallback
        report_path = PROJECT_ROOT / "outputs" / f"daily-report-day{day_num}.txt"
        report_path.write_text(body, encoding="utf-8")
        print(f"  Report saved to {report_path}")


def show_status():
    """Show current schedule status."""
    schedule = load_schedule()
    completed = set(schedule.get("completed_niches", []))

    print("\n" + "=" * 50)
    print("GENERATION SCHEDULE STATUS")
    print("=" * 50)

    for entry in NICHE_SCHEDULE:
        day = entry["day"]
        niches = entry["niches"]
        note = entry["note"]
        status_parts = []
        for n in niches:
            s = "DONE" if n in completed else "PENDING"
            status_parts.append(f"{NICHE_NAMES.get(n, n)}: {s}")
        status_str = " | ".join(status_parts)
        marker = "  " if any(n not in completed for n in niches) else "  "
        print(f"  Day {day:>2}: {status_str} ({note})")

    print(f"\n  Completed: {len(completed)}/14 niches")

    # Check for cowork queues
    cowork_total = 0
    for niche in ALL_NICHES:
        queue_path = get_articles_dir(niche) / "cowork-queue.json"
        if queue_path.exists():
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            count = len(queue.get("slugs", []))
            if count > 0:
                print(f"  COWORK NEEDED: {NICHE_NAMES.get(niche, niche)} — {count} articles")
                cowork_total += count

    if cowork_total == 0:
        print("  No Cowork fallback needed")
    print()


def main():
    if "--status" in sys.argv:
        show_status()
        return

    schedule = load_schedule()

    # Determine which niche(s) to run
    if "--niche" in sys.argv:
        idx = sys.argv.index("--niche")
        if idx + 1 < len(sys.argv):
            niches_to_run = [sys.argv[idx + 1]]
            day_num = 0
            note = "Manual run"
        else:
            print("Error: --niche requires a niche slug")
            sys.exit(1)
    else:
        niches_to_run, day_num, note = get_next_niches(schedule)

    if not niches_to_run:
        print("All niches complete! Nothing to run.")
        show_status()
        return

    print("=" * 60)
    print(f"DAILY RUNNER — Day {day_num}: {note}")
    print(f"Niches: {', '.join(NICHE_NAMES.get(n, n) for n in niches_to_run)}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    results = []
    for niche in niches_to_run:
        result = run_niche_pipeline(niche)
        results.append(result)

        if not result["errors"]:
            schedule["completed_niches"].append(niche)

        schedule["history"].append({
            "niche": niche,
            "day": day_num,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "articles": result["articles_generated"],
            "cowork_needed": result["cowork_needed"],
            "errors": len(result["errors"]),
        })

    schedule["current_day"] = day_num
    save_schedule(schedule)

    # Send email report
    print("\nSending email report...")
    send_email_report(results, day_num)

    # Final summary
    print("\n" + "=" * 60)
    print("DAILY RUN COMPLETE")
    for r in results:
        status = "OK" if not r["errors"] else "ERRORS"
        cowork = f" (Cowork: {r['cowork_needed']})" if r["cowork_needed"] > 0 else ""
        print(f"  {r['name']}: {r['articles_generated']} articles [{status}]{cowork}")
    print("=" * 60)


if __name__ == "__main__":
    main()
