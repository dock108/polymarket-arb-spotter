"""
Unit tests for exception handling and resilience features.
"""

import unittest
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.core.arb_detector import ArbitrageDetector, ArbitrageOpportunity
from app.core.logger import log_event, fetch_recent


class TestExceptionHandling(unittest.TestCase):
    """Test exception handling in critical functions."""

    def test_detect_opportunities_handles_malformed_market(self):
        """Test that detect_opportunities handles malformed market data gracefully."""
        detector = ArbitrageDetector(db_path=":memory:")

        # Mix of valid and malformed market data
        markets = [
            {
                "id": "market_1",
                "name": "Valid Market",
                "outcomes": [
                    {"name": "Yes", "price": 0.45},
                    {"name": "No", "price": 0.45},
                ],
            },
            {
                "id": "market_2",
                # Missing outcomes entirely
                "name": "Malformed Market",
            },
            {
                "id": "market_3",
                "name": "Another Valid Market",
                "outcomes": [
                    {"name": "Yes", "price": 0.40},
                    {"name": "No", "price": 0.40},
                ],
            },
        ]

        # Should not raise exception, should process valid markets
        opportunities = detector.detect_opportunities(markets)

        # Should find opportunities from valid markets
        self.assertGreater(len(opportunities), 0)

    def test_detect_opportunities_continues_after_individual_error(self):
        """Test that detect_opportunities continues processing after error in single market."""
        detector = ArbitrageDetector(db_path=":memory:")

        # Create markets where one will cause an error
        markets = [
            {
                "id": "market_1",
                "name": "Market 1",
                "outcomes": [
                    {"name": "Yes", "price": 0.45},
                    {"name": "No", "price": 0.45},
                ],
            },
            None,  # This will cause an error
            {
                "id": "market_3",
                "name": "Market 3",
                "outcomes": [
                    {"name": "Yes", "price": 0.40},
                    {"name": "No", "price": 0.40},
                ],
            },
        ]

        # Should handle the error and continue
        opportunities = detector.detect_opportunities(markets)

        # Should still find opportunities from valid markets
        self.assertGreater(len(opportunities), 0)

    def test_save_opportunity_handles_database_error(self):
        """Test that save_opportunity handles database errors gracefully."""
        detector = ArbitrageDetector(db_path=":memory:")

        # Create a valid opportunity
        opportunity = ArbitrageOpportunity(
            market_id="test_market",
            market_name="Test Market",
            opportunity_type="two-way",
            expected_profit=10.0,
            expected_return_pct=5.0,
            positions=[],
            detected_at=datetime.now(),
        )

        # Mock the connection to raise an error
        with patch.object(detector, "_conn", None):
            with patch("sqlite3.connect") as mock_connect:
                mock_connect.side_effect = sqlite3.OperationalError("Database locked")

                # Should not raise exception
                try:
                    detector.save_opportunity(opportunity)
                    # If we get here, the exception was handled
                    self.assertTrue(True)
                except Exception as e:
                    self.fail(f"save_opportunity raised unexpected exception: {e}")

    def test_get_recent_opportunities_handles_database_error(self):
        """Test that get_recent_opportunities handles database errors gracefully."""
        detector = ArbitrageDetector(db_path=":memory:")

        # Mock the connection to raise an error
        with patch.object(detector, "_conn", None):
            with patch("sqlite3.connect") as mock_connect:
                mock_connect.side_effect = sqlite3.OperationalError("Database error")

                # Should return empty list instead of raising
                result = detector.get_recent_opportunities()
                self.assertEqual(result, [])

    def test_log_event_handles_database_error(self):
        """Test that log_event handles database errors gracefully."""
        event_data = {
            "timestamp": datetime.now(),
            "market_id": "test_market",
            "market_name": "Test Market",
            "yes_price": 0.5,
            "no_price": 0.5,
            "sum": 1.0,
            "expected_profit_pct": 0.0,
            "mode": "test",
            "decision": "ignored",
            "mock_result": None,
            "failure_reason": None,
            "latency_ms": 10,
        }

        # Mock Database to raise an error
        with patch("app.core.logger.Database") as mock_db:
            mock_db.side_effect = Exception("Database error")

            # Should not raise exception
            try:
                log_event(event_data, db_path="/tmp/test.db")
                # If we get here, the exception was handled
                self.assertTrue(True)
            except Exception as e:
                self.fail(f"log_event raised unexpected exception: {e}")

    def test_fetch_recent_handles_missing_table(self):
        """Test that fetch_recent handles missing table gracefully."""
        # Use a temporary in-memory database
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        # Database exists but has no tables
        result = fetch_recent(limit=10, db_path=db_path)

        # Should return empty list, not raise exception
        self.assertEqual(result, [])

        # Clean up
        import os

        os.unlink(db_path)

    def test_fetch_recent_handles_database_error(self):
        """Test that fetch_recent handles database errors gracefully."""
        with patch("app.core.logger.Database") as mock_db:
            mock_db.side_effect = Exception("Database error")

            # Should return empty list instead of raising
            result = fetch_recent(limit=10, db_path="/tmp/nonexistent.db")
            self.assertEqual(result, [])


