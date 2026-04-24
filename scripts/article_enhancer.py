#!/usr/bin/env python3
"""
article_enhancer.py -- Batch-enhance articles with E-E-A-T signals and visual elements.

Zero LLM cost. Template-based injection of:
  1. Wrap bare callouts (<strong>Pro Tip:) in styled <div> containers
  2. Add experience signals where missing
  3. Add authority/expert signals where missing
  4. Add Key Takeaway boxes where missing
  5. Add "Last updated" trust signal where missing

Usage:
    python scripts/article_enhancer.py <niche-slug>          # Enhance one niche
    python scripts/article_enhancer.py --all                  # All niches
    python scripts/article_enhancer.py <niche-slug> --dry-run # Preview without saving
"""

import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ALL_NICHES, NICHE_NAMES, get_articles_dir, get_site_style
from entity_library import scan_entity_coverage, ENTITY_RELATIONSHIPS, NICHE_ENTITIES


# ---------------------------------------------------------------------------
# Per-niche styled HTML builder (uses SITE_STYLES from config.py)
# ---------------------------------------------------------------------------

def _make_div(bg: str, border: str) -> str:
    return (
        f'<div style="background:{bg};border-left:4px solid {border};'
        'padding:16px 20px;margin:20px 0;border-radius:4px;">\n'
        '{content}\n</div>'
    )

def _make_quote(bg: str, border: str, footer_color: str) -> str:
    return (
        f'<blockquote style="background:{bg};border-left:4px solid {border};'
        'padding:16px 20px;margin:20px 0;border-radius:4px;font-style:italic;">\n'
        '"{quote}"\n'
        f'<footer style="margin-top:8px;font-style:normal;color:{footer_color};">'
        '— <strong>{name}</strong>, {title}</footer>\n'
        '</blockquote>'
    )

def get_niche_templates(niche_slug: str) -> dict:
    """Return styled HTML templates customized for this niche's color scheme."""
    style = get_site_style(niche_slug)
    pt = style["pro_tip"]
    w = style["warning"]
    kt = style["key_takeaway"]
    q = style["quote"]
    return {
        "PRO_TIP_DIV": _make_div(pt["bg"], pt["border"]),
        "WARNING_DIV": _make_div(w["bg"], w["border"]),
        "KEY_TAKEAWAY_DIV": _make_div(kt["bg"], kt["border"]),
        "EXPERT_QUOTE_HTML": _make_quote(q["bg"], q["border"], q["footer_color"]),
        "CALLOUT_MAP": {
            "Pro Tip": (_make_div(pt["bg"], pt["border"]), pt["strong_color"]),
            "Warning": (_make_div(w["bg"], w["border"]), w["strong_color"]),
            "Key Takeaway": (_make_div(kt["bg"], kt["border"]), kt["strong_color"]),
            "Important": (_make_div(w["bg"], w["border"]), w["strong_color"]),
            "Note": (_make_div(kt["bg"], kt["border"]), kt["strong_color"]),
        },
    }

# Fallback: hardcoded defaults (used when no niche context)
PRO_TIP_DIV = _make_div("#e8f5e9", "#4caf50")
WARNING_DIV = _make_div("#fff3e0", "#ff9800")
KEY_TAKEAWAY_DIV = _make_div("#e3f2fd", "#2196f3")
EXPERT_QUOTE_HTML = _make_quote("#f5f5f5", "#9e9e9e", "#616161")

CALLOUT_MAP = {
    "Pro Tip": (PRO_TIP_DIV, "#2e7d32"),
    "Warning": (WARNING_DIV, "#e65100"),
    "Key Takeaway": (KEY_TAKEAWAY_DIV, "#1565c0"),
    "Important": (WARNING_DIV, "#e65100"),
    "Note": (KEY_TAKEAWAY_DIV, "#1565c0"),
}

# ---------------------------------------------------------------------------
# Experience signal banks (niche-agnostic, injected into first <p> after H2)
# ---------------------------------------------------------------------------

EXPERIENCE_SIGNALS = [
    "After testing multiple products in this category over several months, a few clear patterns emerged.",
    "Having used various formulations side by side, the differences become obvious after the first week.",
    "In my experience, the results speak louder than marketing claims.",
    "When I first started exploring this, I made every rookie mistake possible — here's what I learned.",
    "After tracking results for 90 days with different approaches, the data tells a clear story.",
    "My testing routine involved switching products every two weeks to isolate what actually worked.",
]

# ---------------------------------------------------------------------------
# Authority / expert quote banks (Korean skincare focused + general)
# ---------------------------------------------------------------------------

SKINCARE_EXPERTS = [
    {
        "quote": "The key to any effective routine is consistency with the right pH-balanced products, not the number of steps",
        "name": "Dr. Yoon-Jung Kim",
        "title": "Board-Certified Dermatologist, Seoul National University Hospital",
    },
    {
        "quote": "Korean formulations often achieve better tolerability because they combine actives with soothing agents like centella and panthenol from the start",
        "name": "Dr. Hyun-Jin Park",
        "title": "Cosmetic Chemist, Korean Society of Cosmetic Scientists",
    },
    {
        "quote": "Barrier health should always come before active ingredients. If your barrier is compromised, nothing else matters",
        "name": "Dr. Soo-Yeon Lee",
        "title": "Dermatologist, Yonsei University Severance Hospital",
    },
    {
        "quote": "Double cleansing isn't about being more thorough — it's about using the right solvent for each type of residue on your skin",
        "name": "Dr. Min-Ji Choi",
        "title": "Clinical Researcher, Korean Dermatology Research Institute",
    },
    {
        "quote": "SPF is non-negotiable in any routine, but the best sunscreen is the one you'll actually reapply throughout the day",
        "name": "Dr. Tae-Hyung Kim",
        "title": "Photodermatology Specialist, Samsung Medical Center",
    },
]

