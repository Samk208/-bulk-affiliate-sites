"""Three-layer voice mode determination for article enhancement.

Layer order (last applied wins):
  1. niche default (voice.md.first_person)
  2. post-type override (medical/safety always third_only)
  3. title heuristic (female-coded keywords force third_only)
  4. explicit article-level voice_mode_override (beats all three)

This logic prevents the enhancer from injecting first-person operator
voice into articles where it would sound implausible (e.g., a male
operator writing about applying mascara), while preserving authentic
operator voice where it's a strength.
"""

from __future__ import annotations


VALID_MODES = {"allowed", "third_only", "mixed"}


# Post types that always force third_only regardless of niche default
MEDICAL_POST_TYPES = {
    "safety-guide",
    "clinical-explainer",
    "side-effects",
    "diagnosis",
    "treatment-guide",
    "medical-explainer",
    "ingredient-safety",
}


# Title keyword triggers that force third_only
THIRD_PERSON_TITLE_TRIGGERS = (
    # Audience-coded
    "for women", "for woman",
    "menopause", "pregnancy", "pregnant",
    "menstrual", "period", "period pain",
    "estrogen", "hormone replacement", "hormone therapy",
    # Medical/clinical
    "surgery", "surgical",
    "medical", "clinical", "diagnosis", "treatment",
    "side effect", "side-effect",
    "dermatologist", "dermatology",
    # Female-coded products
    "mascara", "lipstick", "lip stick", "concealer",
    "blush", "foundation", "eye shadow", "eyeshadow",
    "eyeliner", "primer", "highlighter", "bronzer",
    "anti-aging", "anti aging", "antiaging",
    "wrinkle", "fine lines",
)


def determine_voice_mode(article_meta: dict, niche_voice: dict, post_type: str) -> str:
    """Return one of: 'allowed', 'third_only', 'mixed'.

    Args:
        article_meta: dict with at least 'title'. May include 'voice_mode_override'.
        niche_voice: parsed voice.md frontmatter dict.
        post_type: detected post type (how-to, buying-guide, safety-guide, etc.)
    """
    # 1. Niche default
    mode = niche_voice.get("first_person", "allowed")
    if mode not in VALID_MODES:
        mode = "allowed"

    # 2. Post-type override
    if post_type in MEDICAL_POST_TYPES:
        mode = "third_only"

    # 3. Title heuristic
    title_lower = (article_meta.get("title") or "").lower()
    if any(t in title_lower for t in THIRD_PERSON_TITLE_TRIGGERS):
        mode = "third_only"

    # 4. Explicit override wins
    override = article_meta.get("voice_mode_override")
    if override in VALID_MODES:
        mode = override

    return mode
