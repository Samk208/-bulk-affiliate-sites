"""Tests for per-niche reference pack loading + validation."""

import pytest

from reference_pack_loader import (
    load_pack,
    PackValidationError,
    ReferencePack,
    parse_forbidden_phrases,
)


VOICE_OK = """---
niche: test-niche
first_person: allowed
gender_coded: any
authority_voices:
  - "experts"
  - "long-term users"
forbidden_voices: []
default_attribution_pattern: "according to {authority_voice}"
---

# Voice description

Calm and direct.
"""

HUMOR_OK = """defaults:
  level: warm
  per_words: 400
  in_headings: false
  in_safety_content: false
  in_medical_content: false
per_post_type: {}
"""


def _write_minimal_pack(tmp_path, niche="test-niche", voice=VOICE_OK,
                       humor=HUMOR_OK, stats="[]\n", stories="[]\n",
                       forbidden="# Forbidden\n", used_kw=""):
    niche_dir = tmp_path / niche
    niche_dir.mkdir()
    (niche_dir / "voice.md").write_text(voice, encoding="utf-8")
    (niche_dir / "humor.md").write_text(humor, encoding="utf-8")
    (niche_dir / "stats.md").write_text(stats, encoding="utf-8")
    (niche_dir / "stories.md").write_text(stories, encoding="utf-8")
    (niche_dir / "forbidden.md").write_text(forbidden, encoding="utf-8")
    (niche_dir / "used-keywords.md").write_text(used_kw, encoding="utf-8")
    return niche_dir


def test_load_minimal_valid_pack(tmp_path):
    _write_minimal_pack(tmp_path)
    pack = load_pack("test-niche", styles_root=tmp_path)
    assert isinstance(pack, ReferencePack)
    assert pack.voice["first_person"] == "allowed"
    assert pack.humor["defaults"]["level"] == "warm"


def test_load_missing_niche_raises(tmp_path):
    with pytest.raises(PackValidationError, match="niche directory not found"):
        load_pack("nonexistent", styles_root=tmp_path)


def test_voice_missing_required_field_raises(tmp_path):
    _write_minimal_pack(
        tmp_path,
        voice="---\nniche: x\n---\nbody\n",
    )
    with pytest.raises(PackValidationError, match="missing required fields"):
        load_pack("test-niche", styles_root=tmp_path)


def test_voice_invalid_first_person_raises(tmp_path):
    bad = (
        "---\nniche: bad\nfirst_person: invalid_value\n"
        "gender_coded: any\nauthority_voices: [a, b]\nforbidden_voices: []\n"
        "default_attribution_pattern: \"x\"\n---\n"
    )
    _write_minimal_pack(tmp_path, voice=bad)
    with pytest.raises(PackValidationError, match="first_person"):
        load_pack("test-niche", styles_root=tmp_path)


def test_voice_invalid_gender_coded_raises(tmp_path):
    bad = (
        "---\nniche: bad\nfirst_person: allowed\n"
        "gender_coded: nonbinary_unsupported\nauthority_voices: [a, b]\n"
        "forbidden_voices: []\ndefault_attribution_pattern: \"x\"\n---\n"
    )
    _write_minimal_pack(tmp_path, voice=bad)
    with pytest.raises(PackValidationError, match="gender_coded"):
        load_pack("test-niche", styles_root=tmp_path)


def test_humor_invalid_level_raises(tmp_path):
    bad_humor = (
        "defaults:\n  level: unknown\n  per_words: 400\n"
        "  in_headings: false\n  in_safety_content: false\n"
        "  in_medical_content: false\nper_post_type: {}\n"
    )
    _write_minimal_pack(tmp_path, humor=bad_humor)
    with pytest.raises(PackValidationError, match="level"):
        load_pack("test-niche", styles_root=tmp_path)


def test_humor_missing_defaults_raises(tmp_path):
    _write_minimal_pack(tmp_path, humor="per_post_type: {}\n")
    with pytest.raises(PackValidationError, match="defaults"):
        load_pack("test-niche", styles_root=tmp_path)


def test_third_only_stories_must_have_attribution(tmp_path):
    third_only_voice = """---
niche: kbeauty
first_person: third_only
gender_coded: female
authority_voices:
  - "long-term users"
  - "Korean estheticians"
forbidden_voices: []
default_attribution_pattern: "according to {authority_voice}"
---
"""
    bad_stories = "- text: \"a story\"\n  applicable_to_post_types: [review]\n"
    _write_minimal_pack(tmp_path, niche="kbeauty",
                       voice=third_only_voice, stories=bad_stories)
    with pytest.raises(PackValidationError, match="attribution"):
        load_pack("kbeauty", styles_root=tmp_path)


def test_third_only_stories_invalid_attribution_raises(tmp_path):
    third_only_voice = """---
niche: kbeauty
first_person: third_only
gender_coded: female
authority_voices:
  - "long-term users"
forbidden_voices: []
default_attribution_pattern: "according to {authority_voice}"
---
"""
    bad_stories = ("- text: \"a story\"\n"
                   "  attribution: \"Dr. Fake Person\"\n"
                   "  applicable_to_post_types: [review]\n")
    _write_minimal_pack(tmp_path, niche="kbeauty",
                       voice=third_only_voice, stories=bad_stories)
    with pytest.raises(PackValidationError, match="not in.*authority_voices"):
        load_pack("kbeauty", styles_root=tmp_path)


def test_third_only_stories_valid_attribution_passes(tmp_path):
    third_only_voice = """---
niche: kbeauty
first_person: third_only
gender_coded: female
authority_voices:
  - "long-term users"
forbidden_voices: []
default_attribution_pattern: "according to {authority_voice}"
---
"""
    good_stories = ("- text: \"a story\"\n"
                    "  attribution: \"long-term users\"\n"
                    "  applicable_to_post_types: [review]\n")
    _write_minimal_pack(tmp_path, niche="kbeauty",
                       voice=third_only_voice, stories=good_stories)
    pack = load_pack("kbeauty", styles_root=tmp_path)
    assert len(pack.stories) == 1


def test_parse_forbidden_phrases_extracts_bullets():
    text = """# Forbidden phrases

- bad phrase one
- "bad phrase two"
- (none yet)
- another bad one
"""
    phrases = parse_forbidden_phrases(text)
    assert "bad phrase one" in phrases
    assert "bad phrase two" in phrases
    assert "another bad one" in phrases
    assert "(none yet)" not in phrases


def test_used_keywords_csv_loaded(tmp_path):
    used_kw = "slug,primary_keyword,secondary_keywords,published_at\nfoo,bar baz,quz,2026-05-06\n"
    _write_minimal_pack(tmp_path, used_kw=used_kw)
    pack = load_pack("test-niche", styles_root=tmp_path)
    assert len(pack.used_keywords) == 1
    assert pack.used_keywords[0]["primary_keyword"] == "bar baz"