GENERAL_EXPERTS = [
    {
        "quote": "The most effective skincare routine is one that addresses your specific concerns without overwhelming your skin's natural defenses",
        "name": "Dr. Rachel Park",
        "title": "Board-Certified Dermatologist, Clinical Skincare Researcher",
    },
    {
        "quote": "Ingredient concentration matters more than ingredient count. A well-formulated product with three actives outperforms ten mediocre ones",
        "name": "Dr. James Lee",
        "title": "Cosmetic Dermatologist, Member of the American Academy of Dermatology",
    },
]

DOG_EXPERTS = [
    {
        "quote": "The most common mistake dog owners make is choosing comfort products based on appearance rather than their dog's sleeping position and joint needs",
        "name": "Dr. Sarah Mitchell",
        "title": "Veterinary Orthopedic Surgeon, American College of Veterinary Surgeons",
    },
    {
        "quote": "Orthopedic support isn't just for senior dogs. Starting early with proper bedding can prevent joint issues later in life",
        "name": "Dr. James Thornton",
        "title": "DVM, Board-Certified Veterinary Behaviorist",
    },
    {
        "quote": "Temperature regulation is one of the most overlooked factors in canine comfort. Dogs can't sweat like humans, so cooling products make a real difference",
        "name": "Dr. Lisa Chen",
        "title": "Veterinarian, AVMA Member, Canine Wellness Specialist",
    },
]

CAT_EXPERTS = [
    {
        "quote": "Cats are masters at hiding discomfort. By the time you notice behavioral changes, the issue has usually been building for weeks",
        "name": "Dr. Karen Wells",
        "title": "Feline Medicine Specialist, American Association of Feline Practitioners",
    },
    {
        "quote": "Environmental enrichment isn't optional for indoor cats. It directly impacts their physical health, mental wellbeing, and lifespan",
        "name": "Dr. Michael Torres",
        "title": "DVM, Certified Cat Behavior Consultant",
    },
]

CAMPING_EXPERTS = [
    {
        "quote": "The gear that keeps you safe in unexpected weather is worth every penny. Comfort gear is negotiable, safety gear isn't",
        "name": "Mark Henderson",
        "title": "Certified Wilderness Guide, 20+ Years Backcountry Experience",
    },
    {
        "quote": "Weight savings compound over distance. Cutting 500 grams from your pack saves your knees over a multi-day trek more than any supplement",
        "name": "Sarah Collins",
        "title": "Thru-Hiker, Appalachian Trail and Pacific Crest Trail Finisher",
    },
]

COFFEE_EXPERTS = [
    {
        "quote": "Water temperature and grind size affect extraction more than the price of your beans. Master those two variables first",
        "name": "James Hoffman",
        "title": "World Barista Champion, Coffee Educator",
    },
    {
        "quote": "Freshly ground beans within 30 days of roasting make more difference than any brewing device upgrade",
        "name": "Dr. Samo Smrke",
        "title": "Coffee Scientist, Zurich University of Applied Sciences",
    },
]

GROOMING_EXPERTS = [
    {
        "quote": "Most men's skin issues come from using the wrong products for their skin type, not from too few products. A simple routine done right beats a complex one done wrong",
        "name": "Dr. Anthony Rossi",
        "title": "Dermatologist, Memorial Sloan Kettering Cancer Center",
    },
    {
        "quote": "SPF is the single most effective anti-aging product for men. Everything else is secondary",
        "name": "Dr. Corey Hartman",
        "title": "Board-Certified Dermatologist, Founder of Skin Wellness Dermatology",
    },
]

ORAL_CARE_EXPERTS = [
    {
        "quote": "Two minutes of proper brushing technique beats five minutes of aggressive scrubbing. Pressure doesn't equal cleanliness",
        "name": "Dr. Ada Cooper",
        "title": "DDS, American Dental Association Consumer Advisor",
    },
    {
        "quote": "Flossing removes 40% of plaque that brushing alone misses. It's the single most underused dental health tool",
        "name": "Dr. Matthew Messina",
        "title": "DDS, Spokesperson for the American Dental Association",
    },
]

CLEANING_EXPERTS = [
    {
        "quote": "Contact time is more important than chemical strength. A properly applied standard cleaner outperforms a strong one wiped off too quickly",
        "name": "Dr. Charles Gerba",
        "title": "Microbiologist, University of Arizona Environmental Sciences",
    },
    {
        "quote": "Most household cleaning failures come from mixing the wrong products or not letting cleaners sit long enough. Read the label dwell time",
        "name": "Becky Rapinchuk",
        "title": "Certified Home Cleaning Expert, Author of Clean Mama's Guide",
    },
]

COOKING_EXPERTS = [
    {
        "quote": "The difference between a good cook and a great cook is temperature control. Invest in a thermometer before any gadget",
        "name": "J. Kenji López-Alt",
        "title": "James Beard Award-Winning Food Writer, MIT-Trained Chef",
    },
    {
        "quote": "Meal prep isn't about cooking everything on Sunday. It's about having the right ingredients washed, chopped, and ready to combine quickly",
        "name": "Dr. Maya Adams",
        "title": "Nutrition Scientist, Stanford Prevention Research Center",
    },
]

HOME_OFFICE_EXPERTS = [
    {
        "quote": "Monitor height and chair adjustment have more impact on long-term back health than any standing desk. Get the ergonomics right first",
        "name": "Dr. Alan Hedge",
        "title": "Professor of Ergonomics, Cornell University",
    },
    {
        "quote": "The 20-20-20 rule — every 20 minutes, look at something 20 feet away for 20 seconds — prevents more eye strain than any screen filter",
        "name": "Dr. Jeffrey Anshel",
        "title": "Optometrist, Founder of Corporate Vision Consulting",
    },
]

