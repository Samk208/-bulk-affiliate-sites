#!/usr/bin/env python3
"""Tests for the 4 new GEO/citation scorers added to article_qa.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from article_qa import (
        score_passage_self_containment,
        score_stats_attribution,
        validate_quick_answer_box,
        check_faq_schema,
    )
except ImportError as _import_err:
    # Not all 4 functions exist yet — import only what's available.
    # Tests for missing functions will error individually when run.
    from article_qa import score_passage_self_containment  # noqa: F401
    try:
        from article_qa import score_stats_attribution  # noqa: F401
    except ImportError:
        score_stats_attribution = None
    try:
        from article_qa import validate_quick_answer_box  # noqa: F401
    except ImportError:
        validate_quick_answer_box = None
    try:
        from article_qa import check_faq_schema  # noqa: F401
    except ImportError:
        check_faq_schema = None


class TestPassageSelfContainment(unittest.TestCase):

    def test_dependent_opener_in_answer_zone_flagged(self):
        html = """
        <div style="background:#9c27b0;padding:16px">
            <p>These are the main options to consider.</p>
        </div>
        <h2>Why do dogs need orthopedic beds?</h2>
        <p>This helps distribute weight evenly across joints.</p>
        """
        result = score_passage_self_containment(html)
        self.assertGreater(result["dependent_count"], 0)
        self.assertTrue(any("This" in i or "These" in i for i in result["issues"]))

    def test_self_contained_openers_not_flagged(self):
        html = """
        <div style="background:#9c27b0;padding:16px">
            <p>Orthopedic dog beds reduce pressure on aging joints.</p>
        </div>
        <h2>Why do dogs need orthopedic beds?</h2>
        <p>Dogs with arthritis benefit from memory foam that conforms to their body shape.</p>
        """
        result = score_passage_self_containment(html)
        self.assertEqual(result["dependent_count"], 0)
        self.assertEqual(result["issues"], [])

    def test_as_mentioned_flagged(self):
        html = """
        <h2>What are the best features?</h2>
        <p>As mentioned above, the foam density matters most.</p>
        """
        result = score_passage_self_containment(html)
        self.assertGreater(result["dependent_count"], 0)

    def test_returns_required_keys(self):
        result = score_passage_self_containment("<p>Hello world.</p>")
        self.assertIn("dependent_count", result)
        self.assertIn("issues", result)
        self.assertIn("density_per_1kw", result)


class TestStatsAttribution(unittest.TestCase):

    def test_unattributed_stat_flagged(self):
        html = "<p>75% of dogs develop joint issues after age 7.</p>"
        result = score_stats_attribution(html)
        self.assertGreater(result["unattributed_count"], 0)

    def test_attributed_stat_not_flagged(self):
        html = "<p>According to the AKC, 75% of dogs develop joint issues after age 7.</p>"
        result = score_stats_attribution(html)
        self.assertEqual(result["unattributed_count"], 0)

    def test_attribution_after_stat_counts(self):
        # Attribution can come after the stat within 15 words
        html = "<p>75% success rate, according to a 2024 AKC study on senior dogs.</p>"
        result = score_stats_attribution(html)
        self.assertEqual(result["unattributed_count"], 0)

    def test_attribution_rate_calculation(self):
        html = """
        <p>According to the ADA, 90% of people don't floss daily.</p>
        <p>Studies show 45% improvement in retention.</p>
        <p>Per the WHO, 60% of adults have gum disease.</p>
        """
        result = score_stats_attribution(html)
        # All 3 are attributed: "according to", "studies show", "per the"
        self.assertEqual(result["total_stats"], 3)
        self.assertEqual(result["attributed_count"], 3)
        self.assertEqual(result["unattributed_count"], 0)

    def test_returns_required_keys(self):
        result = score_stats_attribution("<p>Hello world.</p>")
        self.assertIn("total_stats", result)
        self.assertIn("attributed_count", result)
        self.assertIn("unattributed_count", result)
        self.assertIn("attribution_rate", result)
        self.assertIn("issues", result)

    def test_year_citation_counts_as_attribution(self):
        html = "<p>Studies show 75% success rate (2024) on senior dogs.</p>"
        result = score_stats_attribution(html)
        self.assertEqual(result["unattributed_count"], 0,
                         f"Expected (2024) to count as attribution, got: {result}")

    def test_source_colon_counts_as_attribution(self):
        # source: must be in the same sentence (no period before it) to be within the 15-word window
        html = "<p>75% of pet owners report satisfaction, source: APPA 2024 survey.</p>"
        result = score_stats_attribution(html)
        self.assertEqual(result["unattributed_count"], 0,
                         f"Expected 'source:' to count as attribution, got: {result}")

    def test_studies_show_counts_as_attribution(self):
        html = "<p>Studies show 75% of dogs benefit from orthopedic beds.</p>"
        result = score_stats_attribution(html)
        self.assertEqual(result["unattributed_count"], 0,
                         f"'studies show' should count as attribution, got: {result}")

    def test_attribution_does_not_bleed_across_paragraphs(self):
        html = "<p>75% of dogs suffer joint pain.</p><p>According to AKC, this is common.</p>"
        result = score_stats_attribution(html)
        self.assertEqual(result["unattributed_count"], 1,
                         f"Cross-paragraph bleed: attribution in P2 should not credit stat in P1, got: {result}")

    def test_no_stats_rate_is_one(self):
        result = score_stats_attribution("<p>Dogs are great pets.</p>")
        self.assertEqual(result["attribution_rate"], 1.0)
        self.assertEqual(result["total_stats"], 0)
