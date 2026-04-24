"""Regression tests for article_enhancer.fix_bare_markdown_bold().

NOTE: Regression tests (not TDD) — pin down the fix shipped 2026-04-17
for the Kimi K2.5 `**Pros:**` markdown-rendering bug found in 4/105 real
dog-comfort articles.
"""
from article_enhancer import fix_bare_markdown_bold


def test_bare_bold_with_colon_converted():
    """The canonical bug: ``**Pros:**`` in list items."""
    html = "<li>**Pros:** durable and chew-resistant</li>"
    out, count = fix_bare_markdown_bold(html)
    assert count == 1
    assert "<strong>Pros:</strong>" in out
    assert "**" not in out


def test_bare_bold_without_colon_converted():
    """General markdown bold — not just Label: patterns."""
    html = "<p>The answer is **immediate relief** in most cases.</p>"
    out, count = fix_bare_markdown_bold(html)
    assert count == 1
    assert "<strong>immediate relief</strong>" in out


def test_code_blocks_untouched():
    """Markdown inside ``<code>`` is likely intentional — leave it alone."""
    html = "<code>use **bold** markdown</code><p>But **this** should change</p>"
    out, count = fix_bare_markdown_bold(html)
    assert count == 1
    assert "<code>use **bold** markdown</code>" in out, "code block content must be preserved verbatim"
    assert "<strong>this</strong>" in out


def test_pre_blocks_untouched():
    """Same rule as code — <pre> is verbatim."""
    html = "<pre>some **preformatted** text</pre><p>regular **bold** here</p>"
    out, count = fix_bare_markdown_bold(html)
    assert count == 1
    assert "<pre>some **preformatted** text</pre>" in out


def test_already_wrapped_strong_not_double_wrapped():
    """``<strong>X</strong>`` has no literal asterisks — should be a no-op."""
    html = "<p><strong>Pros:</strong> already done</p>"
    out, count = fix_bare_markdown_bold(html)
    assert count == 0
    assert out == html


def test_multiline_markdown_not_matched():
    """Guard: ``**`` on one line and ``**`` on another must NOT match — that's
    almost always a stray double-asterisk, not a deliberate multi-line bold."""
    html = "<p>**start of bold\nend of bold**</p>"
    out, count = fix_bare_markdown_bold(html)
    assert count == 0
    assert out == html


def test_multiple_bolds_all_converted():
    """An article with many ``**Pros:**``/``**Cons:**`` lines (real Kimi output)."""
    html = (
        "<ul>"
        "<li>**Pros:** soft and supportive</li>"
        "<li>**Cons:** expensive</li>"
        "<li>**Best for:** large breeds</li>"
        "</ul>"
    )
    out, count = fix_bare_markdown_bold(html)
    assert count == 3
    assert out.count("<strong>") == 3
    assert out.count("</strong>") == 3
    assert "**" not in out