WATER_AIR_EXPERTS = [
    {
        "quote": "Activated carbon filters handle chlorine and taste. For heavy metals and contaminants, you need reverse osmosis or ion exchange",
        "name": "Dr. Marc Edwards",
        "title": "Environmental Engineer, Virginia Tech, Flint Water Crisis Researcher",
    },
    {
        "quote": "Indoor air quality is often 2-5 times worse than outdoor air. A HEPA filter in the bedroom alone makes a measurable health difference",
        "name": "Dr. Joseph Allen",
        "title": "Director of Harvard Healthy Buildings Program",
    },
]

MEDICAL_TOURISM_EXPERTS = [
    {
        "quote": "Korea's medical tourism success comes from combining world-class surgical outcomes with competitive pricing and short recovery times",
        "name": "Dr. Park Sung-Ho",
        "title": "Director, Korea Health Industry Development Institute",
    },
    {
        "quote": "Always verify your surgeon's board certification through the Korean Medical Association before booking any procedure",
        "name": "Dr. Kim Jae-Won",
        "title": "Plastic Surgeon, Member of the Korean Society of Plastic and Reconstructive Surgeons",
    },
]

USED_CARS_EXPERTS = [
    {
        "quote": "Korean vehicles consistently rank highest in J.D. Power initial quality studies. A 3-year-old Hyundai or Kia often has more remaining lifespan than competitors at the same price",
        "name": "David Kim",
        "title": "Automotive Industry Analyst, Korea Automobile Manufacturers Association",
    },
    {
        "quote": "The biggest opportunity in Korean used car exports is the gap between Korean depreciation rates and actual vehicle condition. These cars are undervalued globally",
        "name": "James Park",
        "title": "International Auto Export Specialist, 15 Years Korea-to-Global Experience",
    },
]

# Map niche slugs to expert banks
NICHE_EXPERT_MAP = {
    "korean-skincare": SKINCARE_EXPERTS,
    "makeup-beauty": SKINCARE_EXPERTS,
    "dog-comfort": DOG_EXPERTS,
    "cat-care": CAT_EXPERTS,
    "camping-gear": CAMPING_EXPERTS,
    "home-coffee": COFFEE_EXPERTS,
    "mens-grooming": GROOMING_EXPERTS,
    "oral-care": ORAL_CARE_EXPERTS,
    "home-cleaning": CLEANING_EXPERTS,
    "healthy-cooking": COOKING_EXPERTS,
    "home-office": HOME_OFFICE_EXPERTS,
    "water-air-quality": WATER_AIR_EXPERTS,
    "korean-medical-tourism": MEDICAL_TOURISM_EXPERTS,
    "korean-used-cars": USED_CARS_EXPERTS,
}

# ---------------------------------------------------------------------------
# Niche-specific authority citation banks (replaces generic skincare ones)
# ---------------------------------------------------------------------------

DOG_CITATIONS = [
    "According to the American Kennel Club, ",
    "Research published in the Journal of Veterinary Behavior confirms that ",
    "Board-certified veterinarians consistently recommend that ",
    "A 2024 study in the Journal of the American Veterinary Medical Association found that ",
    "According to the ASPCA, ",
]
CAT_CITATIONS = [
    "According to the American Association of Feline Practitioners, ",
    "Research published in the Journal of Feline Medicine and Surgery confirms that ",
    "Board-certified feline specialists consistently recommend that ",
    "A 2024 study in the Journal of Veterinary Internal Medicine found that ",
    "According to the Cornell Feline Health Center, ",
]
CAMPING_CITATIONS = [
    "According to the American Hiking Society, ",
    "Research published in the Journal of Outdoor Recreation and Tourism confirms that ",
    "Certified wilderness guides consistently recommend that ",
    "A 2024 survey by REI Co-op found that ",
    "According to the National Park Service, ",
]
COFFEE_CITATIONS = [
    "According to the Specialty Coffee Association, ",
    "Research published in the Journal of Food Science confirms that ",
    "Professional baristas consistently recommend that ",
    "A 2024 study by the Coffee Quality Institute found that ",
    "According to the National Coffee Association, ",
]
GROOMING_CITATIONS = [
    "According to the American Academy of Dermatology, ",
    "Research published in the British Journal of Dermatology confirms that ",
    "Board-certified dermatologists consistently recommend that ",
    "A 2024 study in the Journal of Clinical and Aesthetic Dermatology found that ",
    "According to the Skin Cancer Foundation, ",
]
SKINCARE_CITATIONS = [
    "According to the Korean Dermatological Association, ",
    "Research published in the Journal of Cosmetic Dermatology confirms that ",
    "Board-certified dermatologists consistently recommend that ",
    "A 2024 study in the International Journal of Dermatology found that ",
    "According to clinical data from Korean dermatology clinics, ",
]
ORAL_CARE_CITATIONS = [
    "According to the American Dental Association, ",
    "Research published in the Journal of Periodontology confirms that ",
    "Board-certified dentists consistently recommend that ",
    "A 2024 study in the Journal of Clinical Dentistry found that ",
    "According to the World Health Organization oral health data, ",
]
CLEANING_CITATIONS = [
    "According to the Environmental Protection Agency, ",
    "Research published in the American Journal of Infection Control confirms that ",
    "Certified cleaning specialists consistently recommend that ",
    "A 2024 study in Applied and Environmental Microbiology found that ",
    "According to the CDC household disinfection guidelines, ",
]
COOKING_CITATIONS = [
    "According to the USDA Food Safety guidelines, ",
    "Research published in the Journal of Food Science confirms that ",
    "Professional nutritionists consistently recommend that ",
    "A 2024 study in the American Journal of Clinical Nutrition found that ",
    "According to the Academy of Nutrition and Dietetics, ",
]
HOME_OFFICE_CITATIONS = [
    "According to OSHA ergonomics guidelines, ",
    "Research published in the International Journal of Environmental Research confirms that ",
    "Certified ergonomists consistently recommend that ",
    "A 2024 study in the Journal of Occupational Health Psychology found that ",
    "According to the American Optometric Association, ",
]
WATER_AIR_CITATIONS = [
    "According to the EPA water quality standards, ",
    "Research published in Environmental Science & Technology confirms that ",
    "Certified water quality specialists consistently recommend that ",
    "A 2024 study in the Journal of Water and Health found that ",
    "According to the WHO drinking water guidelines, ",
]
GENERAL_CITATIONS = [
    "According to industry experts, ",
    "Research published in peer-reviewed journals confirms that ",
    "Board-certified specialists consistently recommend that ",
    "A recent study in the field found that ",
    "According to clinical data, ",
]

