"""
config.py — Shared configuration for the article generation pipeline.

Model routing: Kimi K2.5 via OpenRouter (primary), Sonnet fallback.
"""

import os
from pathlib import Path

# -- Load .env.cowork for API keys ----------------------------------------
# Check: VPS path → project root → legacy _global path
_vps_env = Path("/opt/bulk-affiliate/.env.cowork")
_project_root_env = Path(__file__).parent.parent / ".env.cowork"
_global_env = Path(__file__).parent.parent.parent.parent / "_global" / ".env.cowork"
ENV_FILE = _vps_env if _vps_env.exists() else (_project_root_env if _project_root_env.exists() else _global_env)
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            k, v = key.strip(), value.strip()
            if v and not os.environ.get(k):
                os.environ[k] = v

# -- Paths ----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# -- Model Routing --------------------------------------------------------
# Primary: Kimi K2.5 via OpenRouter ($0.45/$2.20 per 1M tokens)
# Fallback: Claude Sonnet via Anthropic ($3/$15 per 1M tokens)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

PRIMARY_MODEL = "moonshotai/kimi-k2.5"       # All niches
FALLBACK_MODEL = "claude-sonnet-4-6"          # Only if Kimi fails
PRIMARY_MAX_TOKENS = 8192                     # Long-form with visuals (Kimi supports 128K)
FALLBACK_MAX_TOKENS = 4096

# -- Article Generation ---------------------------------------------------
MAX_CONCURRENT = 5          # Parallel API calls
RETRY_ATTEMPTS = 3          # Retries on primary before fallback
RETRY_DELAY = 5             # Seconds between retries

# Word count targets (upgraded for visual-rich content)
HOWTO_MIN_WORDS = 1500
HOWTO_MAX_WORDS = 2500
TIPS_MIN_WORDS = 1200
TIPS_MAX_WORDS = 2000

# -- Quality Thresholds ---------------------------------------------------
EEAT_MIN_SCORE = 7.0        # E-E-A-T minimum (0-10 scale)
GEO_MIN_SCORE = 12          # GEO minimum (0-20 scale)
MIN_VISUAL_ELEMENTS = 3     # Tables + callouts + quotes
MIN_STATS_PER_ARTICLE = 4   # Statistics with sources
STATS_DENSITY_TARGET = 175  # Words per statistic (optimal: 150-250)

# -- Categories -----------------------------------------------------------
INFO_CATEGORIES = {"How-To Guides", "Tips & Care"}
ROUNDUP_CATEGORIES = {"Best Products", "Reviews", "Buying Guides", "Comparisons"}

CATEGORY_SLUGS = {
    "How-To Guides": "how-to-guides",
    "Tips & Care": "tips-care",
    "Best Products": "best-products",
    "Reviews": "reviews",
    "Buying Guides": "buying-guides",
    "Comparisons": "comparisons",
}

# -- Brand Voice ----------------------------------------------------------
BANNED_WORDS = [
    "delve", "tapestry", "landscape", "crucial", "leverage", "utilize",
    "cutting-edge", "game-changer", "revolutionize", "seamless", "robust",
    "in today's world", "it's important to note", "needless to say",
    "at the end of the day", "in today's digital age", "uncover",
    "realm", "symphony", "bustling", "innovative", "furthermore", "moreover",
]

FLUFF_INTROS = [
    "in today's",
    "when it comes to",
    "if you're looking for",
    "are you tired of",
    "have you ever wondered",
    "in the world of",
    "whether you're a",
    "in this article",
    "in today's fast-paced",
]

# -- Niche Display Names --------------------------------------------------
NICHE_NAMES = {
    "dog-comfort": "Dog Comfort",
    "camping-gear": "Camping Gear",
    "cat-care": "Cat Care",
    "home-coffee": "Home Coffee",
    "mens-grooming": "Men's Grooming",
    "oral-care": "Oral Care",
    "home-cleaning": "Home Cleaning",
    "healthy-cooking": "Healthy Cooking",
    "home-office": "Home Office",
    "water-air-quality": "Water & Air Quality",
    "korean-skincare": "Korean Skincare",
    "makeup-beauty": "Makeup & Beauty",
    "korean-medical-tourism": "Korean Medical Tourism",
    "korean-used-cars": "Korean Used Cars & Parts",
}

