"""Tests for the LLM rewrite step (γ). LLM calls are mocked — no API spend."""

import json

from llm_rewriter import (
    apply_llm_rewrite,
    find_unverified_sentences,
    make_rewrite_messages,
    parse_rewrite_response,
)


# --- find_unverified_sentences ---------------------------------------------

def test_find_single_marker():
    html = "<p>Some intro. The bed reduces pain by 40%. [unverified]</p>"
    sents = find_unverified_sentences(html)
    assert len(sents) == 1
    assert "reduces pain by 40%. [unverified]" in sents[0]


def test_find_two_markers_in_same_paragraph():
    html = (
        "<p>Studies show 40% improvement. [unverified] "
        "Other research finds 60% reduction. [unverified]</p>"
    )
    sents = find_unverified_sentences(html)
    assert len(sents) == 2
    assert "Studies show 40% improvement. [unverified]" in sents[0]
    assert "Other research finds 60% reduction. [unverified]" in sents[1]


def test_find_skips_marker_with_no_preceding_sentence_end():
    html = "<p>Loose marker [unverified] with no period before.</p>"
    sents = find_unverified_sentences(html)
    assert sents == []


def test_find_walks_back_to_html_tag_boundary():
    html = "<p>A. B. C with stat 50%. [unverified]</p>"
    sents = find_unverified_sentences(html)
    assert len(sents) == 1
    assert "C with stat 50%. [unverified]" in sents[0]
    # Should NOT include "A." or "B." prior sentences
    assert sents[0].count(".") <= 2  # one period for "C..." one for marker context


# --- prompt construction ---------------------------------------------------

def test_make_rewrite_messages_includes_library_and_sentences():
    library = [
        {"claim": "adult dog daily sleep", "value": "12 to 14 hours",
         "source": "AKC", "year": 2024},
    ]
    sentences = ["Dogs sleep 99 hours a day. [unverified]"]
    msgs = make_rewrite_messages(sentences, library)
    assert msgs[0]["role"] == "system"
    assert "NEVER invent new numbers" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "12 to 14 hours" in msgs[1]["content"]
    assert "AKC" in msgs[1]["content"]
    assert "Dogs sleep 99 hours" in msgs[1]["content"]
    assert "JSON array of 1" in msgs[1]["content"]


# --- response parsing ------------------------------------------------------

def test_parse_clean_json_array():
    content = json.dumps(["rewrite one.", "rewrite two."])
    out = parse_rewrite_response(content, 2)
    assert out == ["rewrite one.", "rewrite two."]


def test_parse_strips_markdown_fences():
    content = "```json\n" + json.dumps(["only one."]) + "\n```"
    out = parse_rewrite_response(content, 1)
    assert out == ["only one."]


def test_parse_pads_short_response():
    content = json.dumps(["only got one back."])
    out = parse_rewrite_response(content, 3)
    assert len(out) == 3
    assert out[0] == "only got one back."
    assert out[1] == "[REMOVE]"
    assert out[2] == "[REMOVE]"


def test_parse_truncates_long_response():
    content = json.dumps(["a", "b", "c", "d"])
    out = parse_rewrite_response(content, 2)
    assert out == ["a", "b"]


def test_parse_falls_back_to_lines_when_not_json():
    content = "1. first rewrite.\n2. second rewrite."
    out = parse_rewrite_response(content, 2)
    assert "first rewrite" in out[0]
    assert "second rewrite" in out[1]


# --- end-to-end with mocked LLM --------------------------------------------

def test_apply_llm_rewrite_replaces_with_library_stat():
    html = (
        "<p>Article opens. According to research, dogs sleep 99 hours daily. "
        "[unverified] More content here.</p>"
    )
    library = [
        {"claim": "adult dog daily sleep", "value": "12 to 14 hours",
         "source": "AKC", "year": 2024},
    ]
    fake_response = json.dumps([
        "According to AKC research, adult dogs sleep 12 to 14 hours daily."
    ])
    fake_llm = lambda msgs: fake_response  # noqa: E731

    new_html, rep = apply_llm_rewrite(html, library, llm_call=fake_llm)
    assert rep["rewritten"] == 1
    assert rep["removed"] == 0
    assert rep["errors"] == 0
    assert "[unverified]" not in new_html
    assert "12 to 14 hours" in new_html
    # Surrounding content preserved
    assert "Article opens" in new_html
    assert "More content here" in new_html


def test_apply_llm_rewrite_removes_when_remove_token():
    html = "<p>Intro. Made-up 99% claim. [unverified] Outro.</p>"
    fake_llm = lambda msgs: json.dumps(["[REMOVE]"])  # noqa: E731

    new_html, rep = apply_llm_rewrite(html, [], llm_call=fake_llm)
    assert rep["removed"] == 1
    assert rep["rewritten"] == 0
    assert "[unverified]" not in new_html
    assert "99%" not in new_html
    assert "Intro" in new_html
    assert "Outro" in new_html


def test_apply_llm_rewrite_handles_zero_flags_noop():
    html = "<p>Clean article with no markers. Done.</p>"
    fake_llm = lambda msgs: ""  # noqa: E731  — should never be called
    new_html, rep = apply_llm_rewrite(html, [], llm_call=fake_llm)
    assert new_html == html
    assert rep["flagged"] == 0
    assert rep["rewritten"] == 0
    assert rep["errors"] == 0


def test_apply_llm_rewrite_records_error_on_llm_failure():
    html = "<p>Sentence with 50% claim. [unverified]</p>"
    def boom(msgs):
        raise ConnectionError("API down")
    new_html, rep = apply_llm_rewrite(html, [], llm_call=boom)
    assert rep["errors"] == 1
    assert "API down" in rep.get("error_msg", "")
    # HTML left unchanged on error
    assert new_html == html


def test_apply_llm_rewrite_strips_leftover_marker_from_rewrite():
    """If LLM accidentally keeps the [unverified] marker in its output, strip it."""
    html = "<p>Original 50% claim. [unverified]</p>"
    fake_llm = lambda msgs: json.dumps(  # noqa: E731
        ["Cautious rewrite without numbers. [unverified]"]
    )
    new_html, rep = apply_llm_rewrite(html, [], llm_call=fake_llm)
    assert "[unverified]" not in new_html
    assert "Cautious rewrite without numbers." in new_html


def test_prompt_treats_source_citations_as_suspect():
    """The system prompt must instruct the LLM to NOT trust source citations.

    Reason: in the 2026-05-07 pilot, sentences like
        'AVMA notes that brachycephalic dogs account for over 20%...'
    were left unchanged because the LLM trusted the AVMA wrapper. The fix is
    explicit: any number not in the verified library is suspect, regardless
    of attribution.
    """
    library = [{"claim": "x", "value": "y", "source": "z", "year": 2024}]
    sentences = ["AVMA notes that 20% of dogs do X. [unverified]"]
    msgs = make_rewrite_messages(sentences, library)
    sys_prompt = msgs[0]["content"].lower()
    # Must mention treating citations / sources as suspect or unreliable
    assert (
        "citation" in sys_prompt or "source" in sys_prompt
    ), "prompt should reference citations/sources"
    # Must explicitly not-trust attribution wrappers
    assert any(token in sys_prompt for token in [
        "do not trust", "do not assume", "treat all citations as suspect",
        "regardless of attribution", "even if attributed",
    ]), "prompt should explicitly distrust attribution wrappers"
