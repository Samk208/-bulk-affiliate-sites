"""TDD: Algorithmic Authorship check for article_qa.

Koray Tuğberk Gübür's highest-ROI single rule: every H2 should be phrased as
a user question AND followed by a <=40-word extractive answer. This combines
four independently-confirmed findings (Perplexity passage extraction, Indig
front-loading, chunk extractability, and Koray's node-edge entity structure)
into one structural pattern.

FAQ sections are exempt — they already have question-formatted H3s.
"""
from article_qa import score_algorithmic_authorship


# --- Question detection ---

def test_h2_ending_with_question_mark_is_question():
    html = "<h2>How do I train my dog?</h2><p>Train daily for five minutes.</p>"
    result = score_algorithmic_authorship(html)
    assert result["question_h2s"] == 1


def test_h2_as_statement_is_not_question():
    html = "<h2>Training Your Dog</h2><p>Train daily for five minutes.</p>"
    result = score_algorithmic_authorship(html)
    assert result["question_h2s"] == 0


def test_h2_starting_with_interrogative_word_counts_even_without_mark():
    """H2s like "What makes a good bed" count as questions even without `?`.
    Interrogatives at sentence start: what, why, how, when, where, who, which, is, are, does, do, can, should."""
    for word in ("What", "Why", "How", "When", "Where", "Who", "Which", "Is", "Are", "Does", "Do", "Can", "Should"):
        html = f"<h2>{word} good dog beds last</h2><p>Five to seven years typically.</p>"
        result = score_algorithmic_authorship(html)
        assert result["question_h2s"] == 1, f"H2 starting with '{word}' should count as a question"


# --- Extractive answer detection (<=40 words) ---

def test_short_answer_paragraph_counts_as_extractive():
    html = "<h2>How long?</h2><p>Most dogs need five to seven minutes per session.</p>"
    result = score_algorithmic_authorship(html)
    assert result["extractive_answers"] == 1


def test_long_answer_paragraph_not_extractive():
    long_p = " ".join(["word"] * 60)
    html = f"<h2>How long?</h2><p>{long_p}</p>"
    result = score_algorithmic_authorship(html)
    assert result["extractive_answers"] == 0


def test_exactly_40_words_is_boundary_still_extractive():
    p40 = " ".join(["word"] * 40) + "."
    html = f"<h2>How long?</h2><p>{p40}</p>"
    result = score_algorithmic_authorship(html)
    assert result["extractive_answers"] == 1


# --- Structural totals ---

def test_total_h2s_counted():
    html = (
        "<h2>First</h2><p>short.</p>"
        "<h2>Second</h2><p>short.</p>"
        "<h2>Third</h2><p>short.</p>"
    )
    result = score_algorithmic_authorship(html)
    assert result["total_h2s"] == 3


def test_score_pct_rewards_both_conditions_met():
    """score_pct = H2s with BOTH question format AND extractive answer."""
    html = (
        # Full compliance: question H2 + short answer
        "<h2>How long should training last?</h2><p>Five to seven minutes works best.</p>"
        # Partial: question but answer too long
        f"<h2>What is the best food?</h2><p>{' '.join(['word']*70)}</p>"
        # Partial: short answer but H2 not a question
        "<h2>Training Basics</h2><p>Start simple and build up.</p>"
        # Fully non-compliant
        f"<h2>Supplies</h2><p>{' '.join(['word']*80)}</p>"
    )
    result = score_algorithmic_authorship(html)
    # Only the first H2 passes both checks → 1/4 = 25%
    assert result["score_pct"] == 25.0


# --- FAQ exemption ---

def test_faq_section_h2_is_exempt():
    """FAQ sections already contain question H3s — don't count the FAQ H2 itself."""
    html = (
        "<h2>How long?</h2><p>Five minutes.</p>"
        "<h2>Frequently Asked Questions</h2>"
        "<h3>Is crate training cruel?</h3><p>No, when done correctly.</p>"
    )
    result = score_algorithmic_authorship(html)
    assert result["total_h2s"] == 1, "FAQ H2 should be excluded from totals"


# --- Issue messages are actionable ---

def test_issue_names_the_failing_h2():
    html = "<h2>Training Basics</h2><p>Start simple and build up gradually over weeks.</p>"
    result = score_algorithmic_authorship(html)
    assert result["issues"], "non-question H2 should produce an issue"
    joined = " ".join(result["issues"]).lower()
    assert "training basics" in joined, (
        f"issue should reference the offending H2 text; got: {result['issues']}"
    )


# --- Robustness ---

def test_h2_without_paragraph_flagged_as_missing_answer():
    """An H2 followed directly by another H2 (no answer paragraph) is non-compliant."""
    html = "<h2>How long?</h2><h2>Next topic</h2>"
    result = score_algorithmic_authorship(html)
    assert result["total_h2s"] == 2
    assert result["extractive_answers"] == 0


def test_empty_html_does_not_crash():
    result = score_algorithmic_authorship("")
    assert result["total_h2s"] == 0
    assert result["score_pct"] == 0.0
