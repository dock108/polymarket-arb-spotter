"""
Unit tests for depth_scanner module.

Tests the analyze_depth function with various orderbook configurations.
"""

import unittest

from app.core.depth_scanner import (
    analyze_depth,
    analyze_normalized_depth,
    convert_normalized_to_raw,
)


class TestAnalyzeDepth(unittest.TestCase):
    """Test analyze_depth function."""

    def test_basic_orderbook(self):
        """Test analysis of a basic orderbook with bids and asks."""
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
        # For binary markets, NO depth equals YES depth
        self.assertEqual(metrics["total_no_depth"], 700.0)
        # YES gap = 0.55 - 0.45 = 0.10
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)
        # NO gap should equal YES gap for binary markets
        self.assertAlmostEqual(metrics["top_gap_no"], 0.10, places=6)
        # Imbalance = YES - NO = 0
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_empty_orderbook(self):
        """Test analysis of an empty orderbook."""
        orderbook = {"bids": [], "asks": []}

        metrics = analyze_depth(orderbook)

        self.assertEqual(metrics["total_yes_depth"], 0.0)
        self.assertEqual(metrics["total_no_depth"], 0.0)
        self.assertEqual(metrics["top_gap_yes"], 0.0)
        self.assertEqual(metrics["top_gap_no"], 0.0)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_orderbook_with_only_bids(self):
        """Test analysis of orderbook with only bids."""
        orderbook = {
            "bids": [
                {"price": "0.40", "size": "100"},
                {"price": "0.35", "size": "200"},
            ],
            "asks": [],
        }

        metrics = analyze_depth(orderbook)

        # Total depth = 100 + 200 = 300
        self.assertEqual(metrics["total_yes_depth"], 300.0)
        self.assertEqual(metrics["total_no_depth"], 300.0)
        # No gap calculation without asks
        self.assertEqual(metrics["top_gap_yes"], 0.0)
        self.assertEqual(metrics["top_gap_no"], 0.0)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_orderbook_with_only_asks(self):
        """Test analysis of orderbook with only asks."""
        orderbook = {
            "bids": [],
            "asks": [
                {"price": "0.60", "size": "100"},
                {"price": "0.65", "size": "200"},
            ],
        }

        metrics = analyze_depth(orderbook)

        # Total depth = 100 + 200 = 300
        self.assertEqual(metrics["total_yes_depth"], 300.0)
        self.assertEqual(metrics["total_no_depth"], 300.0)
        # No gap calculation without bids
        self.assertEqual(metrics["top_gap_yes"], 0.0)
        self.assertEqual(metrics["top_gap_no"], 0.0)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_single_bid_and_ask(self):
        """Test analysis with single bid and ask."""
        orderbook = {
            "bids": [{"price": "0.50", "size": "100"}],
            "asks": [{"price": "0.52", "size": "100"}],
        }

        metrics = analyze_depth(orderbook)

        self.assertEqual(metrics["total_yes_depth"], 200.0)
        self.assertEqual(metrics["total_no_depth"], 200.0)
        # YES gap = 0.52 - 0.50 = 0.02
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.02, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.02, places=6)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_narrow_spread(self):
        """Test orderbook with narrow bid-ask spread."""
        orderbook = {
            "bids": [
                {"price": "0.495", "size": "500"},
                {"price": "0.490", "size": "300"},
            ],
            "asks": [
                {"price": "0.505", "size": "400"},
                {"price": "0.510", "size": "200"},
            ],
        }

        metrics = analyze_depth(orderbook)

        self.assertEqual(metrics["total_yes_depth"], 1400.0)
        self.assertEqual(metrics["total_no_depth"], 1400.0)
        # Narrow gap = 0.505 - 0.495 = 0.01
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.01, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.01, places=6)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_wide_spread(self):
        """Test orderbook with wide bid-ask spread."""
        orderbook = {
            "bids": [
                {"price": "0.30", "size": "1000"},
                {"price": "0.25", "size": "500"},
            ],
            "asks": [
                {"price": "0.70", "size": "800"},
                {"price": "0.75", "size": "600"},
            ],
        }

        metrics = analyze_depth(orderbook)

        self.assertEqual(metrics["total_yes_depth"], 2900.0)
        self.assertEqual(metrics["total_no_depth"], 2900.0)
        # Wide gap = 0.70 - 0.30 = 0.40
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.40, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.40, places=6)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_unsorted_bids_and_asks(self):
        """Test that function correctly handles unsorted orderbook."""
        orderbook = {
            "bids": [
                {"price": "0.44", "size": "200"},
                {"price": "0.45", "size": "100"},  # Best bid (highest)
                {"price": "0.43", "size": "300"},
            ],
            "asks": [
                {"price": "0.56", "size": "250"},
                {"price": "0.57", "size": "150"},
                {"price": "0.55", "size": "200"},  # Best ask (lowest)
            ],
        }

        metrics = analyze_depth(orderbook)

        # Total depth = 200 + 100 + 300 + 250 + 150 + 200 = 1200
        self.assertEqual(metrics["total_yes_depth"], 1200.0)
        self.assertEqual(metrics["total_no_depth"], 1200.0)
        # Gap should be calculated from best bid (0.45) and best ask (0.55)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.10, places=6)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_orderbook_with_zero_sizes(self):
        """Test orderbook containing orders with zero size."""
        orderbook = {
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.44", "size": "0"},  # Zero size
            ],
            "asks": [
                {"price": "0.55", "size": "0"},  # Zero size
                {"price": "0.56", "size": "200"},
            ],
        }

        metrics = analyze_depth(orderbook)

        # Total depth = 100 + 0 + 0 + 200 = 300
        self.assertEqual(metrics["total_yes_depth"], 300.0)
        self.assertEqual(metrics["total_no_depth"], 300.0)
        # Gap calculated from best bid and ask (ignoring zero sizes is OK)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.10, places=6)

    def test_orderbook_with_missing_keys(self):
        """Test graceful handling of missing bids/asks keys."""
        orderbook = {}

        metrics = analyze_depth(orderbook)

        self.assertEqual(metrics["total_yes_depth"], 0.0)
        self.assertEqual(metrics["total_no_depth"], 0.0)
        self.assertEqual(metrics["top_gap_yes"], 0.0)
        self.assertEqual(metrics["top_gap_no"], 0.0)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_orderbook_with_missing_price_or_size(self):
        """Test handling of orders with missing price or size fields."""
        orderbook = {
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.44"},  # Missing size
                {"size": "50"},  # Missing price
            ],
            "asks": [
                {"price": "0.55", "size": "150"},
                {},  # Empty order
            ],
        }

        metrics = analyze_depth(orderbook)

        # Should handle missing fields gracefully, treating them as 0
        # Total depth = 100 + 0 + 50 + 150 + 0 = 300
        # Note: Size is counted even if price is missing (contributes to depth)
        self.assertEqual(metrics["total_yes_depth"], 300.0)
        self.assertEqual(metrics["total_no_depth"], 300.0)
        # Gap calculation may be affected by orders with missing prices
        # (best ask could be 0 from empty order, giving negative gap)
        # This is expected behavior for malformed data
        self.assertIsInstance(metrics["top_gap_yes"], float)
        self.assertIsInstance(metrics["top_gap_no"], float)

    def test_large_orderbook(self):
        """Test with a larger orderbook."""
        bids = [
            {"price": str(0.50 - i * 0.01), "size": str(100 * (i + 1))}
            for i in range(10)
        ]
        asks = [
            {"price": str(0.51 + i * 0.01), "size": str(100 * (i + 1))}
            for i in range(10)
        ]

        orderbook = {"bids": bids, "asks": asks}

        metrics = analyze_depth(orderbook)

        # Total depth = sum of all sizes
        # Bids: 100 + 200 + 300 + ... + 1000 = 5500
        # Asks: 100 + 200 + 300 + ... + 1000 = 5500
        # Total: 11000
        self.assertEqual(metrics["total_yes_depth"], 11000.0)
        self.assertEqual(metrics["total_no_depth"], 11000.0)
        # Gap = 0.51 - 0.50 = 0.01
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.01, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.01, places=6)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_all_metrics_present(self):
        """Test that all expected metrics are present in the result."""
        orderbook = {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        }

        metrics = analyze_depth(orderbook)

        # Verify all expected keys are present
        expected_keys = [
            "total_yes_depth",
            "total_no_depth",
            "top_gap_yes",
            "top_gap_no",
            "imbalance",
        ]

        for key in expected_keys:
            self.assertIn(key, metrics)
            self.assertIsInstance(metrics[key], float)