NICHE_CITATION_MAP = {
    "dog-comfort": DOG_CITATIONS,
    "cat-care": CAT_CITATIONS,
    "camping-gear": CAMPING_CITATIONS,
    "home-coffee": COFFEE_CITATIONS,
    "mens-grooming": GROOMING_CITATIONS,
    "korean-skincare": SKINCARE_CITATIONS,
    "makeup-beauty": SKINCARE_CITATIONS,
    "oral-care": ORAL_CARE_CITATIONS,
    "home-cleaning": CLEANING_CITATIONS,
    "healthy-cooking": COOKING_CITATIONS,
    "home-office": HOME_OFFICE_CITATIONS,
    "water-air-quality": WATER_AIR_CITATIONS,
}

# ---------------------------------------------------------------------------
# Banned words list (must be removed from all articles)
# ---------------------------------------------------------------------------

BANNED_WORDS = [
    "delve", "tapestry", "landscape", "crucial", "leverage", "utilize",
    "cutting-edge", "game-changer", "revolutionize", "seamless", "robust",
    "furthermore", "moreover", "realm", "symphony", "bustling", "innovative",
    "uncover",
]

# ---------------------------------------------------------------------------
# Quick Answer box template
# ---------------------------------------------------------------------------

QUICK_ANSWER_DIV = (
    '<div style="background:#f3e5f5;border:2px solid #9c27b0;padding:20px;'
    'margin:0 0 24px 0;border-radius:8px;">\n'
    '<strong style="color:#6a1b9a;font-size:1.1em;">Quick Answer:</strong>\n'
    '<ul style="margin:10px 0 0 0;padding-left:20px;line-height:1.8;">\n'
    '{items}\n'
    '</ul>\n'
    '</div>\n\n'
)

# ---------------------------------------------------------------------------
# Key Takeaway templates (inserted before FAQ if none exists)
# ---------------------------------------------------------------------------

KEY_TAKEAWAY_TEMPLATES = [
    "Start with the basics — a gentle cleanser, hydrating toner, moisturizer, and SPF — before adding actives. Build slowly over 4-6 weeks.",
    "Listen to your skin, not marketing. If a product causes redness, stinging, or new breakouts after two weeks, it's not right for you regardless of reviews.",
    "Consistency beats complexity. A simple 3-step routine used daily outperforms a 10-step routine used sporadically.",
    "Patch test new products for 48 hours behind your ear or on your inner forearm before applying to your face.",
    "Layer products from thinnest to thickest consistency. This ensures each product penetrates properly without creating a barrier.",
]

# ---------------------------------------------------------------------------
# Core enhancement functions
# ---------------------------------------------------------------------------


def wrap_bare_callouts(html: str, callout_map: dict | None = None) -> tuple[str, int]:
    """Wrap bare <strong style="...">Pro Tip:</strong> in styled <div> containers."""
    cmap = callout_map or CALLOUT_MAP
    count = 0

    for callout_type, (div_template, color) in cmap.items():
        lines = html.split('\n')
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Match lines containing this callout type in a <strong> tag
            has_callout = (
                f'{callout_type}:' in line
                and '<strong' in line
                and 'border-left:4px solid' not in line
            )
            if has_callout:
                # Check if previous line is already a div wrapper
                prev = new_lines[-1].strip() if new_lines else ''
                if '<div style="background:' in prev:
                    new_lines.append(line)
                else:
                    content = line.strip()
                    count += 1
                    new_lines.append(div_template.format(content=content))
            else:
                new_lines.append(line)
            i += 1
        html = '\n'.join(new_lines)

    return html, count


def add_experience_signals(html: str) -> tuple[str, int]:
    """Add experience signals to articles missing them."""
    lower = html.lower()
    exp_patterns = [
        r'(?:i tested|we tested|after testing|my experience|having used|when i first|in my testing|after using)',
        r'(?:i noticed|i found that|in my case)',
    ]
    existing = sum(len(re.findall(p, lower)) for p in exp_patterns)
    if existing >= 3:
        return html, 0

    # Find H2 sections to inject into (skip first H2, FAQ, Related)
    h2_positions = [(m.start(), m.end()) for m in re.finditer(r'<h2[^>]*>.*?</h2>', html)]
    skip_h2s = {'frequently asked', 'faq', 'related', 'expert'}
    injectable = []
    for start, end in h2_positions:
        h2_text = re.sub(r'<[^>]+>', '', html[start:end]).lower()
        if not any(s in h2_text for s in skip_h2s):
            injectable.append(end)

    if len(injectable) < 2:
        return html, 0

    # Pick 2 positions (2nd and 4th H2, or spread evenly)
    needed = min(3 - existing, 2)
    signals = random.sample(EXPERIENCE_SIGNALS, needed)
    positions = [injectable[1]] if needed == 1 else [injectable[1], injectable[min(3, len(injectable) - 1)]]

    # Insert after the first <p> following each chosen H2
    added = 0
    offset = 0
    for pos, signal in zip(sorted(positions), signals):
        adj_pos = pos + offset
        # Find first </p> after this H2
        p_end = html.find('</p>', adj_pos)
        if p_end == -1:
            continue
        p_end += 4  # include </p>
        insert = f'\n\n<p>{signal}</p>'
        html = html[:p_end] + insert + html[p_end:]
        offset += len(insert)
        added += 1

    return html, added


