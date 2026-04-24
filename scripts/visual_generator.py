#!/usr/bin/env python3
"""
visual_generator.py -- Generate branded charts and infographics for articles.

Extracts comparison data, statistics, and process steps from article HTML,
then renders Plotly charts and styled HTML infographics as PNG images.

Usage:
    python scripts/visual_generator.py <niche-slug>              # Full niche
    python scripts/visual_generator.py <niche-slug> --limit 5    # Test batch
    python scripts/visual_generator.py <niche-slug> --slug <slug> # Single article
"""

import json
import re
import sys
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_NICHES, NICHE_NAMES, get_niche_dir, get_articles_dir

# -- Brand Config per niche (expandable) ------------------------------------
DEFAULT_BRAND = {
    "primary": "#1a237e",
    "secondary": "#4caf50",
    "accent": "#ff9800",
    "bg": "#ffffff",
    "text": "#333333",
    "font": "Inter, Arial, sans-serif",
}

NICHE_BRANDS = {
    "dog-comfort": {**DEFAULT_BRAND, "primary": "#2e7d32", "secondary": "#8bc34a", "accent": "#ff8f00"},
    "camping-gear": {**DEFAULT_BRAND, "primary": "#33691e", "secondary": "#689f38", "accent": "#f57c00"},
    "cat-care": {**DEFAULT_BRAND, "primary": "#6a1b9a", "secondary": "#ab47bc", "accent": "#e91e63"},
    "home-coffee": {**DEFAULT_BRAND, "primary": "#4e342e", "secondary": "#795548", "accent": "#ff6f00"},
    "mens-grooming": {**DEFAULT_BRAND, "primary": "#1565c0", "secondary": "#42a5f5", "accent": "#263238"},
    "oral-care": {**DEFAULT_BRAND, "primary": "#00838f", "secondary": "#26c6da", "accent": "#e53935"},
    "home-cleaning": {**DEFAULT_BRAND, "primary": "#0277bd", "secondary": "#4fc3f7", "accent": "#7cb342"},
    "healthy-cooking": {**DEFAULT_BRAND, "primary": "#e65100", "secondary": "#ff9800", "accent": "#388e3c"},
    "home-office": {**DEFAULT_BRAND, "primary": "#37474f", "secondary": "#78909c", "accent": "#ffab00"},
    "water-air-quality": {**DEFAULT_BRAND, "primary": "#01579b", "secondary": "#039be5", "accent": "#00c853"},
    "korean-skincare": {**DEFAULT_BRAND, "primary": "#ec407a", "secondary": "#f48fb1", "accent": "#7e57c2"},
    "makeup-beauty": {**DEFAULT_BRAND, "primary": "#ad1457", "secondary": "#e91e63", "accent": "#ff6f00"},
    "korean-medical-tourism": {**DEFAULT_BRAND, "primary": "#1565c0", "secondary": "#42a5f5", "accent": "#e53935"},
    "korean-used-cars": {**DEFAULT_BRAND, "primary": "#283593", "secondary": "#5c6bc0", "accent": "#f44336"},
}


def get_brand(niche_slug: str) -> dict:
    return NICHE_BRANDS.get(niche_slug, DEFAULT_BRAND)


# -- Chart extraction from article HTML ------------------------------------

def extract_tables_from_html(html: str) -> list[dict]:
    """Extract table data from HTML for potential chart conversion."""
    tables = []
    table_matches = re.findall(
        r'<table[^>]*>(.*?)</table>', html, re.DOTALL
    )
    for table_html in table_matches:
        headers = re.findall(r'<th[^>]*>(.*?)</th>', table_html, re.DOTALL)
        headers = [re.sub(r'<[^>]+>', '', h).strip() for h in headers]

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        data_rows = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if cells:
                data_rows.append([re.sub(r'<[^>]+>', '', c).strip() for c in cells])

        if headers and data_rows:
            tables.append({"headers": headers, "rows": data_rows})

    return tables