class TestRobustness(unittest.TestCase):
    """Test robustness under various conditions."""

    def test_detector_handles_empty_market_list(self):
        """Test that detector handles empty market list."""
        detector = ArbitrageDetector(db_path=":memory:")

        opportunities = detector.detect_opportunities([])

        self.assertEqual(len(opportunities), 0)

    def test_detector_handles_markets_without_prices(self):
        """Test that detector handles markets without price data."""
        detector = ArbitrageDetector(db_path=":memory:")

        markets = [{"id": "market_1", "name": "Market Without Prices", "outcomes": []}]

        # Should not crash
        opportunities = detector.detect_opportunities(markets)
        self.assertEqual(len(opportunities), 0)

    def test_save_opportunity_with_none_values(self):
        """Test that save_opportunity handles None values in optional fields."""
        detector = ArbitrageDetector(db_path=":memory:")

        opportunity = ArbitrageOpportunity(
            market_id="test",
            market_name="Test",
            opportunity_type="two-way",
            expected_profit=10.0,
            expected_return_pct=5.0,
            positions=[],
            detected_at=datetime.now(),
            expires_at=None,  # Optional field
            risk_score=0.0,
        )

        # Should save successfully
        detector.save_opportunity(opportunity)

        # Verify it was saved
        recent = detector.get_recent_opportunities(limit=1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["market_id"], "test")


class TestAPIRetryLogic(unittest.TestCase):
    """Test retry logic in API client."""

    @patch("requests.Session.request")
    def test_api_retries_on_transient_error(self, mock_request):
        """Test that API client retries on transient errors."""
        from app.core.api_client import PolymarketAPIClient
        import requests

        client = PolymarketAPIClient(max_retries=3, retry_delay=0.01)

        # Simulate transient error then success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_request.side_effect = [
            requests.exceptions.ConnectionError("Connection error"),
            mock_response,
        ]

        # Should succeed after retry
        result = client.fetch_markets(limit=10)

        # Should have retried once then succeeded
        self.assertEqual(mock_request.call_count, 2)

    @patch("requests.Session.request")
    def test_api_respects_max_retries(self, mock_request):
        """Test that API client respects max_retries setting."""
        from app.core.api_client import PolymarketAPIClient
        import requests

        client = PolymarketAPIClient(max_retries=2, retry_delay=0.01)

        # Simulate continuous failures
        mock_request.side_effect = requests.exceptions.ConnectionError(
            "Connection error"
        )

        # Should give up after max_retries
        result = client.fetch_markets(limit=10)

        # Should return empty list after exhausting retries
        self.assertEqual(result, [])
        self.assertEqual(mock_request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