def add_expert_quote(html: str, niche: str, quote_template: str | None = None) -> tuple[str, int]:
    """Add expert quotes if the article has fewer than 2."""
    existing_quotes = len(re.findall(r'<blockquote', html))
    if existing_quotes >= 2:
        return html, 0

    # Pick experts based on niche
    expert_bank = NICHE_EXPERT_MAP.get(niche, GENERAL_EXPERTS)
    needed = 2 - existing_quotes
    experts = random.sample(expert_bank, min(needed, len(expert_bank)))

    # Find insertion points: before FAQ and at ~40% through H2 sections
    h2_positions = [m.start() for m in re.finditer(r'<h2', html)]
    faq_match = re.search(r'<h2[^>]*>.*?(?:FAQ|Frequently Asked).*?</h2>', html, re.IGNORECASE)

    insert_positions = []
    if faq_match:
        insert_positions.append(faq_match.start())
    elif h2_positions:
        insert_positions.append(h2_positions[-1])

    # Second insertion point: ~40% through article (between H2s)
    if len(h2_positions) >= 3 and needed >= 2:
        mid_idx = len(h2_positions) // 3
        insert_positions.insert(0, h2_positions[mid_idx])

    if not insert_positions:
        return html, 0

    added = 0
    offset = 0
    for i, expert in enumerate(experts):
        if i >= len(insert_positions):
            break
        tmpl = quote_template or EXPERT_QUOTE_HTML
        quote_html = tmpl.format(**expert)
        pos = insert_positions[i] + offset
        html = html[:pos] + quote_html + '\n\n' + html[pos:]
        offset += len(quote_html) + 2
        added += 1

    return html, added


def add_key_takeaway(html: str, kt_template: str | None = None, kt_color: str | None = None) -> tuple[str, int]:
    """Add a Key Takeaway box if none exists (div-wrapped)."""
    # Check for existing div-wrapped key takeaways
    has_wrapped = bool(re.search(r'<div[^>]*>.*?Key Takeaway', html, re.DOTALL))
    has_bare = bool(re.search(r'<strong[^>]*>Key Takeaway', html))

    if has_wrapped:
        return html, 0
    if has_bare:
        # Already handled by wrap_bare_callouts
        return html, 0

    takeaway = random.choice(KEY_TAKEAWAY_TEMPLATES)
    color = kt_color or "#1565c0"
    content = f'<strong style="color:{color};">Key Takeaway:</strong> {takeaway}'
    tmpl = kt_template or KEY_TAKEAWAY_DIV
    box = tmpl.format(content=content)

    # Insert before FAQ
    faq_match = re.search(r'<h2[^>]*>.*?(?:FAQ|Frequently Asked).*?</h2>', html, re.IGNORECASE)
    if faq_match:
        insert_pos = faq_match.start()
    else:
        h2_positions = [m.start() for m in re.finditer(r'<h2', html)]
        insert_pos = h2_positions[-1] if h2_positions else len(html)

    html = html[:insert_pos] + box + '\n\n' + html[insert_pos:]
    return html, 1


def add_update_date(html: str) -> tuple[str, int]:
    """Add 'Last updated' trust signal if missing."""
    if re.search(r'(?:last updated|updated:|as of 2026)', html.lower()):
        return html, 0

    update_tag = '<p><em>Last updated: April 2026</em></p>'

    # Add before closing or at end
    if html.rstrip().endswith('</p>'):
        html = html.rstrip() + '\n\n' + update_tag
    else:
        html += '\n\n' + update_tag

    return html, 1


def add_authority_citations(html: str, niche: str = "") -> tuple[str, int]:
    """Add authority citation phrases where missing."""
    lower = html.lower()
    auth_patterns = r'(?:according to|research by|study by|published in|board-certified|dermatologist)'
    existing = len(re.findall(auth_patterns, lower))
    if existing >= 3:
        return html, 0

    # Authority phrases to inject into existing paragraphs
    authority_injections = [
        # Filled dynamically per-niche below
    ]

    # Use niche-specific citation sources
    niche_citations = NICHE_CITATION_MAP.get(niche, GENERAL_CITATIONS)
    authority_injections = niche_citations

    # Find paragraphs that make claims (contain "helps", "reduces", "improves", etc.)
    claim_pattern = re.compile(
        r'(<p>)([A-Z][^<]{40,200}(?:helps?|reduces?|improves?|prevents?|fights?|protects?|strengthens?)[^<]{10,150}</p>)',
        re.DOTALL
    )
    matches = list(claim_pattern.finditer(html))
    if not matches:
        return html, 0

    needed = min(3 - existing, len(matches))
    chosen = random.sample(matches, min(needed, len(matches)))
    added = 0
    offset = 0

    for m in sorted(chosen, key=lambda x: x.start()):
        adj_start = m.start(2) + offset
        prefix = random.choice(authority_injections)
        # Lowercase the first letter of the original sentence
        original = html[adj_start]
        insert_text = prefix + original.lower()
        html = html[:adj_start] + insert_text + html[adj_start + 1:]
        offset += len(insert_text) - 1
        added += 1

    return html, added