def extract_stats_from_html(html: str) -> list[dict]:
    """Extract statistics/numbers from article for potential visualization."""
    stats = []
    # Find patterns like "X% of...", "X out of Y", numbers with context
    patterns = [
        r'(\d+(?:\.\d+)?%)\s+(?:of\s+)?([^.;,<]+)',
        r'(\d+(?:\.\d+)?)\s+(?:times|x)\s+(?:more|less|faster|slower)\s+([^.;,<]+)',
        r'(\d+)\s+out\s+of\s+(\d+)\s+([^.;,<]+)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            stats.append({
                "value": match.group(1),
                "context": match.group(0)[:100],
            })
    return stats[:8]  # Cap at 8


# -- Chart generators -------------------------------------------------------

def create_comparison_chart(
    title: str,
    categories: list[str],
    values_a: list[float],
    values_b: list[float],
    label_a: str,
    label_b: str,
    brand: dict,
    output_path: Path,
) -> bool:
    """Create a horizontal bar comparison chart."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=categories, x=values_a, name=label_a,
        orientation='h', marker_color=brand["primary"],
        text=[f'{v}' for v in values_a], textposition='auto',
    ))
    fig.add_trace(go.Bar(
        y=categories, x=values_b, name=label_b,
        orientation='h', marker_color=brand["accent"],
        text=[f'{v}' for v in values_b], textposition='auto',
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=brand["text"])),
        barmode='group',
        font=dict(family=brand["font"], size=13, color=brand["text"]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor=brand["bg"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=20, r=20, t=60, b=20),
        width=800, height=450,
    )
    fig.write_image(str(output_path), scale=2)
    return True


def create_stat_chart(
    title: str,
    labels: list[str],
    values: list[float],
    brand: dict,
    output_path: Path,
    chart_type: str = "bar",
) -> bool:
    """Create a single-series bar or pie chart."""
    if chart_type == "pie":
        fig = go.Figure(go.Pie(
            labels=labels, values=values,
            marker=dict(colors=[brand["primary"], brand["secondary"],
                                brand["accent"], "#78909c", "#b0bec5"]),
            textinfo='label+percent', textfont_size=13,
        ))
    else:
        fig = go.Figure(go.Bar(
            x=labels, y=values,
            marker_color=[brand["primary"], brand["secondary"],
                          brand["accent"], "#78909c", "#b0bec5"][:len(labels)],
            text=[f'{v}' for v in values], textposition='auto',
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=brand["text"])),
        font=dict(family=brand["font"], size=13, color=brand["text"]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor=brand["bg"],
        margin=dict(l=20, r=20, t=60, b=20),
        width=700, height=400,
    )
    fig.write_image(str(output_path), scale=2)
    return True


def create_process_infographic(
    title: str,
    steps: list[dict],
    brand: dict,
    output_path: Path,
) -> str:
    """Create a process/steps infographic as styled HTML (for WP embedding)."""
    steps_html = ""
    for i, step in enumerate(steps, 1):
        steps_html += f"""
<div style="display:flex;align-items:flex-start;margin:16px 0;gap:16px;">
  <div style="min-width:48px;height:48px;background:{brand['primary']};color:white;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:1.2em;">{i}</div>
  <div style="flex:1;">
    <strong style="color:{brand['primary']};font-size:1.05em;">{step.get('name', f'Step {i}')}</strong>
    <p style="margin:4px 0 0 0;color:{brand['text']};">{step.get('description', '')}</p>
  </div>
</div>"""

    infographic_html = f"""
<div style="background:{brand['bg']};border:2px solid {brand['primary']};border-radius:12px;padding:24px;margin:24px 0;max-width:700px;">
  <h3 style="color:{brand['primary']};margin:0 0 16px 0;text-align:center;font-size:1.3em;">{title}</h3>
  {steps_html}
