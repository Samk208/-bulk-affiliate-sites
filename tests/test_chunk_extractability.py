"""TDD: chunk-extractability check for article_qa.

Perplexity extracts 40-60 word passage-level snippets. Indig's 1.2M ChatGPT
answer study found "ski ramp" citation pattern — front-loaded answer zones
win. This test suite drives score_chunk_extractability(), which flags
answer-zone paragraphs longer than 60 words and tracks how many land in
the 40-60w sweet spot.
"""
from article_qa import score_chunk_extractability


def _paragraph_of_n_words(n: int) -> str:
    return " ".join(["word"] * n) + "."


# --- Basic length check ---

def test_short_answer_paragraph_passes():
    """A 30-word answer paragraph is fine — no flags."""
    html = f"<h2>Topic</h2><p>{_paragraph_of_n_words(30)}</p>"
    result = score_chunk_extractability(html)
    assert result["long_paragraphs"] == []
    assert result["total_answer_paragraphs"] == 1


def test_exactly_60_words_is_the_boundary_still_ok():
    """60 words is the upper limit — not flagged."""
    html = f"<h2>Topic</h2><p>{_paragraph_of_n_words(60)}</p>"
    result = score_chunk_extractability(html)
    assert result["long_paragraphs"] == []


def test_paragraph_over_60_words_is_flagged():
    """61 words = too long for Perplexity passage extraction."""
    html = f"<h2>Topic</h2><p>{_paragraph_of_n_words(85)}</p>"
    result = score_chunk_extractability(html)
    assert len(result["long_paragraphs"]) == 1
    long = result["long_paragraphs"][0]
    assert long["word_count"] == 85
    # Snippet helps humans locate the paragraph in the source
    assert "word" in long["snippet"]


def test_multiple_long_paragraphs_each_flagged():
    html = (
        f"<h2>First</h2><p>{_paragraph_of_n_words(90)}</p>"
        f"<h2>Second</h2><p>{_paragraph_of_n_words(72)}</p>"
        f"<h2>Third</h2><p>{_paragraph_of_n_words(40)}</p>"
    )
    result = score_chunk_extractability(html)
    assert len(result["long_paragraphs"]) == 2
    assert result["total_answer_paragraphs"] == 3


# --- Sweet spot (40-60) tracking ---

def test_sweet_spot_counted():
    """Answer paragraphs in 40-60 word range are ideal for Perplexity extraction."""
    html = (
        f"<h2>A</h2><p>{_paragraph_of_n_words(45)}</p>"   # in sweet spot
        f"<h2>B</h2><p>{_paragraph_of_n_words(55)}</p>"   # in sweet spot
        f"<h2>C</h2><p>{_paragraph_of_n_words(20)}</p>"   # too short for snippet
        f"<h2>D</h2><p>{_paragraph_of_n_words(90)}</p>"   # too long
    )
    result = score_chunk_extractability(html)
    assert result["in_sweet_spot"] == 2
    assert result["total_answer_paragraphs"] == 4


def test_short_answers_not_counted_as_long():
    """A 15-word paragraph is short but not a "long" flag — it's just short."""
    html = f"<h2>Topic</h2><p>{_paragraph_of_n_words(15)}</p>"
    result = score_chunk_extractability(html)
    assert result["long_paragraphs"] == []
    assert result["in_sweet_spot"] == 0


# --- Quick Answer zone ---

def test_quick_answer_content_checked():
    """The Quick Answer box is also a citation zone — long content there flags too."""
    html = (
        '<div style="background:#f3e5f5;border:2px solid #9c27b0;">'
        f'<p>{_paragraph_of_n_words(80)}</p>'
        '</div>'
        '<h2>Body</h2><p>Normal length.</p>'
    )
    result = score_chunk_extractability(html)
    # Quick answer paragraph (80w) should be flagged
    assert len(result["long_paragraphs"]) >= 1
    assert any(p["word_count"] >= 80 for p in result["long_paragraphs"])


# --- Deep body paragraphs NOT checked ---

def test_second_paragraph_after_h2_not_checked():
    """Only the FIRST paragraph after each H2 is the citation zone.
    Second/third paragraphs can be any length — they're body depth."""
    html = (
        "<h2>Topic</h2>"
        f"<p>{_paragraph_of_n_words(40)}</p>"  # answer zone — ok
        f"<p>{_paragraph_of_n_words(200)}</p>"  # deep body — not checked
    )
    result = score_chunk_extractability(html)
    assert result["long_paragraphs"] == []
    assert result["total_answer_paragraphs"] == 1


# --- HTML robustness ---

def test_inline_tags_do_not_inflate_word_count():
    """``<strong>``/``<em>``/``<a>`` inside paragraphs should not change the word count."""
    html = (
        "<h2>Topic</h2>"
        "<p>This is <strong>important</strong> and <em>useful</em> too.</p>"
    )
    result = score_chunk_extractability(html)
    assert result["long_paragraphs"] == []
    # Word count for this paragraph should be 7, not 7+4 (the tags aren't words)
    assert result["total_answer_paragraphs"] == 1


# --- Issues message format ---

def test_issue_message_mentions_word_count():
    html = f"<h2>Topic</h2><p>{_paragraph_of_n_words(85)}</p>"
    result = score_chunk_extractability(html)
    assert result["issues"], "expected at least one issue"
    assert "85" in result["issues"][0], f"issue should cite word count: {result['issues'][0]}"


# --- No H2, no answer zones ---

def test_article_with_no_h2_has_no_answer_paragraphs():
    """An article that's all Quick Answer + raw body (no H2) should still not crash."""
    html = "<p>Just a body paragraph with no H2 above it.</p>"
    result = score_chunk_extractability(html)
    assert result["total_answer_paragraphs"] == 0
    assert result["long_paragraphs"] == []
