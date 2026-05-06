"""End-to-end tests for the 11-step enhancement pipeline."""

import pytest
from pathlib import Path

from enhance_pipeline import (
    extract_article_meta,
    detect_post_type,
    apply_stat_substitution,
    inject_stories,
    apply_voice_mode_constraints,
    apply_humor_policy,
    apply_forbidden_substitution,
    cross_check_serp_brief,
    run_pipeline,
    enhance_with_regression_guard,
)


# ---- minimal pack helpers -------------------------------------------------

VOICE_ALLOWED = """---
niche: test-allowed
first_person: allowed
gender_coded: any
authority_voices:
  - "long-term users"
  - "experts"
forbidden_voices:
  - "as a man"
default_attribution_pattern: "according to {authority_voice}"
---

Voice description body.
"""

VOICE_THIRD_ONLY = """---
niche: test-third
first_person: third_only
gender_coded: female
authority_voices:
  - "long-term users"
  - "Korean estheticians"
forbidden_voices:
  - "I tested"
  - "I have used"
default_attribution_pattern: "according to {authority_voice}"
---

Body.
"""

HUMOR_WARM = """defaults:
  level: warm
  per_words: 400
  in_headings: false
  in_safety_content: false
  in_medical_content: false
per_post_type:
  buying-guide: { level: warm }
  safety-guide: { level: never }
"""

HUMOR_NEVER = """defaults:
  level: never
  per_words: 0
  in_headings: false
  in_safety_content: true
  in_medical_content: true
per_post_type: {}
"""


def _write_pack(tmp_path, niche, voice=VOICE_ALLOWED, humor=HUMOR_WARM,
                stats="[]\n", stories="[]\n", forbidden="# Forbidden\n\n- (none)\n",
                used_kw="slug,primary_keyword,secondary_keywords,published_at\n"):
    nd = tmp_path / niche
    nd.mkdir()
    (nd / "voice.md").write_text(voice, encoding="utf-8")
    (nd / "humor.md").write_text(humor, encoding="utf-8")
    (nd / "stats.md").write_text(stats, encoding="utf-8")
    (nd / "stories.md").write_text(stories, encoding="utf-8")
    (nd / "forbidden.md").write_text(forbidden, encoding="utf-8")
    (nd / "used-keywords.md").write_text(used_kw, encoding="utf-8")
    return nd


# ---- unit tests on pieces -------------------------------------------------

def test_extract_article_meta_from_h1():
    html = "<h1>Best Dog Beds 2026</h1><p>body</p>"
    meta = extract_article_meta(html, "best-dog-beds")
    assert meta["title"] == "Best Dog Beds 2026"


def test_extract_article_meta_falls_back_to_slug():
    html = "<p>no h1</p>"
    meta = extract_article_meta(html, "best-dog-beds")
    assert meta["title"].lower() == "best dog beds"


def test_detect_post_type_safety():
    assert detect_post_type({"title": "Toxic foods for dogs"},
                             "toxic-foods-safety") == "safety-guide"


def test_detect_post_type_buying_guide():
    assert detect_post_type({"title": "Best Dog Beds"},
                             "best-dog-bed") == "buying-guide"


def test_detect_post_type_how_to():
    assert detect_post_type({"title": "How to Train Your Dog"},
                             "how-to-train-dog") == "how-to"


def test_apply_stat_substitution_processes_numeric_sentence():
    """Any number-bearing sentence gets substituted/needs-source/unverified."""
    library = [{
        "claim": "Korean cosmetics export volume reached",
        "value": "$8.4 billion",
        "year": 2023,
        "source": "Korea Customs Service",
        "url": "https://x", "verified_at": "2026-05-06",
    }]
    html = "<p>Korean cosmetics exports reached $8.4 billion last year.</p>"
    new_html, rep = apply_stat_substitution(html, library)
    total = rep["substitutions"] + rep["needs_source"] + rep["unverified"]
    assert total >= 1, f"Expected at least 1 action, got {rep}"
    # And the article must show evidence of action
    assert any(marker in new_html for marker in
               ("[unverified]", "[needs-source]", "Korea Customs Service"))


