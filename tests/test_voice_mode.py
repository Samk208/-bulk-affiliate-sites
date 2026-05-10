"""Tests for the 3-layer voice mode determination."""

from voice_mode import determine_voice_mode


def test_niche_default_allowed():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "Best dog beds"}, voice, "buying-guide"
    ) == "allowed"


def test_niche_default_third_only_passes_through():
    voice = {"first_person": "third_only"}
    assert determine_voice_mode(
        {"title": "Best K-beauty serums"}, voice, "review"
    ) == "third_only"


def test_post_type_safety_forces_third_only():
    voice = {"first_person": "allowed"}  # niche allows first-person
    assert determine_voice_mode(
        {"title": "How to safely brush dog teeth"}, voice, "safety-guide"
    ) == "third_only"


def test_post_type_clinical_forces_third_only():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "Senior dog arthritis"}, voice, "clinical-explainer"
    ) == "third_only"


def test_post_type_treatment_forces_third_only():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "Cat dental cleaning"}, voice, "treatment-guide"
    ) == "third_only"


def test_title_for_women_forces_third_only():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "Best dog breeds for women living alone"}, voice, "buying-guide"
    ) == "third_only"


def test_title_pregnancy_forces_third_only():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "Cat care during pregnancy"}, voice, "how-to"
    ) == "third_only"


def test_title_mascara_forces_third_only_even_if_niche_allows():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "How to apply waterproof mascara"}, voice, "how-to"
    ) == "third_only"


def test_title_dermatologist_forces_third_only():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "What dermatologists recommend for acne"}, voice, "tips"
    ) == "third_only"


def test_explicit_override_wins_over_niche_third_only():
    voice = {"first_person": "third_only"}
    assert determine_voice_mode(
        {"title": "Best K-beauty serums", "voice_mode_override": "allowed"},
        voice, "review",
    ) == "allowed"


def test_explicit_override_wins_over_title_trigger():
    voice = {"first_person": "allowed"}
    assert determine_voice_mode(
        {"title": "Best mascara", "voice_mode_override": "allowed"},
        voice, "review",
    ) == "allowed"


def test_unknown_first_person_value_defaults_to_allowed():
    voice = {"first_person": "garbage"}
    assert determine_voice_mode({"title": "x"}, voice, "review") == "allowed"


def test_missing_first_person_defaults_to_allowed():
    voice = {}
    assert determine_voice_mode({"title": "x"}, voice, "review") == "allowed"


def test_kbeauty_safe_article_stays_third_only():
    """K-beauty (third_only niche) should stay third_only on safety post type."""
    voice = {"first_person": "third_only"}
    assert determine_voice_mode(
        {"title": "Snail mucin allergy reactions"}, voice, "safety-guide"
    ) == "third_only"


def test_invalid_override_value_ignored():
    voice = {"first_person": "third_only"}
    # Override with an invalid value should be ignored — niche default wins
    assert determine_voice_mode(
        {"title": "x", "voice_mode_override": "not_a_real_mode"},
        voice, "review",
    ) == "third_only"