</div>"""
    return infographic_html


def create_key_stats_card(
    stats: list[dict],
    brand: dict,
) -> str:
    """Create a key statistics card as styled HTML for embedding."""
    cards_html = ""
    for stat in stats[:4]:
        cards_html += f"""
<div style="flex:1;min-width:140px;background:{brand['bg']};border:1px solid #e0e0e0;border-top:4px solid {brand['primary']};border-radius:8px;padding:16px;text-align:center;">
  <div style="font-size:2em;font-weight:bold;color:{brand['primary']};">{stat['value']}</div>
  <div style="font-size:0.85em;color:#666;margin-top:4px;">{stat['label']}</div>
</div>"""

    return f"""
<div style="display:flex;flex-wrap:wrap;gap:16px;margin:24px 0;justify-content:center;">
  {cards_html}
</div>"""


# -- Main pipeline: analyze article → generate visuals ---------------------

def generate_visuals_for_article(
    slug: str,
    html_content: str,
    niche_slug: str,
    images_dir: Path,
) -> dict:
    """Analyze article HTML and generate appropriate visuals.

    Returns dict of generated assets with their embed HTML/paths.
    """
    brand = get_brand(niche_slug)
    results = {"charts": [], "infographics": [], "stat_cards": []}

    # Extract data from article
    tables = extract_tables_from_html(html_content)
    stats = extract_stats_from_html(html_content)

    # Generate comparison chart from first table with numeric data
    for i, table in enumerate(tables[:2]):
        if len(table["headers"]) >= 3 and len(table["rows"]) >= 2:
            # Try to extract numeric values for charting
            chart_path = images_dir / f"{slug}-chart-{i+1}.png"
            results["charts"].append({
                "path": str(chart_path),
                "table_data": table,
                "generated": False,  # Will be generated by LLM-guided extraction
            })

    # Generate stat cards if we found statistics
    if stats:
        stat_items = []
        for s in stats[:4]:
            stat_items.append({
                "value": s["value"],
                "label": s["context"][:40],
            })
        if stat_items:
            card_html = create_key_stats_card(stat_items, brand)
            results["stat_cards"].append({"html": card_html})

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/visual_generator.py <niche-slug> [--limit N] [--slug <slug>]")
        sys.exit(1)

    niche_slug = sys.argv[1]
    limit = None
    target_slug = None

    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    if "--slug" in sys.argv:
        idx = sys.argv.index("--slug")
        if idx + 1 < len(sys.argv):
            target_slug = sys.argv[idx + 1]

    niche_dir = get_niche_dir(niche_slug)
    articles_dir = get_articles_dir(niche_slug)
    images_dir = niche_dir / "images"
    images_dir.mkdir(exist_ok=True)

    brand = get_brand(niche_slug)
    print(f"\nVisual Pipeline: {NICHE_NAMES.get(niche_slug, niche_slug)}")
    print(f"Brand: {brand['primary']} / {brand['secondary']} / {brand['accent']}")

    # Find articles to process
    html_files = sorted(articles_dir.glob("*.html"))
    if target_slug:
        html_files = [f for f in html_files if f.stem == target_slug]
    if limit:
        html_files = html_files[:limit]

    print(f"Articles to process: {len(html_files)}\n")

    total_charts = 0
    total_cards = 0

    for html_path in html_files:
        slug = html_path.stem
        html = html_path.read_text(encoding="utf-8")

        results = generate_visuals_for_article(slug, html, niche_slug, images_dir)

        n_charts = len(results["charts"])
        n_cards = len(results["stat_cards"])
        total_charts += n_charts
        total_cards += n_cards

        if n_charts or n_cards:
            print(f"  {slug}: {n_charts} chart candidates, {n_cards} stat cards")

    print(f"\nTotal: {total_charts} chart candidates, {total_cards} stat cards across {len(html_files)} articles")
    print(f"Images dir: {images_dir}")


if __name__ == "__main__":
    main()
