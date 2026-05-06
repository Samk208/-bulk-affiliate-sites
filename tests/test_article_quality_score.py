"""Tests for the unified quality score aggregator."""

from article_quality_score import score_article, QualityScore


def test_score_returns_quality_score():
    html = "<h1>Test</h1>" + "<p>filler. </p>" * 100
    score = score_article(html, niche="dog-comfort", slug="test", serp_brief=None)
    assert isinstance(score, QualityScore)
    assert 0 <= score.total <= 10


def test_score_full_visuals():
    html = """
    <h1>Test</h1>
    <div style="background:#9c27b0;border-left:4px solid #4a1942;">QA box</div>
    <h2>Section 1</h2>
    <div style="background:#e8f5e9;border-left:4px solid #4caf50;">Pro tip</div>
    <h2>Section 2</h2>
    <div style="background:#fff3e0;border-left:4px solid #ff9800;">Warning</div>
    <h2>Section 3</h2>
    <div style="background:#e3f2fd;border-left:4px solid #2196f3;">Key</div>
    <table><tr><td>x</td></tr></table>
    <blockquote>quote</blockquote>
    """ + "<p>filler. </p>" * 200
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=None)
    assert score.visual_richness >= 1.5


def test_score_no_visuals_low():
    html = "<h1>x</h1>" + "<p>filler. </p>" * 100
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=None)
    assert score.visual_richness < 1.0


def test_score_unverified_markers_dock_factual():
    html = ("<h1>x</h1><p>About 73% of users report this. [unverified]</p>"
            + "<p>filler. </p>" * 100)
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=None)
    assert score.factual_grounding < 1.0


def test_score_dr_name_dock_factual():
    html = ("<h1>x</h1><p>Dr. Jane Smith says this is great.</p>"
            + "<p>filler. </p>" * 100)
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=None)
    assert score.factual_grounding < 1.0
    assert any("specific_named_persons" in f for f in score.flags)


def test_score_quick_answer_boosts_geo():
    html = ('<h1>x</h1><div style="background:#9c27b0;">Quick A</div>'
            + "<p>filler. </p>" * 100)
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=None)
    assert score.geo_optimization > 0


def test_score_with_serp_brief_word_count_alignment():
    html = "<h1>x</h1>" + ("<p>filler word. </p>" * 200)  # ~400 words
    brief = {
        "min_word_count": 300, "max_word_count": 500,
        "common_h2_topics": [],
    }
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=brief)
    # word count is in range, no flag
    assert not any("word_count" in f for f in score.flags)


def test_score_with_serp_brief_word_count_outside_range_flagged():
    html = "<h1>x</h1>" + ("<p>filler. </p>" * 50)  # ~100 words
    brief = {
        "min_word_count": 1500, "max_word_count": 2500,
        "common_h2_topics": [],
    }
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=brief)
    assert any("word_count" in f for f in score.flags)


def test_score_total_caps_at_10():
    """Even with all subscores at max, total caps at 10."""
    html = ("<h1>X</h1>"
            '<div style="background:#9c27b0;border-left:4px solid #4a1942;">QA</div>'
            "<h2>1</h2><h2>2</h2><h2>3</h2><h2>4</h2><h2>5</h2>"
            "<h3>1.1</h3><h3>1.2</h3><h3>1.3</h3><h3>1.4</h3><h3>1.5</h3>"
            '<div style="background:#e8f5e9;border-left:4px solid #4caf50;">tip</div>'
            '<div style="background:#fff3e0;border-left:4px solid #ff9800;">warn</div>'
            '<div style="background:#e3f2fd;border-left:4px solid #2196f3;">key</div>'
            "<table><tr><td>x</td></tr></table>"
            "<blockquote>q</blockquote>"
            '<script type="application/ld+json">{"@type":"Article"}</script>'
            '<script type="application/ld+json">{"@type":"FAQPage"}</script>'
            "<p>According to research, this works.</p>"
            + "<p>solid evidence. </p>" * 300)
    score = score_article(html, niche="dog-comfort", slug="x", serp_brief=None)
    assert 0 <= score.total <= 10
