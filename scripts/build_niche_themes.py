#!/usr/bin/env python3
"""
build_niche_themes.py — Generate per-niche GP child themes from golden template.

Each niche gets its own child theme with distinct:
  - CSS custom properties (colors, fonts)
  - Author name and bio in the disclosure
  - Theme name and description

This prevents Google's template fingerprinting across the 14 affiliate sites.

Usage:
    python scripts/build_niche_themes.py                 # Build all 14
    python scripts/build_niche_themes.py dog-comfort     # Build one
    python scripts/build_niche_themes.py --list          # Show style groups
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import NICHE_NAMES, SITE_STYLES, get_site_style

PROJECT_ROOT = Path(__file__).parent.parent
GOLDEN_DIR = PROJECT_ROOT / "templates" / "affiliate-gp-child"
OUTPUT_DIR = PROJECT_ROOT / "templates" / "niche-themes"


# Google Font import URLs per heading font family
FONT_IMPORTS = {
    "'Merriweather', Georgia, serif": "@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&display=swap');",
    "'Libre Baskerville', Georgia, serif": "@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&display=swap');",
    "'Playfair Display', Georgia, serif": "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&display=swap');",
    "'Roboto Slab', 'Segoe UI', sans-serif": "@import url('https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;700&display=swap');",
    "'Source Sans 3', 'Segoe UI', sans-serif": "@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap');",
    "'Inter', -apple-system, sans-serif": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');",
}


def build_style_css(niche_slug: str) -> str:
    """Generate style.css with niche-specific CSS custom properties."""
    style = get_site_style(niche_slug)
    display_name = NICHE_NAMES.get(niche_slug, niche_slug.replace("-", " ").title())
    css_vars = style["css_vars"]
    heading_font = css_vars.get("--font-heading", "-apple-system, BlinkMacSystemFont, sans-serif")
    font_import = FONT_IMPORTS.get(heading_font, "")

    # Read golden template CSS
    golden_css = (GOLDEN_DIR / "style.css").read_text(encoding="utf-8")

    # Replace the theme header
    header = f"""/*
Theme Name: {display_name} Affiliate
Theme URI: https://example.com
Description: Custom affiliate theme for {display_name} content. GeneratePress child.
Author: {style['author']['name']}
Template: generatepress
Version: 1.0
License: GNU General Public License v2 or later
*/"""

    # Strip the old header (everything before first non-comment CSS)
    lines = golden_css.split("\n")
    in_header = True
    body_lines = []
    for line in lines:
        if in_header:
            if line.strip() == "*/" and not body_lines:
                in_header = False
                continue
            continue
        body_lines.append(line)

    # Replace :root CSS variables
    root_block = ":root {\n"
    # Start with the golden template defaults, override with niche-specific
    default_vars = {
        "--aff-primary": "#1e40af",
        "--aff-primary-lt": "#3b82f6",
        "--aff-dark": "#1e293b",
        "--aff-text": "#334155",
        "--aff-text-muted": "#64748b",
        "--aff-bg": "#ffffff",
        "--aff-bg-alt": "#f8fafc",
        "--aff-border": "#e2e8f0",
        "--aff-success": "#10b981",
        "--aff-warning": "#f59e0b",
        "--aff-cta": "#f97316",
        "--aff-cta-hover": "#ea580c",
        "--font-body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "--font-heading": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    }
    default_vars.update(css_vars)

    for var_name, var_value in default_vars.items():
        root_block += f"    {var_name}: {var_value};\n"
    root_block += "}"

    # Rebuild the CSS body, replacing the old :root block
    css_body = "\n".join(body_lines)
    # Remove old :root block
    import re
    css_body = re.sub(r':root\s*\{[^}]*\}', '', css_body, count=1)

    # Add niche-specific accent to table headers
    th = style["table_header"]
    table_override = f"""
/* === Niche-specific table styling ({display_name}) === */
.wp-block-table th {{
    background: {th['bg']};
    color: {th['color']};
}}

.wp-block-table tr:nth-child(even) {{
    background: {style['table_alt_row']};
}}
"""

    # Add niche-specific blockquote styling
    q = style["quote"]
    quote_override = f"""