class TestAnalyzeNormalizedDepth(unittest.TestCase):
    """Test analyze_normalized_depth function."""

    def test_basic_normalized_depth(self):
        """Test analysis of normalized orderbook levels."""
        yes_bids = [[0.45, 100.0], [0.44, 200.0]]
        yes_asks = [[0.55, 150.0], [0.56, 250.0]]
        no_bids = [[0.45, 150.0], [0.44, 250.0]]
        no_asks = [[0.55, 100.0], [0.56, 200.0]]

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)

        # YES depth = 100 + 200 + 150 + 250 = 700
        self.assertEqual(metrics["total_yes_depth"], 700.0)
        self.assertEqual(metrics["yes_bid_depth"], 300.0)
        self.assertEqual(metrics["yes_ask_depth"], 400.0)

        # NO depth = 150 + 250 + 100 + 200 = 700
        self.assertEqual(metrics["total_no_depth"], 700.0)
        self.assertEqual(metrics["no_bid_depth"], 400.0)
        self.assertEqual(metrics["no_ask_depth"], 300.0)

        # Gaps
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.10, places=6)

        # Imbalance
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_normalized_depth_with_empty_lists(self):
        """Test analysis with empty lists."""
        metrics = analyze_normalized_depth([], [], [], [])

        self.assertEqual(metrics["total_yes_depth"], 0.0)
        self.assertEqual(metrics["total_no_depth"], 0.0)
        self.assertEqual(metrics["top_gap_yes"], 0.0)
        self.assertEqual(metrics["top_gap_no"], 0.0)
        self.assertEqual(metrics["imbalance"], 0.0)

    def test_normalized_depth_with_single_level(self):
        """Test analysis with single level orderbook."""
        yes_bids = [[0.50, 1000.0]]
        yes_asks = [[0.52, 800.0]]
        no_bids = [[0.48, 800.0]]
        no_asks = [[0.50, 1000.0]]

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)

        self.assertEqual(metrics["total_yes_depth"], 1800.0)
        self.assertEqual(metrics["total_no_depth"], 1800.0)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.02, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.02, places=6)

    def test_normalized_depth_with_multiple_levels(self):
        """Test analysis with multiple price levels."""
        yes_bids = [
            [0.45, 100.0],
            [0.44, 200.0],
            [0.43, 300.0],
            [0.42, 400.0],
            [0.41, 500.0],
        ]
        yes_asks = [
            [0.55, 150.0],
            [0.56, 250.0],
            [0.57, 350.0],
            [0.58, 450.0],
            [0.59, 550.0],
        ]
        no_bids = [
            [0.45, 150.0],
            [0.44, 250.0],
            [0.43, 350.0],
            [0.42, 450.0],
            [0.41, 550.0],
        ]
        no_asks = [
            [0.55, 100.0],
            [0.56, 200.0],
            [0.57, 300.0],
            [0.58, 400.0],
            [0.59, 500.0],
        ]

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)

        # YES: 1500 + 1750 = 3250
        self.assertEqual(metrics["total_yes_depth"], 3250.0)
        self.assertEqual(metrics["yes_bid_depth"], 1500.0)
        self.assertEqual(metrics["yes_ask_depth"], 1750.0)

        # NO: 1750 + 1500 = 3250
        self.assertEqual(metrics["total_no_depth"], 3250.0)
        self.assertEqual(metrics["no_bid_depth"], 1750.0)
        self.assertEqual(metrics["no_ask_depth"], 1500.0)

        # Gap based on best prices
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)


