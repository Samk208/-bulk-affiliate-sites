"""TDD: declarative-language linter for article_qa.

GEO paper (arXiv:2311.09735) finding: declarative language produces a +14%
aggregate citation lift over hedging. This test suite drives implementation
of score_declarative_language() which flags hedges in "answer zones" (the
Quick Answer box and the first paragraph after each H2) — the zones AI
search engines most likely extract.
"""
import pytest
from article_qa import score_declarative_language


HEDGE_WORDS = ["may", "might", "could possibly", "perhaps", "potentially", "arguably"]


# --- RED: basic hedge detection ---

def test_clean_declarative_paragraph_has_no_issues():
    html = "<h2>Memory Foam</h2><p>Memory foam reduces joint pain by 40%.</p>"
    result = score_declarative_language(html)
    assert result["hedge_count"] == 0
    assert result["issues"] == []


def test_hedge_in_first_paragraph_after_h2_flagged():
    """The first paragraph after each H2 is a citation zone — hedges must flag."""
    html = "<h2>Memory Foam</h2><p>Memory foam may help reduce joint pain.</p>"
    result = score_declarative_language(html)
    assert result["hedge_count"] >= 1
    assert any("may" in i.lower() for i in result["issues"])


def test_hedge_inside_quick_answer_box_flagged():
    """Quick Answer is the AI-search citation target — any hedge there is bad."""
    html = (
        '<div style="background:#f3e5f5;border:2px solid #9c27b0;">'
        '<ul><li>Perhaps the best option for arthritis</li></ul>'
        '</div>'
        '<h2>Body</h2><p>Declarative content here.</p>'
    )
    result = score_declarative_language(html)
    assert result["hedge_count"] >= 1
    assert any("perhaps" in i.lower() for i in result["issues"])


@pytest.mark.parametrize("hedge", HEDGE_WORDS)
def test_all_common_hedges_detected(hedge):
    """Every hedge word in our list must be catchable in a citation zone."""
    html = f"<h2>Foo</h2><p>This {hedge} work for most dogs.</p>"
    result = score_declarative_language(html)
    assert result["hedge_count"] >= 1, f"Missed hedge: {hedge!r}"


# --- Scope: only answer zones count ---

def test_hedge_in_deep_body_not_counted_as_issue():
    """Hedges in the SECOND paragraph after an H2 are tolerated (not a citation zone)."""
    html = (
        "<h2>Section</h2>"
        "<p>Memory foam reduces pressure on joints.</p>"
        "<p>Some owners may prefer alternatives for their puppies.</p>"
    )
    result = score_declarative_language(html)
    # Hedge exists in body but is not in a flagged zone — issues list empty
    assert result["issues"] == [], (
        f"Hedge in deep body should not flag; got issues={result['issues']}"
    )


# --- Substring safety ---

def test_hedge_word_not_matched_as_substring():
    """'perhaps' must not match inside words like 'perhapss' (unlikely) or
    be confused with innocent words. 'may' must not match inside 'mayor', 'maybe'."""
    html = (
        "<h2>Politics</h2>"
        "<p>The mayor of Seoul visited the dog park, and maybe the best part was the view.</p>"
    )
    result = score_declarative_language(html)
    # "maybe" IS a hedge; "mayor" is NOT. But "may" appearing as a prefix of "maybe"
    # or "mayor" must not each count separately. Accept 0 or 1 count, never 2+.
    assert result["hedge_count"] <= 1


def test_may_in_proper_noun_not_flagged():
    """The month 'May' (capital M) inside sentences should not trigger 'may' hedge."""
    html = "<h2>Summer</h2><p>In May, the weather warms up considerably.</p>"
    result = score_declarative_language(html)
    assert result["hedge_count"] == 0, "Capitalized 'May' (month) must not match 'may' hedge"


# --- Density metric ---

def test_density_per_1kw_calculated():
    """Returned metric: hedges per 1,000 words across flagged zones."""
    html = (
        "<h2>Foo</h2>"
        "<p>This might work and that could possibly help too.</p>"
    )
    result = score_declarative_language(html)
    assert "density_per_1kw" in result
    assert result["density_per_1kw"] > 0
