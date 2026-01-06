"""
Unit tests for depth_view module.

Tests the depth view rendering functions and helper utilities.
"""

import unittest

from app.ui.depth_view import (
    _get_sample_orderbooks,
)
from app.core.depth_scanner import (
    analyze_depth,
    detect_depth_signals,
    DEFAULT_CONFIG,
)


class TestDepthViewHelpers(unittest.TestCase):
    """Test depth view helper functions."""

    def test_get_sample_orderbooks_returns_dict(self):
        """Test that _get_sample_orderbooks returns a dictionary."""
        result = _get_sample_orderbooks()
        self.assertIsInstance(result, dict)

    def test_get_sample_orderbooks_has_markets(self):
        """Test that sample orderbooks contain market data."""
        result = _get_sample_orderbooks()
        self.assertGreater(len(result), 0)

    def test_sample_orderbooks_have_valid_structure(self):
        """Test that sample orderbooks have valid bids and asks."""
        result = _get_sample_orderbooks()

        for market_id, orderbook in result.items():
            self.assertIn("bids", orderbook)
            self.assertIn("asks", orderbook)
            self.assertIsInstance(orderbook["bids"], list)
            self.assertIsInstance(orderbook["asks"], list)

    def test_sample_orderbooks_can_be_analyzed(self):
        """Test that sample orderbooks can be analyzed with analyze_depth."""
        result = _get_sample_orderbooks()

        for market_id, orderbook in result.items():
            metrics = analyze_depth(orderbook)

            # Verify metrics are returned
            self.assertIn("total_yes_depth", metrics)
            self.assertIn("total_no_depth", metrics)
            self.assertIn("top_gap_yes", metrics)
            self.assertIn("top_gap_no", metrics)
            self.assertIn("imbalance", metrics)

            # Verify values are floats
            for key, value in metrics.items():
                self.assertIsInstance(value, float)

    def test_sample_orderbooks_detect_signals(self):
        """Test that sample orderbooks can generate depth signals."""
        result = _get_sample_orderbooks()

        # At least one sample should trigger signals
        signals_found = False

        for market_id, orderbook in result.items():
            metrics = analyze_depth(orderbook)
            signals = detect_depth_signals(metrics, config=DEFAULT_CONFIG)

            if signals:
                signals_found = True
                for signal in signals:
                    self.assertIn(
                        signal.signal_type,
                        ["thin_depth", "large_gap", "strong_imbalance"],
                    )
                    self.assertTrue(signal.triggered)
                    self.assertIsInstance(signal.reason, str)
                    self.assertIsInstance(signal.metrics, dict)

        # Sample data includes thin market, so signals should be found
        self.assertTrue(
            signals_found, "Expected at least one sample market to trigger signals"
        )


class TestDepthViewIntegration(unittest.TestCase):
    """Test depth view integration with depth scanner."""

    def test_thin_market_detection(self):
        """Test that thin markets are properly detected."""
        thin_orderbook = {
            "bids": [{"price": "0.48", "size": "50"}],
            "asks": [{"price": "0.72", "size": "40"}],
        }

        metrics = analyze_depth(thin_orderbook)
        signals = detect_depth_signals(metrics, config=DEFAULT_CONFIG)

        # Should detect thin depth and large gap
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)

    def test_healthy_market_no_signals(self):
        """Test that healthy markets don't trigger signals."""
        healthy_orderbook = {
            "bids": [
                {"price": "0.50", "size": "500"},
                {"price": "0.49", "size": "600"},
                {"price": "0.48", "size": "700"},
            ],
            "asks": [
                {"price": "0.52", "size": "450"},
                {"price": "0.53", "size": "550"},
                {"price": "0.54", "size": "650"},
            ],
        }

        metrics = analyze_depth(healthy_orderbook)
        signals = detect_depth_signals(metrics, config=DEFAULT_CONFIG)

        # Healthy market should not trigger signals
        self.assertEqual(len(signals), 0)

    def test_custom_thresholds(self):
        """Test that custom thresholds affect signal detection."""
        # Create an orderbook with total depth of 200 (50+50+50+50)
        # YES depth = 100, NO depth = 100, total = 200 (below 500 threshold)
        orderbook = {
            "bids": [
                {"price": "0.45", "size": "50"},
                {"price": "0.44", "size": "50"},
            ],
            "asks": [
                {"price": "0.55", "size": "50"},
                {"price": "0.56", "size": "50"},
            ],
        }

        metrics = analyze_depth(orderbook)

        # With default thresholds (min_depth=500), total depth of 400 (200*2)
        # should trigger thin_depth
        default_signals = detect_depth_signals(metrics, config=DEFAULT_CONFIG)
        default_types = {s.signal_type for s in default_signals}
        self.assertIn("thin_depth", default_types)

        # With lower threshold, should not trigger thin_depth
        custom_config = {
            "min_depth": 100.0,  # Lower threshold
            "max_gap": 0.20,  # Higher threshold
            "imbalance_ratio": 1000.0,  # Higher threshold
            "markets_to_watch": [],
        }
        custom_signals = detect_depth_signals(metrics, config=custom_config)
        self.assertEqual(len(custom_signals), 0)


