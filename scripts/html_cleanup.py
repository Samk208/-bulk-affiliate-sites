#!/usr/bin/env python3
"""
html_cleanup.py -- Fix Kimi K2.5 HTML formatting inconsistencies.

Kimi sometimes outputs:
- Raw text without <p> tags
- Markdown tables instead of HTML tables
- Markdown bold (**text**) instead of <strong>
- Markdown blockquotes (> text) instead of <blockquote>
- Markdown lists (- item) instead of <ul><li>
- ```html wrappers around content

Usage:
    python scripts/html_cleanup.py <niche-slug>
    python scripts/html_cleanup.py --all
    python scripts/html_cleanup.py <niche-slug> --dry-run   # Preview changes only
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_NICHES, NICHE_NAMES, get_articles_dir, get_niche_dir


def cleanup_html(html: str) -> tuple[str, list[str]]:
    """Clean up Kimi formatting issues. Returns (cleaned_html, list_of_changes)."""
    changes = []
    original = html

    # 1. Remove ```html wrapper if present
    if html.strip().startswith("```"):
        html = re.sub(r'^```(?:html)?\s*\n?', '', html.strip())
        html = re.sub(r'\n?```\s*$', '', html.strip())
        changes.append("Removed ```html wrapper")

    # 2. Convert markdown tables to HTML tables
    md_table_pattern = r'(\|[^\n]+\|\n\|[-: |]+\|\n(?:\|[^\n]+\|\n?)+)'
    md_tables = re.findall(md_table_pattern, html)
    for md_table in md_tables:
        html_table = markdown_table_to_html(md_table)
        html = html.replace(md_table, html_table)
        changes.append("Converted markdown table to HTML")

    # 3. Convert markdown bold to <strong>
    bold_count = len(re.findall(r'\*\*([^*]+)\*\*', html))
    if bold_count > 0:
        html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
        changes.append(f"Converted {bold_count} markdown bold to <strong>")

    # 4. Convert markdown italic to <em>
    # Only match single * not preceded/followed by * (avoid conflict with bold)
    italic_count = len(re.findall(r'(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)', html))
    if italic_count > 0:
        html = re.sub(r'(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)', r'<em>\1</em>', html)
        changes.append(f"Converted {italic_count} markdown italic to <em>")

    # 5. Convert markdown blockquotes to <blockquote>
    blockquote_lines = re.findall(r'^>\s*(.+)$', html, re.MULTILINE)
    if blockquote_lines:
        # Group consecutive > lines into single blockquotes
        html = convert_blockquotes(html)
        changes.append(f"Converted {len(blockquote_lines)} blockquote lines")

    # 6. Convert markdown unordered lists to HTML
    md_list_pattern = r'(?:^[-*]\s+.+\n?)+'
    md_lists = re.findall(md_list_pattern, html, re.MULTILINE)
    for md_list in md_lists:
        # Skip if it's inside an existing <ul> or <ol>
        pos = html.find(md_list)
        if pos > 0 and '<ul>' in html[max(0, pos-20):pos]:
            continue
        html_list = markdown_list_to_html(md_list)
        html = html.replace(md_list, html_list)
        changes.append("Converted markdown list to <ul>")

    # 7. Wrap orphan text lines in <p> tags
    lines = html.split('\n')
    wrapped_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            wrapped_lines.append('')
            continue
        # Skip lines that are already HTML elements
        if re.match(r'^<(?:h[1-6]|p|ul|ol|li|table|tr|th|td|thead|tbody|blockquote|div|script|strong|em|a|img|hr)', stripped, re.IGNORECASE):
            wrapped_lines.append(line)
            continue
        # Skip lines inside tables or lists
        if stripped.startswith('</'):
            wrapped_lines.append(line)
            continue
        # Skip empty or whitespace lines
        if len(stripped) < 5:
            wrapped_lines.append(line)
            continue
        # Wrap in <p> if it looks like a paragraph (30+ chars, no leading HTML)
        if len(stripped) > 30 and not stripped.startswith('<'):
            wrapped_lines.append(f'<p>{stripped}</p>')
            changes.append(f"Wrapped orphan text in <p>")
        else:
            wrapped_lines.append(line)

    html = '\n'.join(wrapped_lines)

    # 8. Clean up double <p> tags
    html = re.sub(r'<p>\s*<p>', '<p>', html)
    html = re.sub(r'</p>\s*</p>', '</p>', html)

    # 9. Remove excessive blank lines (3+ → 2)
    html = re.sub(r'\n{3,}', '\n\n', html)

    # Deduplicate change messages
    unique_changes = list(dict.fromkeys(changes))

    return html.strip(), unique_changes


def markdown_table_to_html(md_table: str) -> str:
    """Convert a markdown table to HTML table."""
    lines = [l.strip() for l in md_table.strip().split('\n') if l.strip()]
    if len(lines) < 2:
        return md_table

    # Parse header
    header_cells = [c.strip() for c in lines[0].split('|') if c.strip()]

    # Skip separator line (line 1)
    # Parse body rows
    body_rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if cells:
            body_rows.append(cells)

    # Build HTML
    html = '<table>\n<thead>\n<tr>\n'
    for cell in header_cells:
        html += f'<th>{cell}</th>\n'
    html += '</tr>\n</thead>\n<tbody>\n'
    for row in body_rows:
        html += '<tr>\n'
        for cell in row:
            html += f'<td>{cell}</td>\n'
        html += '</tr>\n'
    html += '</tbody>\n</table>'

    return html


def convert_blockquotes(html: str) -> str:
    """Convert markdown > lines to <blockquote> blocks."""
    lines = html.split('\n')
    result = []
    in_quote = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('>'):
            quote_text = stripped[1:].strip()
            if not in_quote:
                result.append('<blockquote>')
                in_quote = True
            if quote_text:
                # Check if it's an attribution line (-- Name)
                if quote_text.startswith('--') or quote_text.startswith('\u2014'):
                    result.append(f'<footer>{quote_text}</footer>')
                else:
                    result.append(f'<p>{quote_text}</p>')
        else:
            if in_quote:
                result.append('</blockquote>')
                in_quote = False
            result.append(line)

    if in_quote:
        result.append('</blockquote>')

    return '\n'.join(result)


def markdown_list_to_html(md_list: str) -> str:
    """Convert markdown - items to <ul><li> HTML."""
    items = re.findall(r'^[-*]\s+(.+)$', md_list, re.MULTILINE)
    if not items:
        return md_list

    html = '<ul>\n'
    for item in items:
        html += f'<li>{item.strip()}</li>\n'
    html += '</ul>'
    return html


def run_cleanup(niche_slug: str, dry_run: bool = False):
    """Clean up all articles in a niche."""
    niche_name = NICHE_NAMES.get(niche_slug, niche_slug)
    articles_dir = get_articles_dir(niche_slug)

    html_files = sorted(articles_dir.glob("*.html"))
    if not html_files:
        print(f"  No articles found in {articles_dir}")
        return

    print(f"\n{'='*50}")
    print(f"HTML CLEANUP: {niche_name} ({len(html_files)} articles)")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print(f"{'='*50}")

    total_changed = 0
    total_unchanged = 0

    for html_path in html_files:
        original = html_path.read_text(encoding="utf-8")
        cleaned, changes = cleanup_html(original)

        if changes:
            total_changed += 1
            if not dry_run:
                html_path.write_text(cleaned, encoding="utf-8")
            # Show first 3 changes per file
            change_summary = ", ".join(changes[:3])
            if len(changes) > 3:
                change_summary += f" (+{len(changes)-3} more)"
            print(f"  {'[DRY]' if dry_run else '[FIX]'} {html_path.stem}: {change_summary}")
        else:
            total_unchanged += 1

    print(f"\n  Changed: {total_changed} | Unchanged: {total_unchanged}")
    if dry_run and total_changed > 0:
        print(f"  Run without --dry-run to apply fixes")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/html_cleanup.py <niche-slug> [--dry-run]")
        print("       python scripts/html_cleanup.py --all [--dry-run]")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    niches = ALL_NICHES if sys.argv[1] == "--all" else [sys.argv[1]]

    for niche in niches:
        if not get_niche_dir(niche).exists():
            print(f"SKIP: {niche}")
            continue
        run_cleanup(niche, dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