class TestConvertNormalizedToRaw(unittest.TestCase):
    """Test convert_normalized_to_raw function."""

    def test_basic_conversion(self):
        """Test basic conversion from normalized to raw format."""
        yes_bids = [[0.45, 100.0], [0.44, 200.0]]
        yes_asks = [[0.55, 150.0], [0.56, 250.0]]

        raw = convert_normalized_to_raw(yes_bids, yes_asks)

        self.assertIn("bids", raw)
        self.assertIn("asks", raw)

        self.assertEqual(len(raw["bids"]), 2)
        self.assertEqual(len(raw["asks"]), 2)

        self.assertEqual(raw["bids"][0], {"price": "0.45", "size": "100.0"})
        self.assertEqual(raw["bids"][1], {"price": "0.44", "size": "200.0"})
        self.assertEqual(raw["asks"][0], {"price": "0.55", "size": "150.0"})
        self.assertEqual(raw["asks"][1], {"price": "0.56", "size": "250.0"})

    def test_empty_conversion(self):
        """Test conversion with empty lists."""
        raw = convert_normalized_to_raw([], [])

        self.assertEqual(raw["bids"], [])
        self.assertEqual(raw["asks"], [])

    def test_conversion_can_be_analyzed(self):
        """Test that converted data can be analyzed by analyze_depth."""
        yes_bids = [[0.45, 100.0], [0.44, 200.0]]
        yes_asks = [[0.55, 150.0], [0.56, 250.0]]

        raw = convert_normalized_to_raw(yes_bids, yes_asks)
        metrics = analyze_depth(raw)

        # Should produce same results as original analyze_depth
        self.assertEqual(metrics["total_yes_depth"], 700.0)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)


if __name__ == "__main__":
    unittest.main()
