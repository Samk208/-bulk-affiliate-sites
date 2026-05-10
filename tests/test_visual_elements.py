"""Tests for visual element counting (used by regression check + QA score)."""

from visual_elements import count_visual_elements, visual_regressions, ElementCounts


def test_count_callouts():
    html = """
    <div style="background:#e8f5e9;border-left:4px solid #4caf50;">Pro tip 1</div>
    <p>some text</p>
    <div style="background:#fff3e0;border-left:4px solid #ff9800;">Warning</div>
    """
    counts = count_visual_elements(html)
    assert counts.callouts == 2


def test_count_tables():
    html = "<table><tr><td>x</td></tr></table><p>y</p><table></table>"
    counts = count_visual_elements(html)
    assert counts.tables == 2


def test_count_blockquotes():
    html = '<blockquote>quote 1</blockquote><blockquote>quote 2</blockquote>'
    counts = count_visual_elements(html)
    assert counts.blockquotes == 2


def test_count_quick_answer_present():
    html = '<div style="background:#9c27b0;">Quick answer</div>'
    counts = count_visual_elements(html)
    assert counts.quick_answer_present is True


def test_count_quick_answer_absent():
    html = '<p>no quick answer</p>'
    counts = count_visual_elements(html)
    assert counts.quick_answer_present is False


def test_count_quick_answer_via_bg_color():
    """Match Quick Answer by its background color too."""
    html = '<div style="background:#f3e5f5;border:1px solid #ccc;">Q</div>'
    counts = count_visual_elements(html)
    assert counts.quick_answer_present is True


def test_count_images():
    html = '<img src="a.jpg"><p>x</p><img src="b.png">'
    counts = count_visual_elements(html)
    assert counts.images == 2


def test_count_h2_h3():
    html = "<h2>One</h2><h3>1.1</h3><h2>Two</h2><h3>2.1</h3><h3>2.2</h3>"
    counts = count_visual_elements(html)
    assert counts.h2_count == 2
    assert counts.h3_count == 3


def test_word_count_strips_tags():
    html = "<p>one two three four five</p>"
    counts = count_visual_elements(html)
    assert counts.word_count == 5


def test_extract_jsonld_schema_types():
    html = '<script type="application/ld+json">{"@type": "Article", "headline": "x"}</script>'
    counts = count_visual_elements(html)
    assert "Article" in counts.schema_types


def test_visual_regressions_empty_when_counts_increase():
    before = ElementCounts(callouts=2, tables=1)
    after = ElementCounts(callouts=3, tables=2)
    issues = visual_regressions(before, after)
    assert issues == []


def test_visual_regressions_flags_decrease():
    before = ElementCounts(callouts=3, tables=1, blockquotes=1)
    after = ElementCounts(callouts=2, tables=1, blockquotes=0)
    issues = visual_regressions(before, after)
    assert any("callouts" in i for i in issues)
    assert any("blockquotes" in i for i in issues)


def test_visual_regressions_quick_answer_loss():
    before = ElementCounts(quick_answer_present=True)
    after = ElementCounts(quick_answer_present=False)
    issues = visual_regressions(before, after)
    assert any("quick_answer" in i for i in issues)


def test_visual_regressions_schema_drop():
    before = ElementCounts(schema_types=["Article", "FAQPage"])
    after = ElementCounts(schema_types=["Article"])
    issues = visual_regressions(before, after)
    assert any("FAQPage" in i for i in issues)