ALL_NICHES = list(NICHE_NAMES.keys())

# -- Site Style Groups (Anti-Network Detection) ----------------------------
# Each group has distinct visual identity to avoid template fingerprinting.
# 6 groups × 2-3 sites each. K-Beauty excluded (separate site).
SITE_STYLES = {
    # Group A: Pet Care — warm, earthy, approachable
    "dog-comfort": {
        "group": "A",
        "pro_tip":      {"bg": "#e8f5e9", "border": "#4caf50", "strong_color": "#2e7d32"},
        "warning":       {"bg": "#fff3e0", "border": "#ff9800", "strong_color": "#e65100"},
        "key_takeaway":  {"bg": "#e3f2fd", "border": "#2196f3", "strong_color": "#1565c0"},
        "table_header":  {"bg": "#1b3a5c", "color": "#ffffff"},
        "table_alt_row": "#f0f4f8",
        "quote":         {"bg": "#f5f5f5", "border": "#9e9e9e", "footer_color": "#616161"},
        "quick_answer":  {"bg": "#f3e5f5", "border": "#9c27b0"},
        "section_order": ["quick_answer", "intro", "toc", "content", "expert_quote", "faq", "key_takeaway"],
        "has_toc": True,
        "quick_answer_position": "top",
        "author": {"name": "Dr. Sarah Mitchell", "bio": "Veterinary wellness researcher with 12 years in companion animal care. AVMA member."},
        "css_vars": {
            "--aff-primary": "#2d6a4f",
            "--aff-primary-lt": "#52b788",
            "--aff-cta": "#e76f51",
            "--aff-cta-hover": "#c9563a",
            "--aff-dark": "#1b4332",
            "--font-heading": "'Merriweather', Georgia, serif",
        },
    },
    "cat-care": {
        "group": "A",
        "pro_tip":      {"bg": "#e8f5e9", "border": "#4caf50", "strong_color": "#2e7d32"},
        "warning":       {"bg": "#fff3e0", "border": "#ff9800", "strong_color": "#e65100"},
        "key_takeaway":  {"bg": "#e3f2fd", "border": "#2196f3", "strong_color": "#1565c0"},
        "table_header":  {"bg": "#1b3a5c", "color": "#ffffff"},
        "table_alt_row": "#f0f4f8",
        "quote":         {"bg": "#f5f5f5", "border": "#9e9e9e", "footer_color": "#616161"},
        "quick_answer":  {"bg": "#f3e5f5", "border": "#9c27b0"},
        "section_order": ["quick_answer", "intro", "toc", "content", "expert_quote", "faq", "key_takeaway"],
        "has_toc": True,
        "quick_answer_position": "top",
        "author": {"name": "Dr. Karen Wells", "bio": "Feline behavior specialist and AAFP member. 15 years in cat-only veterinary practice."},
        "css_vars": {
            "--aff-primary": "#2d6a4f",
            "--aff-primary-lt": "#52b788",
            "--aff-cta": "#e76f51",
            "--aff-cta-hover": "#c9563a",
            "--aff-dark": "#1b4332",
            "--font-heading": "'Merriweather', Georgia, serif",
        },
    },

    # Group B: Outdoor & Workspace — bold, utilitarian, high-contrast
    "camping-gear": {
        "group": "B",
        "pro_tip":      {"bg": "#e0f2f1", "border": "#009688", "strong_color": "#00695c"},
        "warning":       {"bg": "#fbe9e7", "border": "#e53935", "strong_color": "#b71c1c"},
        "key_takeaway":  {"bg": "#fff8e1", "border": "#ffc107", "strong_color": "#f57f17"},
        "table_header":  {"bg": "#1b5e20", "color": "#ffffff"},
        "table_alt_row": "#e8f5e9",
        "quote":         {"bg": "#eceff1", "border": "#607d8b", "footer_color": "#455a64"},
        "quick_answer":  {"bg": "#e8eaf6", "border": "#3f51b5"},
        "section_order": ["intro", "quick_answer", "content", "faq", "expert_quote", "key_takeaway"],
        "has_toc": False,
        "quick_answer_position": "after_intro",
        "author": {"name": "Jake Thornton", "bio": "Backcountry guide and gear tester. AT and PCT thru-hiker. Tests 200+ products yearly."},
        "css_vars": {
            "--aff-primary": "#37474f",
            "--aff-primary-lt": "#546e7a",
            "--aff-cta": "#ff6f00",
            "--aff-cta-hover": "#e65100",
            "--aff-dark": "#263238",
            "--font-heading": "'Inter', -apple-system, sans-serif",
        },
    },
    "home-office": {
        "group": "B",
        "pro_tip":      {"bg": "#e0f2f1", "border": "#009688", "strong_color": "#00695c"},
        "warning":       {"bg": "#fbe9e7", "border": "#e53935", "strong_color": "#b71c1c"},
        "key_takeaway":  {"bg": "#fff8e1", "border": "#ffc107", "strong_color": "#f57f17"},
        "table_header":  {"bg": "#1b5e20", "color": "#ffffff"},
        "table_alt_row": "#e8f5e9",
        "quote":         {"bg": "#eceff1", "border": "#607d8b", "footer_color": "#455a64"},
        "quick_answer":  {"bg": "#e8eaf6", "border": "#3f51b5"},
        "section_order": ["intro", "quick_answer", "content", "faq", "expert_quote", "key_takeaway"],
        "has_toc": False,
        "quick_answer_position": "after_intro",
        "author": {"name": "Chris Rivera", "bio": "Remote work consultant and ergonomics specialist. Reviewed 300+ WFH setups."},
        "css_vars": {
            "--aff-primary": "#37474f",
            "--aff-primary-lt": "#546e7a",
            "--aff-cta": "#ff6f00",
            "--aff-cta-hover": "#e65100",
            "--aff-dark": "#263238",
            "--font-heading": "'Inter', -apple-system, sans-serif",
        },
    },

    # Group C: Kitchen & Food — warm browns, earthy, inviting
    "home-coffee": {
        "group": "C",
        "pro_tip":      {"bg": "#efebe9", "border": "#795548", "strong_color": "#4e342e"},
        "warning":       {"bg": "#fff3e0", "border": "#ff9800", "strong_color": "#e65100"},
        "key_takeaway":  {"bg": "#f1f8e9", "border": "#8bc34a", "strong_color": "#558b2f"},
        "table_header":  {"bg": "#3e2723", "color": "#ffffff"},
        "table_alt_row": "#efebe9",
        "quote":         {"bg": "#fafafa", "border": "#a1887f", "footer_color": "#6d4c41"},
        "quick_answer":  {"bg": "#fce4ec", "border": "#e91e63"},
        "section_order": ["quick_answer", "intro", "content", "key_takeaway", "expert_quote", "faq"],
        "has_toc": True,
        "quick_answer_position": "top",
        "author": {"name": "Marco DeLuca", "bio": "Home barista and SCA-certified coffee professional. Tests brewing equipment daily."},
        "css_vars": {
            "--aff-primary": "#5d4037",
            "--aff-primary-lt": "#8d6e63",
            "--aff-cta": "#ef6c00",
            "--aff-cta-hover": "#d84315",
            "--aff-dark": "#3e2723",
            "--font-heading": "'Libre Baskerville', Georgia, serif",
        },
    },
    "healthy-cooking": {
        "group": "C",
        "pro_tip":      {"bg": "#efebe9", "border": "#795548", "strong_color": "#4e342e"},
        "warning":       {"bg": "#fff3e0", "border": "#ff9800", "strong_color": "#e65100"},
        "key_takeaway":  {"bg": "#f1f8e9", "border": "#8bc34a", "strong_color": "#558b2f"},
        "table_header":  {"bg": "#3e2723", "color": "#ffffff"},
        "table_alt_row": "#efebe9",
        "quote":         {"bg": "#fafafa", "border": "#a1887f", "footer_color": "#6d4c41"},
        "quick_answer":  {"bg": "#fce4ec", "border": "#e91e63"},
        "section_order": ["quick_answer", "intro", "content", "key_takeaway", "expert_quote", "faq"],
        "has_toc": True,
        "quick_answer_position": "top",
        "author": {"name": "Chef Lena Park", "bio": "Nutritionist and culinary researcher. ACF-certified. Tests kitchen equipment for home cooks."},
        "css_vars": {
            "--aff-primary": "#5d4037",
            "--aff-primary-lt": "#8d6e63",
            "--aff-cta": "#ef6c00",
            "--aff-cta-hover": "#d84315",
            "--aff-dark": "#3e2723",
            "--font-heading": "'Libre Baskerville', Georgia, serif",
        },
    },

    # Group D: Personal Care — cool, clinical, professional
    "mens-grooming": {
        "group": "D",
        "pro_tip":      {"bg": "#eceff1", "border": "#607d8b", "strong_color": "#37474f"},
        "warning":       {"bg": "#fce4ec", "border": "#e91e63", "strong_color": "#ad1457"},
        "key_takeaway":  {"bg": "#e8eaf6", "border": "#5c6bc0", "strong_color": "#283593"},
        "table_header":  {"bg": "#37474f", "color": "#ffffff"},
        "table_alt_row": "#eceff1",
        "quote":         {"bg": "#e3f2fd", "border": "#42a5f5", "footer_color": "#1565c0"},
        "quick_answer":  {"bg": "#f3e5f5", "border": "#ab47bc"},
        "section_order": ["intro", "content", "quick_answer", "expert_quote", "faq", "key_takeaway"],
        "has_toc": True,
        "quick_answer_position": "mid_content",
        "author": {"name": "Dr. Corey Hartman", "bio": "Board-certified dermatologist and men's skincare researcher. AAD fellow."},
        "css_vars": {
            "--aff-primary": "#455a64",
            "--aff-primary-lt": "#78909c",
            "--aff-cta": "#ef5350",
            "--aff-cta-hover": "#d32f2f",
            "--aff-dark": "#263238",
            "--font-heading": "'Roboto Slab', 'Segoe UI', sans-serif",
        },
    },
    "oral-care": {
        "group": "D",
        "pro_tip":      {"bg": "#eceff1", "border": "#607d8b", "strong_color": "#37474f"},
        "warning":       {"bg": "#fce4ec", "border": "#e91e63", "strong_color": "#ad1457"},
        "key_takeaway":  {"bg": "#e8eaf6", "border": "#5c6bc0", "strong_color": "#283593"},
        "table_header":  {"bg": "#37474f", "color": "#ffffff"},
        "table_alt_row": "#eceff1",
        "quote":         {"bg": "#e3f2fd", "border": "#42a5f5", "footer_color": "#1565c0"},
        "quick_answer":  {"bg": "#f3e5f5", "border": "#ab47bc"},
        "section_order": ["intro", "content", "quick_answer", "expert_quote", "faq", "key_takeaway"],
        "has_toc": True,
        "quick_answer_position": "mid_content",
        "author": {"name": "Dr. Ada Cooper", "bio": "DDS, ADA consumer advisor. 20 years in preventive dentistry and oral health education."},
        "css_vars": {
            "--aff-primary": "#455a64",
            "--aff-primary-lt": "#78909c",
            "--aff-cta": "#ef5350",
            "--aff-cta-hover": "#d32f2f",
            "--aff-dark": "#263238",
            "--font-heading": "'Roboto Slab', 'Segoe UI', sans-serif",
        },
    },

    # Group E: Home & Environment — fresh, clean, bright
    "home-cleaning": {
        "group": "E",
        "pro_tip":      {"bg": "#e0f7fa", "border": "#00bcd4", "strong_color": "#006064"},
        "warning":       {"bg": "#fff8e1", "border": "#ffd54f", "strong_color": "#f9a825"},
        "key_takeaway":  {"bg": "#e8f5e9", "border": "#66bb6a", "strong_color": "#2e7d32"},
        "table_header":  {"bg": "#2e7d32", "color": "#ffffff"},
        "table_alt_row": "#e8f5e9",
        "quote":         {"bg": "#f1f8e9", "border": "#aed581", "footer_color": "#558b2f"},
        "quick_answer":  {"bg": "#ede7f6", "border": "#7e57c2"},
        "section_order": ["quick_answer", "content", "intro", "faq", "key_takeaway", "expert_quote"],
        "has_toc": False,
        "quick_answer_position": "top",
        "author": {"name": "Lisa Chen", "bio": "Home science researcher and cleaning product tester. Chemistry background, EPA-certified."},
        "css_vars": {
            "--aff-primary": "#00796b",
            "--aff-primary-lt": "#26a69a",
            "--aff-cta": "#ff7043",
            "--aff-cta-hover": "#e64a19",
            "--aff-dark": "#004d40",
            "--font-heading": "'Source Sans 3', 'Segoe UI', sans-serif",
        },
    },
    "water-air-quality": {
        "group": "E",
        "pro_tip":      {"bg": "#e0f7fa", "border": "#00bcd4", "strong_color": "#006064"},
        "warning":       {"bg": "#fff8e1", "border": "#ffd54f", "strong_color": "#f9a825"},
        "key_takeaway":  {"bg": "#e8f5e9", "border": "#66bb6a", "strong_color": "#2e7d32"},
        "table_header":  {"bg": "#2e7d32", "color": "#ffffff"},
        "table_alt_row": "#e8f5e9",
        "quote":         {"bg": "#f1f8e9", "border": "#aed581", "footer_color": "#558b2f"},
        "quick_answer":  {"bg": "#ede7f6", "border": "#7e57c2"},
        "section_order": ["quick_answer", "content", "intro", "faq", "key_takeaway", "expert_quote"],
        "has_toc": False,
        "quick_answer_position": "top",
        "author": {"name": "Tom Bradley", "bio": "Environmental health analyst and water quality tester. WQA-certified, 10+ years in filtration systems."},
        "css_vars": {
            "--aff-primary": "#00796b",
            "--aff-primary-lt": "#26a69a",
            "--aff-cta": "#ff7043",
            "--aff-cta-hover": "#e64a19",
            "--aff-dark": "#004d40",
            "--font-heading": "'Source Sans 3', 'Segoe UI', sans-serif",
        },
    },

    # Group F: Korean Business — elegant, premium, purple/indigo
    "korean-skincare": {
        "group": "F",
        "pro_tip":      {"bg": "#f3e5f5", "border": "#ab47bc", "strong_color": "#6a1b9a"},
        "warning":       {"bg": "#fce4ec", "border": "#ec407a", "strong_color": "#c2185b"},
        "key_takeaway":  {"bg": "#ede7f6", "border": "#7e57c2", "strong_color": "#4527a0"},
        "table_header":  {"bg": "#4a148c", "color": "#ffffff"},
        "table_alt_row": "#f3e5f5",
        "quote":         {"bg": "#f5f0ff", "border": "#b39ddb", "footer_color": "#5e35b1"},
        "quick_answer":  {"bg": "#e8eaf6", "border": "#5c6bc0"},
        "section_order": ["intro", "quick_answer", "toc", "content", "faq", "expert_quote", "key_takeaway"],
        "has_toc": True,
        "quick_answer_position": "after_intro",
        "author": {"name": "Ji-Yeon Cho", "bio": "Korean beauty editor and skincare formulation researcher based in Seoul. 8 years covering K-beauty trends."},
        "css_vars": {
            "--aff-primary": "#6a1b9a",
            "--aff-primary-lt": "#9c27b0",
            "--aff-cta": "#e91e63",
            "--aff-cta-hover": "#c2185b",
            "--aff-dark": "#311b92",
            "--font-heading": "'Playfair Display', Georgia, serif",
        },
    },
    "makeup-beauty": {
        "group": "F",
        "pro_tip":      {"bg": "#fce4ec", "border": "#ec407a", "strong_color": "#c2185b"},
        "warning":       {"bg": "#fff3e0", "border": "#ff9800", "strong_color": "#e65100"},
        "key_takeaway":  {"bg": "#f3e5f5", "border": "#ab47bc", "strong_color": "#6a1b9a"},
        "table_header":  {"bg": "#4a148c", "color": "#ffffff"},
        "table_alt_row": "#fce4ec",
        "quote":         {"bg": "#f5f0ff", "border": "#b39ddb", "footer_color": "#5e35b1"},
        "quick_answer":  {"bg": "#e8eaf6", "border": "#5c6bc0"},
        "section_order": ["intro", "quick_answer", "toc", "content", "faq", "expert_quote", "key_takeaway"],
        "has_toc": True,
        "quick_answer_position": "after_intro",
        "author": {"name": "Mina Park", "bio": "Professional makeup artist and beauty reviewer. K-beauty specialist, featured in Allure and Cosmopolitan."},
        "css_vars": {
            "--aff-primary": "#880e4f",
            "--aff-primary-lt": "#c2185b",
            "--aff-cta": "#e91e63",
            "--aff-cta-hover": "#ad1457",
            "--aff-dark": "#311b92",
            "--font-heading": "'Playfair Display', Georgia, serif",
        },
    },
    "korean-medical-tourism": {
        "group": "F",
        "pro_tip":      {"bg": "#ede7f6", "border": "#7e57c2", "strong_color": "#4527a0"},
        "warning":       {"bg": "#fbe9e7", "border": "#e53935", "strong_color": "#b71c1c"},
        "key_takeaway":  {"bg": "#e8eaf6", "border": "#5c6bc0", "strong_color": "#283593"},
        "table_header":  {"bg": "#1a237e", "color": "#ffffff"},
        "table_alt_row": "#e8eaf6",
        "quote":         {"bg": "#f5f0ff", "border": "#b39ddb", "footer_color": "#5e35b1"},
        "quick_answer":  {"bg": "#fce4ec", "border": "#ec407a"},
        "section_order": ["intro", "quick_answer", "content", "expert_quote", "key_takeaway", "faq"],
        "has_toc": True,
        "quick_answer_position": "after_intro",
        "author": {"name": "Dr. Hyun-Soo Kim", "bio": "Medical tourism consultant and healthcare researcher. 10 years advising international patients in Seoul."},
        "css_vars": {
            "--aff-primary": "#283593",
            "--aff-primary-lt": "#3f51b5",
            "--aff-cta": "#7c4dff",
            "--aff-cta-hover": "#651fff",
            "--aff-dark": "#1a237e",
            "--font-heading": "'Playfair Display', Georgia, serif",
        },
    },
    "korean-used-cars": {
        "group": "F",
        "pro_tip":      {"bg": "#e8eaf6", "border": "#5c6bc0", "strong_color": "#283593"},
        "warning":       {"bg": "#fff3e0", "border": "#ff9800", "strong_color": "#e65100"},
        "key_takeaway":  {"bg": "#ede7f6", "border": "#7e57c2", "strong_color": "#4527a0"},
        "table_header":  {"bg": "#1a237e", "color": "#ffffff"},
        "table_alt_row": "#e8eaf6",
        "quote":         {"bg": "#eceff1", "border": "#78909c", "footer_color": "#455a64"},
        "quick_answer":  {"bg": "#f3e5f5", "border": "#ab47bc"},
        "section_order": ["quick_answer", "intro", "content", "faq", "key_takeaway", "expert_quote"],
        "has_toc": False,
        "quick_answer_position": "top",
        "author": {"name": "David Chung", "bio": "Korean automotive export specialist and used car inspector. 15 years in cross-border vehicle trade."},
        "css_vars": {
            "--aff-primary": "#283593",
            "--aff-primary-lt": "#3f51b5",
            "--aff-cta": "#ff6f00",
            "--aff-cta-hover": "#e65100",
            "--aff-dark": "#1a237e",
            "--font-heading": "'Inter', -apple-system, sans-serif",
        },
    },
}

# Convenience: get style for a niche, fallback to dog-comfort defaults
def get_site_style(niche_slug: str) -> dict:
    return SITE_STYLES.get(niche_slug, SITE_STYLES["dog-comfort"])


def get_niche_dir(niche_slug: str) -> Path:
    return OUTPUTS_DIR / niche_slug


def get_articles_dir(niche_slug: str) -> Path:
    d = get_niche_dir(niche_slug) / "articles"
    d.mkdir(parents=True, exist_ok=True)
    return d