/* === Niche-specific quote styling === */
blockquote {{
    background: {q['bg']};
    border-left: 4px solid {q['border']};
    padding: 16px 20px;
    margin: 20px 0;
    border-radius: 4px;
    font-style: italic;
}}

blockquote footer {{
    color: {q['footer_color']};
}}
"""

    full_css = f"""{header}

{font_import}

/* ===== DESIGN TOKENS ({display_name}) ===== */
{root_block}

{css_body}
{table_override}
{quote_override}
"""
    return full_css


def build_functions_php(niche_slug: str) -> str:
    """Generate functions.php with niche-specific author and disclosure."""
    style = get_site_style(niche_slug)
    display_name = NICHE_NAMES.get(niche_slug, niche_slug.replace("-", " ").title())
    author = style["author"]

    # Read golden template functions.php
    golden_php = (GOLDEN_DIR / "functions.php").read_text(encoding="utf-8")

    # Replace the disclosure text to use the niche author
    old_disclosure = (
        "'<strong>Disclosure:</strong> As an Amazon Associate I earn from qualifying purchases. '"
        "\n        . 'This post may contain affiliate links at no extra cost to you.'"
    )
    new_disclosure = (
        f"'<strong>Disclosure:</strong> As an Amazon Associate I earn from qualifying purchases. '"
        f"\n        . 'This post may contain affiliate links at no extra cost to you.'"
        f"\n        . '<br><small>Reviewed by {author['name']}</small>'"
    )
    golden_php = golden_php.replace(old_disclosure, new_disclosure)

    # Update the doc comment
    golden_php = golden_php.replace(
        "Affiliate GP Child — Golden Template functions.php",
        f"{display_name} Affiliate — functions.php"
    )
    golden_php = golden_php.replace(
        "Clone this to all 14 niche sites via WP-CLI.",
        f"Generated by build_niche_themes.py for {display_name}."
    )

    return golden_php


def build_niche_theme(niche_slug: str):
    """Build a complete child theme for one niche."""
    theme_dir = OUTPUT_DIR / f"{niche_slug}-affiliate"
    theme_dir.mkdir(parents=True, exist_ok=True)

    # Write style.css
    style_css = build_style_css(niche_slug)
    (theme_dir / "style.css").write_text(style_css, encoding="utf-8")

    # Write functions.php
    functions_php = build_functions_php(niche_slug)
    (theme_dir / "functions.php").write_text(functions_php, encoding="utf-8")

    # Copy any additional files from golden template
    for f in GOLDEN_DIR.iterdir():
        if f.name not in ("style.css", "functions.php") and f.is_file():
            shutil.copy2(f, theme_dir / f.name)

    style = get_site_style(niche_slug)
    print(f"  Built: {theme_dir.name} (Group {style['group']}, author: {style['author']['name']})")


def show_groups():
    """Display style group summary."""
    groups = {}
    for niche, style in SITE_STYLES.items():
        g = style["group"]
        if g not in groups:
            groups[g] = []
        groups[g].append({
            "niche": niche,
            "author": style["author"]["name"],
            "primary": style["css_vars"]["--aff-primary"],
            "font": style["css_vars"]["--font-heading"].split(",")[0].strip("'\""),
            "toc": style["has_toc"],
            "qa_pos": style["quick_answer_position"],
        })

    for g_id in sorted(groups.keys()):
        niches = groups[g_id]
        print(f"\n  Group {g_id}:")
        for n in niches:
            toc_str = "TOC" if n["toc"] else "no-TOC"
            print(f"    {n['niche']:25s} | {n['primary']:8s} | {n['font']:20s} | {toc_str:6s} | QA:{n['qa_pos']:15s} | by {n['author']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        print("Site Style Groups:")
        show_groups()
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        niche = sys.argv[1]
        if niche not in SITE_STYLES:
            print(f"Unknown niche: {niche}")
            print(f"Available: {', '.join(SITE_STYLES.keys())}")
            sys.exit(1)
        print(f"Building theme for {niche}...")
        build_niche_theme(niche)
    else:
        print(f"Building {len(SITE_STYLES)} niche themes...")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for niche_slug in SITE_STYLES:
            build_niche_theme(niche_slug)

    print("\nDone. Themes in: templates/niche-themes/")
