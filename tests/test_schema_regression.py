"""Regression tests for article_template.build_schema().

NOTE: These are regression tests (not TDD) — they pin down fixes shipped
on 2026-04-17 for HANDOVER-2026-04-15 bugs #2 and #5. They pass on first
run; their value is preventing future regressions, not proving the fixes.

Fixes covered:
- Bug #2: mainEntityOfPage must be a WebPage object with article URL, not a
  niche-entity type (MedicalCondition/Product/Thing)
- Bug #5: @type must appear early in the schema dict (after @context) for
  readability — cosmetic but prevents confusion when inspecting JSON
"""
from article_template import build_schema


def _minimal_html() -> str:
    """Minimum HTML fixture — two H2s so entity extraction has something to chew on."""
    return (
        "<h2>Memory Foam Density</h2><p>Arthritis relief.</p>"
        "<h2>FAQ</h2><h3>Is it safe?</h3><p>Yes, veterinarian-approved.</p>"
    )


def _schema(html: str = None, **overrides) -> dict:
    """Call build_schema with sensible defaults; unwrap list-of-schemas to first."""
    defaults = dict(
        title="Best Dog Bed for Arthritis",
        slug="best-dog-bed-for-arthritis",
        category="Reviews",
        description="Orthopedic beds for senior dogs with joint issues.",
        html_content=html or _minimal_html(),
        niche_name="Dog Comfort",
        niche_slug="dog-comfort",
    )
    defaults.update(overrides)
    result = build_schema(**defaults)
    return result[0] if isinstance(result, list) else result


# --- Bug #2: mainEntityOfPage ---

def test_mainEntityOfPage_is_WebPage_type():
    """Article schema must declare the page itself as a WebPage, not the subject entity."""
    schema = _schema()
    meop = schema["mainEntityOfPage"]
    assert meop["@type"] == "WebPage", (
        f"Expected WebPage, got {meop['@type']} — Schema.org says mainEntityOfPage is the "
        f"page that hosts the article, not the article's subject"
    )


def test_mainEntityOfPage_id_contains_slug_when_no_site_url():
    """Without site_url the @id is a relative path — must include the article slug."""
    schema = _schema(slug="my-test-slug")
    assert "/my-test-slug/" in schema["mainEntityOfPage"]["@id"]


def test_mainEntityOfPage_id_is_absolute_when_site_url_provided():
    """Passing site_url produces an absolute @id (domain + slug)."""
    schema = _schema(slug="foo", site_url="https://dogcomfort.example.com")
    assert schema["mainEntityOfPage"]["@id"] == "https://dogcomfort.example.com/foo/"


def test_mainEntityOfPage_never_uses_niche_entity_type():
    """Regression: previously set to MedicalCondition/Product/Thing (wrong).

    These types belong in `about[0]`, which already works correctly — verify
    the primary entity still lives there.
    """
    schema = _schema()
    assert schema["mainEntityOfPage"]["@type"] == "WebPage"
    # And the subject entity is in `about[]`, not promoted to mainEntityOfPage
    assert "about" in schema
    assert len(schema["about"]) > 0, "dog-comfort niche should yield at least one `about` entity"


# --- Bug #5: @type ordering ---

def test_at_type_appears_early_in_schema():
    """@type should come right after @context — was buried at the bottom via .update()."""
    keys = list(_schema().keys())
    assert keys[0] == "@context"
    assert keys[1] == "@type", f"Expected @type as second key, got order: {keys[:5]}"


def test_at_type_is_Article_for_non_howto():
    """Reviews/Tips/Buying Guides all emit @type: Article."""
    for category in ("Reviews", "Tips & Care", "Buying Guides", "Comparisons"):
        schema = _schema(category=category)
        assert schema["@type"] == "Article", f"{category} should map to Article"


def test_at_type_is_HowTo_for_howto_category():
    """How-To Guides category overrides @type to HowTo and adds steps."""
    html = "<h2>Step 1: Prepare the crate</h2><p>...</p><h2>Step 2: Introduce the dog</h2><p>...</p>"
    schema = _schema(category="How-To Guides", html_content=html)
    assert schema["@type"] == "HowTo"
    assert "step" in schema
    assert len(schema["step"]) >= 1


# --- Entity enrichment still works alongside the fix ---

def test_about_array_preserves_sameAs_links():
    """Fixing mainEntityOfPage must not have broken Wikipedia/Wikidata sameAs in about[]."""
    schema = _schema()
    first_about = schema["about"][0]
    assert "sameAs" in first_about
    # sameAs is either a string or a list — both contain wikipedia or wikidata URLs
    same_as = first_about["sameAs"]
    if isinstance(same_as, list):
        joined = " ".join(same_as)
    else:
        joined = same_as
    assert "wiki" in joined.lower(), f"Expected a Wiki* URL in sameAs, got {same_as!r}"
