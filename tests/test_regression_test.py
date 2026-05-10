"""Tests for before/after article diff."""

from regression_test import diff_articles


def test_diff_visual_increase_is_safe():
    before = "<h1>x</h1><p>p</p>"
    after = ('<h1>x</h1>'
             '<div style="background:#e8f5e9;border-left:4px solid #4caf50;">tip</div>'
             '<p>p</p>')
    d = diff_articles(before, after)
    assert d.regressed is False
    assert d.callout_delta == 1


def test_diff_no_change_is_safe():
    html = '<h1>x</h1><p>same</p>'
    d = diff_articles(html, html)
    assert d.regressed is False
    assert d.callout_delta == 0


def test_diff_table_loss_is_regression():
    before = '<table><tr><td>x</td></tr></table><p>p</p>'
    after = '<p>p</p>'
    d = diff_articles(before, after)
    assert d.regressed is True
    assert any("tables" in r for r in d.regressions)


def test_diff_blockquote_loss_is_regression():
    before = '<blockquote>q</blockquote>'
    after = '<p>q</p>'
    d = diff_articles(before, after)
    assert d.regressed is True
    assert any("blockquotes" in r for r in d.regressions)


def test_diff_quick_answer_loss_is_regression():
    before = '<div style="background:#9c27b0;">Q</div>'
    after = '<p>Q</p>'
    d = diff_articles(before, after)
    assert d.regressed is True
    assert d.quick_answer_lost is True


def test_diff_schema_loss_is_regression():
    before = ('<script type="application/ld+json">{"@type": "Article"}</script>'
              '<script type="application/ld+json">{"@type": "FAQPage"}</script>')
    after = '<script type="application/ld+json">{"@type": "Article"}</script>'
    d = diff_articles(before, after)
    assert d.regressed is True
    assert "FAQPage" in d.schemas_lost


def test_diff_word_count_delta_tracked():
    before = '<p>one two three</p>'
    after = '<p>one two three four five</p>'
    d = diff_articles(before, after)
    assert d.word_count_delta == 2