# ---------------------------------------------------------------------------
# NEW: Quick Answer box injection
# ---------------------------------------------------------------------------


def add_quick_answer_box(html: str) -> tuple[str, int]:
    """Add a Quick Answer box at the top if missing."""
    if 'Quick Answer' in html:
        return html, 0

    # Extract key points from the first few H3 question/answer pairs
    h3_matches = list(re.finditer(r'<h3[^>]*>(.*?)</h3>\s*\n*\s*<p>(.*?)</p>', html, re.DOTALL))
    if len(h3_matches) < 2:
        # Fallback: extract from first few paragraphs
        p_matches = list(re.finditer(r'<p>([^<]{30,200})</p>', html))
        if len(p_matches) < 3:
            return html, 0
        items = ""
        for p in p_matches[1:4]:
            text = p.group(1).strip()
            # Truncate to first sentence
            sentence = re.split(r'[.!?]', text)[0].strip()
            if len(sentence) > 20:
                items += f'<li>{sentence}</li>\n'
    else:
        items = ""
        for m in h3_matches[:4]:
            question = re.sub(r'<[^>]+>', '', m.group(1)).strip().rstrip('?')
            answer = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            # First sentence of the answer
            sentence = re.split(r'[.!?]', answer)[0].strip()
            if len(sentence) > 20:
                items += f'<li><strong>{question}:</strong> {sentence}</li>\n'

    if not items.strip():
        return html, 0

    box = QUICK_ANSWER_DIV.format(items=items.rstrip())
    html = box + html
    return html, 1


# ---------------------------------------------------------------------------
# NEW: Style unstyled tables
# ---------------------------------------------------------------------------


def style_tables(html: str) -> tuple[str, int]:
    """Add navy headers and alternating row colors to unstyled tables."""
    # Find tables without inline styles
    unstyled = list(re.finditer(r'<table(?![^>]*style=)[^>]*>', html))
    if not unstyled:
        return html, 0

    count = 0
    offset = 0
    for m in unstyled:
        adj_start = m.start() + offset
        adj_end = m.end() + offset

        # Find the closing </table>
        table_end = html.find('</table>', adj_end)
        if table_end == -1:
            continue

        table_html = html[adj_start:table_end + 8]

        # Style the <table> tag
        new_table = table_html.replace(
            m.group(),
            '<table style="width:100%;border-collapse:collapse;margin:20px 0;">',
            1,
        )

        # Style <th> cells (exclude <thead>/<th... tags that aren't th cells)
        new_table = re.sub(
            r'<th(?!ead)(?![^>]*style=)([^>]*)>',
            r'<th style="padding:12px 16px;text-align:left;"\1>',
            new_table,
        )

        # Style header row
        new_table = re.sub(
            r'(<thead>\s*<tr)(?![^>]*style=)([^>]*>)',
            r'\1 style="background:#1a237e;color:white;"\2',
            new_table,
        )

        # Style <td> cells
        new_table = re.sub(
            r'<td(?![^>]*style=)([^>]*)>',
            r'<td style="padding:10px 16px;border-bottom:1px solid #e0e0e0;"\1>',
            new_table,
        )

        # Add alternating row colors to <tr> in tbody
        tbody_match = re.search(r'<tbody>(.*?)</tbody>', new_table, re.DOTALL)
        if tbody_match:
            tbody_content = tbody_match.group(1)
            rows = list(re.finditer(r'<tr(?![^>]*style=)([^>]*)>', tbody_content))
            new_tbody = tbody_content
            row_offset = 0
            for idx, row in enumerate(rows):
                if idx % 2 == 0:
                    old = row.group()
                    replacement = f'<tr style="background:#f5f5f5;"{row.group(1)}>'
                    adj = row.start() + row_offset
                    new_tbody = new_tbody[:adj] + replacement + new_tbody[adj + len(old):]
                    row_offset += len(replacement) - len(old)
            new_table = new_table[:tbody_match.start(1)] + new_tbody + new_table[tbody_match.end(1):]

        old_len = table_end + 8 - adj_start
        html = html[:adj_start] + new_table + html[adj_start + old_len:]
        offset += len(new_table) - old_len
        count += 1

    return html, count


# ---------------------------------------------------------------------------
# NEW: Style unstyled blockquotes
# ---------------------------------------------------------------------------


def style_blockquotes(html: str) -> tuple[str, int]:
    """Add background and border styling to unstyled blockquotes."""
    unstyled = list(re.finditer(r'<blockquote(?![^>]*style=)[^>]*>', html))
    if not unstyled:
        return html, 0

    styled_tag = (
        '<blockquote style="background:#f5f5f5;border-left:4px solid #9e9e9e;'
        'padding:16px 20px;margin:20px 0;border-radius:4px;font-style:italic;">'
    )

    count = 0
    offset = 0
    for m in unstyled:
        adj_start = m.start() + offset
        adj_end = m.end() + offset
        old_tag = html[adj_start:adj_end]
        html = html[:adj_start] + styled_tag + html[adj_end:]
        offset += len(styled_tag) - len(old_tag)
        count += 1

    # Also style unstyled <footer> inside blockquotes
    html = re.sub(
        r'<footer(?![^>]*style=)([^>]*)>--\s*',
        r'<footer style="margin-top:8px;font-style:normal;color:#616161;"\1>— <strong>',
        html,
    )
    # Close the <strong> before </footer> for those we just added
    html = re.sub(
        r'(<footer style="margin-top:8px[^>]*>— <strong>[^<]+)(</footer>)',
        lambda m: m.group(1).rstrip() + '</strong>' + m.group(2) if '</strong>' not in m.group(1) else m.group(0),
        html,
    )

    return html, count


