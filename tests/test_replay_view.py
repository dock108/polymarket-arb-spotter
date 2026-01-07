"""
Unit tests for replay_view module.

Tests the replay view helper functions and database operations.
"""

import unittest
from datetime import datetime, timedelta

from app.ui.replay_view import LABEL_TYPES
from app.core.logger import (
    init_db,
    save_history_label,
    fetch_history_labels,
    delete_history_label,
)


class TestReplayViewConstants(unittest.TestCase):
    """Test replay view constants."""

    def test_label_types_defined(self):
        """Test that LABEL_TYPES is defined and contains expected labels."""
        self.assertIsInstance(LABEL_TYPES, list)
        self.assertGreater(len(LABEL_TYPES), 0)

        # Check for expected label types
        expected_labels = [
            "news-driven move",
            "whale entry",
            "arb collapse",
            "false signal",
        ]
        for label in expected_labels:
            self.assertIn(label, LABEL_TYPES)


class TestHistoryLabels(unittest.TestCase):
    """Test history label database operations."""

    @classmethod
    def setUpClass(cls):
        """Initialize database once for all tests."""
        init_db()

    def test_save_and_fetch_label(self):
        """Test saving and fetching a label."""
        test_market = "test_market_unittest"
        test_timestamp = datetime.now()

        label_data = {
            "timestamp": test_timestamp,
            "market_id": test_market,
            "label_type": "whale entry",
            "notes": "Test label for unit test",
        }

        # Save label
        save_history_label(label_data)

        # Fetch labels
        labels = fetch_history_labels(market_id=test_market, limit=10)

        # Verify label was saved
        self.assertGreater(len(labels), 0)

        # Verify label content
        saved_label = labels[0]
        self.assertEqual(saved_label["market_id"], test_market)
        self.assertEqual(saved_label["label_type"], "whale entry")
        self.assertEqual(saved_label["notes"], "Test label for unit test")

    def test_fetch_labels_with_date_range(self):
        """Test fetching labels with date range filtering."""
        test_market = "test_market_date_range"
        base_time = datetime.now()

        # Create labels at different times
        label1 = {
            "timestamp": base_time - timedelta(days=2),
            "market_id": test_market,
            "label_type": "news-driven move",
            "notes": "Old label",
        }
        label2 = {
            "timestamp": base_time,
            "market_id": test_market,
            "label_type": "whale entry",
            "notes": "Recent label",
        }

        save_history_label(label1)
        save_history_label(label2)

        # Fetch only recent labels
        start = (base_time - timedelta(days=1)).isoformat()
        labels = fetch_history_labels(market_id=test_market, start=start, limit=10)

        # Should only get the recent label
        self.assertGreaterEqual(len(labels), 1)

        # Verify we got the recent label
        label_types = [label["label_type"] for label in labels]
        self.assertIn("whale entry", label_types)

    def test_delete_label(self):
        """Test deleting a label."""
        test_market = "test_market_delete"

        label_data = {
            "timestamp": datetime.now(),
            "market_id": test_market,
            "label_type": "false signal",
            "notes": "To be deleted",
        }

        # Save label
        save_history_label(label_data)

        # Fetch to get ID
        labels = fetch_history_labels(market_id=test_market, limit=1)
        self.assertGreater(len(labels), 0)

        label_id = labels[0]["id"]

        # Delete label
        result = delete_history_label(label_id)
        self.assertTrue(result)

        # Verify deletion
        labels_after = fetch_history_labels(market_id=test_market, limit=10)
        # The label should be gone (or at least one less than before)
        remaining_ids = [label["id"] for label in labels_after]
        self.assertNotIn(label_id, remaining_ids)


if __name__ == "__main__":
    unittest.main()