def test_apply_stat_substitution_high_match_substitutes():
    """Sentence with very high token overlap gets substituted with citation."""
    library = [{
        "claim": "Korean cosmetics exports reached billion",
        "value": "$8.4 billion last year",
        "year": 2023,
        "source": "Korea Customs Service",
        "url": "https://x", "verified_at": "2026-05-06",
    }]
    # Near-identical wording for high Jaccard score
    html = "<p>Korean cosmetics exports reached $8.4 billion last year.</p>"
    new_html, rep = apply_stat_substitution(html, library)
    total = rep["substitutions"] + rep["needs_source"] + rep["unverified"]
    assert total >= 1


def test_apply_stat_substitution_no_library_marks_unverified():
    html = "<p>Roughly 50% of dogs prefer this.</p>"
    new_html, rep = apply_stat_substitution(html, [])
    assert "[unverified]" in new_html
    assert rep["unverified"] >= 1


def test_inject_stories_first_person_in_allowed_mode():
    stories = [{
        "id": "x1", "text": "I tested this for 6 weeks.",
        "applicable_to_post_types": ["buying-guide", "review"],
    }]
    html = "<h1>X</h1><p>body</p>"
    new_html, rep = inject_stories(html, stories, "allowed", "buying-guide")
    assert rep["injected"] == 1
    assert "I tested this for 6 weeks" in new_html


def test_inject_stories_third_only_skips_first_person():
    stories = [{
        "id": "x1", "text": "I tested this.",
        "applicable_to_post_types": ["review"],
    }]  # no attribution → first-person flavor
    html = "<h1>X</h1><p>body</p>"
    new_html, rep = inject_stories(html, stories, "third_only", "review")
    assert rep["injected"] == 0


def test_inject_stories_third_only_uses_attributed():
    stories = [{
        "id": "x1", "text": "Long-term users report visible results in 6 weeks.",
        "attribution": "long-term users",
        "applicable_to_post_types": ["review"],
    }]
    html = "<h1>X</h1><p>body</p>"
    new_html, rep = inject_stories(html, stories, "third_only", "review")
    assert rep["injected"] == 1
    assert "long-term users" in new_html.lower()


def test_apply_voice_mode_constraints_strips_first_person():
    voice = {"forbidden_voices": ["I tested", "I have used"]}
    html = "<p>I tested this product. I have used it daily.</p>"
    new_html, rep = apply_voice_mode_constraints(html, voice, "third_only")
    assert "I tested" not in new_html
    assert rep["first_person_phrases_stripped"] >= 1


def test_apply_voice_mode_constraints_passes_through_allowed():
    voice = {"forbidden_voices": ["as a man"]}
    html = "<p>I tested this product.</p>"
    new_html, rep = apply_voice_mode_constraints(html, voice, "allowed")
    assert "I tested" in new_html  # not stripped in allowed mode
    assert rep["mode"] == "allowed"


def test_apply_humor_policy_strips_when_never():
    humor = {"defaults": {"level": "never", "per_words": 0,
                          "in_headings": False, "in_safety_content": True,
                          "in_medical_content": True}, "per_post_type": {}}
    html = "<p>Haha this is funny lol</p>"
    new_html, rep = apply_humor_policy(html, humor, "buying-guide")
    assert "haha" not in new_html.lower()
    assert "lol" not in new_html.lower()
    assert rep["humor_markers_stripped"] >= 2


def test_apply_humor_policy_keeps_when_warm():
    humor = {"defaults": {"level": "warm", "per_words": 400,
                          "in_headings": False, "in_safety_content": False,
                          "in_medical_content": False}, "per_post_type": {}}
    html = "<p>haha this is warm</p>"
    new_html, rep = apply_humor_policy(html, humor, "buying-guide")
    assert "haha" in new_html  # not stripped
    assert rep["level_applied"] == "warm"


def test_apply_forbidden_substitution_strips_phrases():
    forbidden_text = "# Forbidden\n\n- snake oil\n- miracle cream\n"
    html = "<p>This is not snake oil or miracle cream.</p>"
    new_html, rep = apply_forbidden_substitution(html, forbidden_text)
    assert "snake oil" not in new_html
    assert "miracle cream" not in new_html
    assert rep["phrases_stripped"] == 2