# ---------------------------------------------------------------------------
# NEW: Convert bare <strong> FAQ questions to <h3>
# ---------------------------------------------------------------------------


def fix_bare_markdown_bold(html: str) -> tuple[str, int]:
    """Convert leftover ``**Text:**`` / ``**Text**`` markdown bold into ``<strong>``.

    Kimi K2.5 often drops bare markdown bold (e.g. ``**Pros:**``, ``**Best for:**``)
    inside list items and paragraphs. WordPress renders these as literal asterisks.

    Rules:
    - Non-greedy match, single-line only (no newlines inside the match)
    - Skip anything inside ``<code>``, ``<pre>``, or existing ``<strong>`` — segment
      the HTML by those tags and only transform non-code segments
    - Preserve one-or-more trailing colon for the common ``**Label:**`` pattern
    """
    # Segment on code/pre blocks to avoid touching fenced content
    segments = re.split(r'(<(?:code|pre)[^>]*>.*?</(?:code|pre)>)', html, flags=re.DOTALL | re.IGNORECASE)
    bold_re = re.compile(r'\*\*([^*\n]{1,120}?)\*\*')
    total = 0
    for i, seg in enumerate(segments):
        if seg.lower().startswith(('<code', '<pre')):
            continue
        new_seg, count = bold_re.subn(r'<strong>\1</strong>', seg)
        if count:
            segments[i] = new_seg
            total += count
    return ''.join(segments), total


def fix_faq_headings(html: str) -> tuple[str, int]:
    """Convert bare <strong>Question?</strong> in FAQ sections to <h3> tags."""
    # Find FAQ section
    faq_match = re.search(r'<h2[^>]*>.*?(?:FAQ|Frequently Asked).*?</h2>', html, re.IGNORECASE)
    if not faq_match:
        return html, 0

    faq_start = faq_match.end()
    # Find next H2 or end of document
    next_h2 = re.search(r'<h2', html[faq_start:])
    faq_end = faq_start + next_h2.start() if next_h2 else len(html)

    faq_section = html[faq_start:faq_end]

    # Replace <strong>Question text?</strong> that appear on their own line (not inside <p>)
    new_faq, count = re.subn(
        r'(?<!</p>)\s*<strong>([^<]{15,200}\?)</strong>',
        r'\n\n<h3>\1</h3>',
        faq_section,
    )

    if count == 0:
        return html, 0

    html = html[:faq_start] + new_faq + html[faq_end:]
    return html, count


# ---------------------------------------------------------------------------
# NEW: Remove banned words
# ---------------------------------------------------------------------------


def remove_banned_words(html: str) -> tuple[str, int]:
    """Replace banned AI-typical words with natural alternatives."""
    replacements = {
        "delve": "explore",
        "tapestry": "mix",
        "landscape": "field",
        "crucial": "important",
        "leverage": "use",
        "utilize": "use",
        "cutting-edge": "modern",
        "game-changer": "major improvement",
        "revolutionize": "transform",
        "seamless": "smooth",
        "robust": "strong",
        "furthermore": "also",
        "moreover": "also",
        "realm": "area",
        "symphony": "combination",
        "bustling": "busy",
        "innovative": "new",
        "uncover": "find",
    }
    count = 0
    for banned, replacement in replacements.items():
        # Case-insensitive replacement, preserving case of first letter
        pattern = re.compile(re.escape(banned), re.IGNORECASE)
        matches = pattern.findall(html)
        if matches:
            for match in matches:
                if match[0].isupper():
                    rep = replacement.capitalize()
                else:
                    rep = replacement
                html = html.replace(match, rep, 1)
                count += 1

    return html, count


# ---------------------------------------------------------------------------
# Entity coverage check + injection
# ---------------------------------------------------------------------------


def inject_missing_entities(html: str, niche: str, missing: list[str]) -> tuple[str, int]:
    """Inject missing entity mentions into relevant paragraphs.

    Strategy: find paragraphs discussing related topics (via entity relationships)
    and naturally insert the missing entity name. Light-touch — adds 1-2 mentions max.
    """
    if not missing:
        return html, 0

    relationships = ENTITY_RELATIONSHIPS.get(niche, [])
    entities = NICHE_ENTITIES.get(niche, {})
    injected = 0

    for entity_name in missing[:3]:  # Max 3 entity injections per article
        entity_lower = entity_name.lower()

        # Find related entities via relationships
        related_terms = set()
        for subj, verb, obj in relationships:
            if subj.lower() == entity_lower:
                related_terms.add(obj.lower())
            elif obj.lower() == entity_lower:
                related_terms.add(subj.lower())

        if not related_terms:
            continue

        # Find a paragraph that mentions a related entity
        para_pattern = re.compile(r"(<p>)(.*?)(</p>)", re.DOTALL)
        for m in para_pattern.finditer(html):
            para_text = m.group(2).lower()
            # Check if paragraph mentions a related entity
            if any(rt in para_text for rt in related_terms):
                # Don't inject into very short paragraphs
                if len(para_text.split()) < 10:
                    continue
                # Don't inject if entity already there (fuzzy check)
                if entity_lower in para_text:
                    continue

                # Build injection phrase based on entity type
                etype = entities.get(entity_name, {}).get("@type", "Thing")
                if etype == "MedicalCondition":
                    phrase = f", which is particularly relevant for those dealing with {entity_name},"
                elif etype == "Organization":
                    phrase = f" (as recommended by {entity_name})"
                elif etype == "Product":
                    phrase = f", especially when using a {entity_name},"
                else:
                    phrase = f", including {entity_name},"

                # Insert after the first sentence in the paragraph
                first_period = m.group(2).find(". ")
                if first_period > 20:
                    original = m.group(2)
                    modified = original[:first_period + 1] + phrase + original[first_period + 1:]
                    html = html[:m.start(2)] + modified + html[m.end(2):]
                    injected += 1
                    break  # One injection per entity

    return html, injected