class TestDepthMetricsCalculation(unittest.TestCase):
    """Test depth metrics calculations used in the view."""

    def test_total_depth_calculation(self):
        """Test that total depth is calculated correctly."""
        orderbook = {
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.44", "size": "200"},
            ],
            "asks": [
                {"price": "0.55", "size": "150"},
                {"price": "0.56", "size": "250"},
            ],
        }

        metrics = analyze_depth(orderbook)

        # Total YES depth = 100 + 200 + 150 + 250 = 700
        self.assertEqual(metrics["total_yes_depth"], 700.0)

    def test_gap_calculation(self):
        """Test that bid-ask gap is calculated correctly."""
        orderbook = {
            "bids": [{"price": "0.40", "size": "100"}],
            "asks": [{"price": "0.60", "size": "100"}],
        }

        metrics = analyze_depth(orderbook)

        # Gap = 0.60 - 0.40 = 0.20
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.20, places=6)

    def test_imbalance_calculation(self):
        """Test that imbalance is calculated correctly."""
        orderbook = {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        }

        metrics = analyze_depth(orderbook)

        # For binary markets with same orderbook, imbalance should be 0
        self.assertEqual(metrics["imbalance"], 0.0)


class TestDepthConfigIntegration(unittest.TestCase):
    """Test depth config integration with the view."""

    def test_default_config_values(self):
        """Test that default config has expected values."""
        self.assertIn("min_depth", DEFAULT_CONFIG)
        self.assertIn("max_gap", DEFAULT_CONFIG)
        self.assertIn("imbalance_ratio", DEFAULT_CONFIG)
        self.assertIn("markets_to_watch", DEFAULT_CONFIG)

        self.assertEqual(DEFAULT_CONFIG["min_depth"], 500.0)
        self.assertEqual(DEFAULT_CONFIG["max_gap"], 0.10)
        self.assertEqual(DEFAULT_CONFIG["imbalance_ratio"], 300.0)
        self.assertIsInstance(DEFAULT_CONFIG["markets_to_watch"], list)

    def test_config_affects_signals(self):
        """Test that config values affect signal detection."""
        # Metrics right at the boundary
        metrics = {
            "total_yes_depth": 250.0,
            "total_no_depth": 250.0,  # Total = 500
            "top_gap_yes": 0.10,  # At threshold
            "top_gap_no": 0.10,
            "imbalance": 0.0,
        }

        # With default config (min_depth=500), total depth of 500 should NOT trigger
        signals = detect_depth_signals(metrics, config=DEFAULT_CONFIG)
        signal_types = {s.signal_type for s in signals}
        self.assertNotIn("thin_depth", signal_types)

        # With slightly higher min_depth, should trigger
        stricter_config = DEFAULT_CONFIG.copy()
        stricter_config["min_depth"] = 501.0
        signals = detect_depth_signals(metrics, config=stricter_config)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)


if __name__ == "__main__":
    unittest.main()