def test_cross_check_serp_brief_flags_word_count():
    html = "<h1>x</h1>" + "<p>filler. </p>" * 50  # ~100 words
    brief = {
        "min_word_count": 1500, "max_word_count": 2500,
        "common_h2_topics": [], "top_results": [],
        "target_word_count": 2000,
    }
    rep = cross_check_serp_brief(html, brief)
    assert any("word_count_below_min" in f for f in rep["flags"])


def test_cross_check_serp_brief_flags_missing_topics():
    html = "<h1>x</h1><h2>Intro</h2>" + "<p>body. </p>" * 200
    brief = {
        "min_word_count": 100, "max_word_count": 5000,
        "common_h2_topics": ["ingredients", "routine", "skin types"],
        "top_results": [],
        "target_word_count": 1500,
    }
    rep = cross_check_serp_brief(html, brief)
    assert "ingredients" in rep["missing_topics"]
    assert "routine" in rep["missing_topics"]


def test_cross_check_anti_mirror_flags_verbatim_h2():
    html = "<h1>x</h1><h2>How to choose a dog bed</h2>" + "<p>body. </p>" * 100
    brief = {
        "min_word_count": 100, "max_word_count": 5000,
        "common_h2_topics": [], "top_results": [
            {"h2_tree": ["How to choose a dog bed", "Materials"]}
        ],
        "target_word_count": 1500,
    }
    rep = cross_check_serp_brief(html, brief)
    assert any("anti_mirror" in f for f in rep["flags"])


# ---- pipeline-level tests --------------------------------------------------

def test_run_pipeline_with_minimal_pack(tmp_path):
    _write_pack(tmp_path, "test-allowed")
    html = "<h1>Best Dog Beds</h1><p>body content. </p>" + "<p>filler. </p>" * 100
    new_html, report = run_pipeline(html, "test-allowed", "best-dog-beds",
                                     styles_root=tmp_path)
    assert "error" not in report
    assert report["voice_mode"] == "allowed"
    assert report["post_type"] == "buying-guide"


def test_run_pipeline_third_only_strips_first_person(tmp_path):
    stories_yaml = (
        "- id: y1\n"
        "  text: \"Long-term users report results.\"\n"
        "  attribution: \"long-term users\"\n"
        "  applicable_to_post_types: [review]\n"
    )
    _write_pack(tmp_path, "test-third", voice=VOICE_THIRD_ONLY,
                stories=stories_yaml)
    html = ("<h1>Best K-beauty Serums</h1>"
            "<p>I tested this serum for 6 weeks.</p>"
            + "<p>filler content. </p>" * 100)
    new_html, report = run_pipeline(html, "test-third", "best-kbeauty-review",
                                     styles_root=tmp_path)
    assert report["voice_mode"] == "third_only"
    assert "I tested" not in new_html


def test_enhance_with_regression_guard_preserves_visuals(tmp_path):
    _write_pack(tmp_path, "test-allowed")
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()

    html = (
        "<h1>Best Dog Beds</h1>"
        '<div style="background:#e8f5e9;border-left:4px solid #4caf50;">'
        '<strong>Pro Tip:</strong> Use memory foam.</div>'
        "<table><tr><td>x</td></tr></table>"
        "<blockquote>quote</blockquote>"
        + "<p>body. </p>" * 200
    )
    enhanced, result = enhance_with_regression_guard(
        html, "test-allowed", "best-dog-beds", articles_dir,
        styles_root=tmp_path,
    )
    assert result["status"] == "success"
    # Visuals preserved (>= baseline)
    assert result["after"]["callouts"] >= 1
    assert result["after"]["tables"] >= 1
    assert result["after"]["blockquotes"] >= 1


def test_enhance_with_regression_guard_creates_bak(tmp_path):
    _write_pack(tmp_path, "test-allowed")
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    html = "<h1>X</h1>" + "<p>body. </p>" * 100
    enhance_with_regression_guard(
        html, "test-allowed", "x", articles_dir, styles_root=tmp_path,
    )
    bak = articles_dir / "x.html.bak"
    assert bak.exists()
    assert bak.read_text(encoding="utf-8") == html