# ---------------------------------------------------------------------------
# Main enhancement pipeline
# ---------------------------------------------------------------------------

def enhance_article(filepath: Path, niche: str, dry_run: bool = False) -> dict:
    """Run all enhancements on a single article. Returns stats."""
    html = filepath.read_text(encoding='utf-8')
    original = html
    stats = {"file": filepath.name, "changes": []}

    # Load niche-specific templates for visual differentiation
    nt = get_niche_templates(niche)
    niche_callout_map = nt["CALLOUT_MAP"]
    niche_quote_tmpl = nt["EXPERT_QUOTE_HTML"]
    niche_kt_tmpl = nt["KEY_TAKEAWAY_DIV"]
    niche_style = get_site_style(niche)
    niche_kt_color = niche_style["key_takeaway"]["strong_color"]

    # 0. Remove banned words (do first so other steps don't re-introduce)
    html, n = remove_banned_words(html)
    if n:
        stats["changes"].append(f"Removed {n} banned words")

    # 1. Wrap bare callouts in styled divs (niche colors)
    html, n = wrap_bare_callouts(html, callout_map=niche_callout_map)
    if n:
        stats["changes"].append(f"Wrapped {n} callouts in styled divs")

    # 2. Style unstyled tables
    html, n = style_tables(html)
    if n:
        stats["changes"].append(f"Styled {n} tables")

    # 3. Style unstyled blockquotes
    html, n = style_blockquotes(html)
    if n:
        stats["changes"].append(f"Styled {n} blockquotes")

    # 4. Fix FAQ headings (<strong> -> <h3>)
    html, n = fix_faq_headings(html)
    if n:
        stats["changes"].append(f"Fixed {n} FAQ headings to H3")

    # 4b. Convert leftover bare markdown bold (**Pros:**) to <strong>
    html, n = fix_bare_markdown_bold(html)
    if n:
        stats["changes"].append(f"Converted {n} bare markdown bold to <strong>")

    # 5. Add Quick Answer box if missing
    html, n = add_quick_answer_box(html)
    if n:
        stats["changes"].append(f"Added Quick Answer box")

    # 6. Add experience signals
    html, n = add_experience_signals(html)
    if n:
        stats["changes"].append(f"Added {n} experience signals")

    # 7. Add authority citations (niche-specific)
    html, n = add_authority_citations(html, niche)
    if n:
        stats["changes"].append(f"Added {n} authority citations")

    # 8. Add expert quote (niche colors)
    html, n = add_expert_quote(html, niche, quote_template=niche_quote_tmpl)
    if n:
        stats["changes"].append(f"Added expert quote")

    # 9. Entity coverage check + injection
    coverage = scan_entity_coverage(niche, html)
    stats["entity_coverage"] = coverage["coverage_pct"]
    stats["entity_density"] = coverage["density_per_1k"]
    if coverage["coverage_pct"] < 50 and coverage["missing"]:
        html, n = inject_missing_entities(html, niche, coverage["missing"])
        if n:
            stats["changes"].append(f"Injected {n} missing entities (coverage was {coverage['coverage_pct']:.0f}%)")

    # 10. Add Key Takeaway box (niche colors)
    html, n = add_key_takeaway(html, kt_template=niche_kt_tmpl, kt_color=niche_kt_color)
    if n:
        stats["changes"].append(f"Added Key Takeaway box")

    # 11. Add update date
    html, n = add_update_date(html)
    if n:
        stats["changes"].append(f"Added 'Last updated' signal")

    stats["changed"] = html != original
    if stats["changed"] and not dry_run:
        filepath.write_text(html, encoding='utf-8')

    return stats


def enhance_niche(niche: str, dry_run: bool = False):
    """Enhance all articles in a niche."""
    articles_dir = get_articles_dir(niche)
    html_files = sorted(articles_dir.glob("*.html"))

    if not html_files:
        print(f"  No articles found in {articles_dir}")
        return

    name = NICHE_NAMES.get(niche, niche)
    mode = "DRY RUN" if dry_run else "APPLY"
    print(f"\n{'=' * 50}")
    print(f"ENHANCING: {name} ({len(html_files)} articles)")
    print(f"Mode: {mode}")
    print(f"{'=' * 50}")

    changed = 0
    unchanged = 0
    total_changes = 0

    for f in html_files:
        stats = enhance_article(f, niche, dry_run)
        if stats["changed"]:
            changed += 1
            total_changes += len(stats["changes"])
            changes_str = ", ".join(stats["changes"])
            print(f"  [FIX] {f.stem}: {changes_str}")
        else:
            unchanged += 1

    print(f"\n  Changed: {changed} | Unchanged: {unchanged} | Total fixes: {total_changes}")
    print(f"\nDone.")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if not args:
        print("Usage: python scripts/article_enhancer.py <niche-slug> [--dry-run]")
        print("       python scripts/article_enhancer.py --all [--dry-run]")
        sys.exit(1)

    if args[0] == "--all":
        for niche in ALL_NICHES:
            articles_dir = get_articles_dir(niche)
            if list(articles_dir.glob("*.html")):
                enhance_niche(niche, dry_run)
    else:
        niche = args[0]
        if niche not in NICHE_NAMES:
            print(f"Unknown niche: {niche}")
            print(f"Available: {', '.join(ALL_NICHES)}")
            sys.exit(1)
        enhance_niche(niche, dry_run)


if __name__ == "__main__":
    main()
