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
    score_stats_attribution = None
    validate_quick_answer_box = None
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
