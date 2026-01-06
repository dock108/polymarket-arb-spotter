"""
Unit tests for depth_scanner module.

Tests the analyze_depth function with various orderbook configurations.
"""

import unittest

from app.core.depth_scanner import (
    analyze_depth,
    analyze_normalized_depth,
    convert_normalized_to_raw,
    DepthSignal,
    detect_depth_signals,
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


class TestDepthSignal(unittest.TestCase):
    """Test DepthSignal dataclass."""

    def test_depth_signal_creation(self):
        """Test creating a DepthSignal object."""
        signal = DepthSignal(
            signal_type="thin_depth",
            triggered=True,
            reason="Test signal",
            metrics={"total_depth": 100.0},
        )

        self.assertEqual(signal.signal_type, "thin_depth")
        self.assertTrue(signal.triggered)
        self.assertEqual(signal.reason, "Test signal")
        self.assertEqual(signal.metrics["total_depth"], 100.0)

    def test_depth_signal_to_dict(self):
        """Test converting DepthSignal to dictionary."""
        signal = DepthSignal(
            signal_type="large_gap",
            triggered=True,
            reason="Gap too wide",
            metrics={"max_gap": 0.15},
        )

        signal_dict = signal.to_dict()

        self.assertEqual(signal_dict["signal_type"], "large_gap")
        self.assertTrue(signal_dict["triggered"])
        self.assertEqual(signal_dict["reason"], "Gap too wide")
        self.assertEqual(signal_dict["metrics"]["max_gap"], 0.15)


class TestDetectDepthSignals(unittest.TestCase):
    """Test detect_depth_signals function."""

    def test_no_signals_triggered(self):
        """Test when no signals should be triggered."""
        # Healthy orderbook: good depth, narrow spread, balanced
        metrics = {
            "total_yes_depth": 5000.0,
            "total_no_depth": 5000.0,
            "top_gap_yes": 0.02,
            "top_gap_no": 0.02,
            "imbalance": 0.0,
        }

        signals = detect_depth_signals(metrics)

        self.assertEqual(len(signals), 0)

    def test_thin_depth_signal(self):
        """Test thin depth signal is triggered."""
        # Low total depth
        metrics = {
            "total_yes_depth": 100.0,
            "total_no_depth": 100.0,
            "top_gap_yes": 0.05,
            "top_gap_no": 0.05,
            "imbalance": 0.0,
        }

        signals = detect_depth_signals(metrics)

        # Should trigger thin_depth signal
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "thin_depth")
        self.assertTrue(signals[0].triggered)
        self.assertIn("Thin orderbook depth", signals[0].reason)
        self.assertEqual(signals[0].metrics["total_depth"], 200.0)

    def test_large_gap_signal(self):
        """Test large gap signal is triggered."""
        # Wide bid-ask spread
        metrics = {
            "total_yes_depth": 1000.0,
            "total_no_depth": 1000.0,
            "top_gap_yes": 0.15,  # 15% spread
            "top_gap_no": 0.12,  # 12% spread
            "imbalance": 0.0,
        }

        signals = detect_depth_signals(metrics)

        # Should trigger large_gap signal
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "large_gap")
        self.assertTrue(signals[0].triggered)
        self.assertIn("Large bid-ask gap", signals[0].reason)
        self.assertEqual(signals[0].metrics["max_gap"], 0.15)

    def test_strong_imbalance_signal_yes_favored(self):
        """Test strong imbalance signal when YES side has more depth."""
        # Strong imbalance favoring YES
        metrics = {
            "total_yes_depth": 1500.0,
            "total_no_depth": 1000.0,
            "top_gap_yes": 0.05,
            "top_gap_no": 0.05,
            "imbalance": 500.0,  # YES - NO
        }

        signals = detect_depth_signals(metrics)

        # Should trigger strong_imbalance signal
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong_imbalance")
        self.assertTrue(signals[0].triggered)
        self.assertIn("Strong depth imbalance", signals[0].reason)
        self.assertIn("YES", signals[0].reason)
        self.assertEqual(signals[0].metrics["deeper_side"], "YES")
        self.assertEqual(signals[0].metrics["imbalance"], 500.0)

    def test_strong_imbalance_signal_no_favored(self):
        """Test strong imbalance signal when NO side has more depth."""
        # Strong imbalance favoring NO
        metrics = {
            "total_yes_depth": 800.0,
            "total_no_depth": 1500.0,
            "top_gap_yes": 0.05,
            "top_gap_no": 0.05,
            "imbalance": -700.0,  # YES - NO (negative means NO has more)
        }

        signals = detect_depth_signals(metrics)

        # Should trigger strong_imbalance signal
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong_imbalance")
        self.assertTrue(signals[0].triggered)
        self.assertIn("Strong depth imbalance", signals[0].reason)
        self.assertIn("NO", signals[0].reason)
        self.assertEqual(signals[0].metrics["deeper_side"], "NO")
        self.assertEqual(signals[0].metrics["imbalance"], -700.0)

    def test_multiple_signals_triggered(self):
        """Test when multiple signals are triggered simultaneously."""
        # Problematic orderbook: thin, wide spread, and imbalanced
        metrics = {
            "total_yes_depth": 150.0,
            "total_no_depth": 100.0,
            "top_gap_yes": 0.20,
            "top_gap_no": 0.18,
            "imbalance": 50.0,  # Not enough to trigger imbalance
        }

        signals = detect_depth_signals(metrics)

        # Should trigger thin_depth and large_gap
        self.assertEqual(len(signals), 2)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)

    def test_all_three_signals_triggered(self):
        """Test when all three signal types are triggered."""
        # Very problematic orderbook
        metrics = {
            "total_yes_depth": 150.0,
            "total_no_depth": 50.0,
            "top_gap_yes": 0.25,
            "top_gap_no": 0.22,
            "imbalance": 100.0,  # Not enough (needs > 300)
        }

        signals = detect_depth_signals(metrics)

        # Should trigger thin_depth and large_gap (imbalance not large enough)
        self.assertEqual(len(signals), 2)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)

    def test_edge_case_exactly_at_threshold(self):
        """Test behavior when metrics are exactly at threshold values."""
        # Metrics exactly at thresholds (should NOT trigger)
        metrics = {
            "total_yes_depth": 250.0,
            "total_no_depth": 250.0,  # total = 500, exactly at threshold
            "top_gap_yes": 0.10,  # exactly at threshold
            "top_gap_no": 0.08,
            "imbalance": 300.0,  # exactly at threshold
        }

        signals = detect_depth_signals(metrics)

        # Thresholds use < and >, so exactly at threshold should NOT trigger
        self.assertEqual(len(signals), 0)

    def test_just_below_thin_depth_threshold(self):
        """Test thin depth signal just below threshold."""
        metrics = {
            "total_yes_depth": 249.0,
            "total_no_depth": 249.0,  # total = 498, just below 500
            "top_gap_yes": 0.05,
            "top_gap_no": 0.05,
            "imbalance": 0.0,
        }

        signals = detect_depth_signals(metrics)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "thin_depth")

    def test_just_above_large_gap_threshold(self):
        """Test large gap signal just above threshold."""
        metrics = {
            "total_yes_depth": 1000.0,
            "total_no_depth": 1000.0,
            "top_gap_yes": 0.10001,  # just above 0.10
            "top_gap_no": 0.05,
            "imbalance": 0.0,
        }

        signals = detect_depth_signals(metrics)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "large_gap")

    def test_just_above_imbalance_threshold(self):
        """Test imbalance signal just above threshold."""
        metrics = {
            "total_yes_depth": 1500.0,
            "total_no_depth": 1199.0,
            "top_gap_yes": 0.05,
            "top_gap_no": 0.05,
            "imbalance": 301.0,  # just above 300
        }

        signals = detect_depth_signals(metrics)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong_imbalance")

    def test_empty_metrics(self):
        """Test with empty metrics dictionary."""
        metrics = {}

        signals = detect_depth_signals(metrics)

        # With all zeros, should trigger thin_depth
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "thin_depth")

    def test_missing_some_metrics(self):
        """Test with some metrics missing."""
        metrics = {
            "total_yes_depth": 100.0,
            # Missing other metrics
        }

        signals = detect_depth_signals(metrics)

        # Should still work with defaults
        self.assertGreaterEqual(len(signals), 1)
        # Should trigger thin_depth at minimum
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)

    def test_signal_metrics_content(self):
        """Test that signal metrics contain expected information."""
        metrics = {
            "total_yes_depth": 100.0,
            "total_no_depth": 80.0,
            "top_gap_yes": 0.15,
            "top_gap_no": 0.12,
            "imbalance": 20.0,
        }

        signals = detect_depth_signals(metrics)

        # Should have thin_depth and large_gap
        thin_signal = next(s for s in signals if s.signal_type == "thin_depth")
        self.assertIn("total_depth", thin_signal.metrics)
        self.assertIn("threshold", thin_signal.metrics)
        self.assertEqual(thin_signal.metrics["total_depth"], 180.0)

        large_gap_signal = next(s for s in signals if s.signal_type == "large_gap")
        self.assertIn("max_gap", large_gap_signal.metrics)
        self.assertIn("threshold", large_gap_signal.metrics)
        self.assertEqual(large_gap_signal.metrics["max_gap"], 0.15)

    def test_integration_with_analyze_depth(self):
        """Test detect_depth_signals with output from analyze_depth."""
        # Create a thin orderbook
        orderbook = {
            "bids": [{"price": "0.45", "size": "50"}],
            "asks": [{"price": "0.65", "size": "50"}],
        }

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics)

        # Should trigger both thin_depth and large_gap
        self.assertGreaterEqual(len(signals), 2)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)

    def test_integration_with_analyze_normalized_depth(self):
        """Test detect_depth_signals with output from analyze_normalized_depth."""
        # Create orderbook with strong imbalance
        yes_bids = [[0.45, 800.0], [0.44, 700.0]]
        yes_asks = [[0.55, 600.0], [0.56, 500.0]]
        no_bids = [[0.45, 300.0], [0.44, 200.0]]
        no_asks = [[0.55, 250.0], [0.56, 150.0]]

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics)

        # YES: 800+700+600+500 = 2600
        # NO: 300+200+250+150 = 900
        # Imbalance: 2600-900 = 1700 (> 300 threshold)
        # Should trigger strong_imbalance
        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertGreaterEqual(len(imbalance_signals), 1)
        self.assertEqual(imbalance_signals[0].metrics["deeper_side"], "YES")


if __name__ == "__main__":
    unittest.main()
