"""
Unit tests for analyzer and signal rules using mocked orderbooks.

Tests the full pipeline: mocked orderbook -> analyze_depth/analyze_normalized_depth -> detect_depth_signals
Covers thin depth, gaps, imbalance, and no-signal cases.
"""

import unittest
from typing import Dict, Any, List

from app.core.depth_scanner import (
    analyze_depth,
    analyze_normalized_depth,
    detect_depth_signals,
    DepthSignal,
)


def create_mock_orderbook(bids: List[tuple], asks: List[tuple]) -> Dict[str, Any]:
    """
    Create a mock orderbook from price/size tuples.

    Args:
        bids: List of (price, size) tuples for bids
        asks: List of (price, size) tuples for asks

    Returns:
        Dictionary in raw orderbook format
    """
    return {
        "bids": [{"price": str(price), "size": str(size)} for price, size in bids],
        "asks": [{"price": str(price), "size": str(size)} for price, size in asks],
    }


def create_mock_normalized_orderbook(
    yes_bids: List[tuple],
    yes_asks: List[tuple],
    no_bids: List[tuple],
    no_asks: List[tuple],
) -> tuple:
    """
    Create mock normalized orderbook lists.

    Args:
        yes_bids: List of (price, size) tuples for YES bids
        yes_asks: List of (price, size) tuples for YES asks
        no_bids: List of (price, size) tuples for NO bids
        no_asks: List of (price, size) tuples for NO asks

    Returns:
        Tuple of (yes_bids, yes_asks, no_bids, no_asks) as lists of [price, size]
    """
    return (
        [[price, size] for price, size in yes_bids],
        [[price, size] for price, size in yes_asks],
        [[price, size] for price, size in no_bids],
        [[price, size] for price, size in no_asks],
    )


# Default test configuration matching depth_scanner defaults
DEFAULT_TEST_CONFIG = {
    "min_depth": 500.0,
    "max_gap": 0.10,
    "imbalance_ratio": 300.0,
}


class TestThinDepthWithMockedOrderbook(unittest.TestCase):
    """Test thin depth signal detection using mocked orderbooks."""

    def test_very_thin_depth_single_level(self):
        """Test thin depth with single level orderbook having minimal liquidity."""
        orderbook = create_mock_orderbook(
            bids=[(0.45, 25)],
            asks=[(0.55, 25)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # total_yes_depth = 25 + 25 = 50, total_no_depth = 50 (binary market)
        # Total depth for threshold check = 50 + 50 = 100 (< 500 threshold)
        self.assertEqual(metrics["total_yes_depth"], 50.0)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)
        self.assertIn("Thin orderbook depth", thin_signals[0].reason)
        self.assertEqual(thin_signals[0].metrics["total_depth"], 100.0)

    def test_thin_depth_multiple_levels(self):
        """Test thin depth with multiple levels but still below threshold."""
        orderbook = create_mock_orderbook(
            bids=[(0.45, 40), (0.44, 30), (0.43, 20)],
            asks=[(0.55, 50), (0.56, 40), (0.57, 30)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # total_yes_depth = 40+30+20+50+40+30 = 210, total_no_depth = 210
        # Total depth for threshold check = 210 + 210 = 420 (< 500 threshold)
        self.assertEqual(metrics["total_yes_depth"], 210.0)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)
        self.assertEqual(thin_signals[0].metrics["total_depth"], 420.0)

    def test_thin_depth_normalized_orderbook(self):
        """Test thin depth using normalized orderbook format."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 30.0), (0.44, 20.0)],
            yes_asks=[(0.55, 40.0), (0.56, 30.0)],
            no_bids=[(0.55, 40.0), (0.54, 30.0)],
            no_asks=[(0.45, 30.0), (0.46, 20.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 30+20+40+30 = 120, NO depth = 40+30+30+20 = 120
        self.assertEqual(metrics["total_yes_depth"], 120.0)
        self.assertEqual(metrics["total_no_depth"], 120.0)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)
        # Total depth for threshold check = 120 + 120 = 240
        self.assertEqual(thin_signals[0].metrics["total_depth"], 240.0)

    def test_thin_depth_boundary_just_below(self):
        """Test thin depth signal triggered just below threshold."""
        orderbook = create_mock_orderbook(
            bids=[(0.45, 124)],
            asks=[(0.55, 125)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # total_yes_depth = 124 + 125 = 249, total_no_depth = 249
        # Total depth for threshold check = 249 + 249 = 498 (< 500 threshold)
        self.assertEqual(metrics["total_yes_depth"], 249.0)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)

    def test_thin_depth_empty_orderbook(self):
        """Test thin depth signal for empty orderbook."""
        orderbook = create_mock_orderbook(bids=[], asks=[])

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        self.assertEqual(metrics["total_yes_depth"], 0.0)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)
        self.assertEqual(thin_signals[0].metrics["total_depth"], 0.0)


class TestLargeGapWithMockedOrderbook(unittest.TestCase):
    """Test large gap (bid-ask spread) signal detection using mocked orderbooks."""

    def test_large_gap_wide_spread(self):
        """Test large gap signal with wide bid-ask spread."""
        orderbook = create_mock_orderbook(
            bids=[(0.35, 500), (0.34, 400)],
            asks=[(0.65, 500), (0.66, 400)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Gap = 0.65 - 0.35 = 0.30 (> 0.10 threshold)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.30, places=6)
        gap_signals = [s for s in signals if s.signal_type == "large_gap"]
        self.assertEqual(len(gap_signals), 1)
        self.assertIn("Large bid-ask gap", gap_signals[0].reason)
        self.assertAlmostEqual(gap_signals[0].metrics["max_gap"], 0.30, places=6)

    def test_large_gap_extreme_spread(self):
        """Test large gap signal with extreme spread (very illiquid market)."""
        orderbook = create_mock_orderbook(
            bids=[(0.10, 1000)],
            asks=[(0.90, 1000)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Gap = 0.90 - 0.10 = 0.80 (extreme gap)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.80, places=6)
        gap_signals = [s for s in signals if s.signal_type == "large_gap"]
        self.assertEqual(len(gap_signals), 1)
        self.assertAlmostEqual(gap_signals[0].metrics["max_gap"], 0.80, places=6)

    def test_large_gap_normalized_orderbook(self):
        """Test large gap using normalized orderbook format."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.30, 500.0), (0.29, 400.0)],
            yes_asks=[(0.55, 500.0), (0.56, 400.0)],
            no_bids=[(0.45, 500.0), (0.44, 400.0)],
            no_asks=[(0.70, 500.0), (0.71, 400.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES gap = 0.55 - 0.30 = 0.25, NO gap = 0.70 - 0.45 = 0.25
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.25, places=6)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.25, places=6)
        gap_signals = [s for s in signals if s.signal_type == "large_gap"]
        self.assertEqual(len(gap_signals), 1)
        # Max gap should be 0.25
        self.assertAlmostEqual(gap_signals[0].metrics["max_gap"], 0.25, places=6)

    def test_large_gap_boundary_just_above(self):
        """Test large gap signal triggered just above threshold."""
        orderbook = create_mock_orderbook(
            bids=[(0.44, 500)],
            asks=[(0.5501, 500)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Gap = 0.5501 - 0.44 = 0.1101 (> 0.10 threshold)
        self.assertGreater(metrics["top_gap_yes"], 0.10)
        gap_signals = [s for s in signals if s.signal_type == "large_gap"]
        self.assertEqual(len(gap_signals), 1)

    def test_large_gap_with_deep_levels(self):
        """Test large gap with deep orderbook levels but wide spread."""
        orderbook = create_mock_orderbook(
            bids=[
                (0.30, 200),
                (0.29, 300),
                (0.28, 400),
                (0.27, 500),
            ],
            asks=[
                (0.60, 200),
                (0.61, 300),
                (0.62, 400),
                (0.63, 500),
            ],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Gap = 0.60 - 0.30 = 0.30 (> 0.10 threshold)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.30, places=6)
        # Total depth = 2800 (above threshold, so no thin depth signal)
        self.assertEqual(metrics["total_yes_depth"], 2800.0)
        gap_signals = [s for s in signals if s.signal_type == "large_gap"]
        self.assertEqual(len(gap_signals), 1)


class TestImbalanceWithMockedOrderbook(unittest.TestCase):
    """Test depth imbalance signal detection using mocked orderbooks."""

    def test_strong_imbalance_yes_favored(self):
        """Test strong imbalance signal when YES side has more depth."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 600.0), (0.44, 500.0)],
            yes_asks=[(0.55, 500.0), (0.56, 400.0)],
            no_bids=[(0.55, 200.0), (0.54, 150.0)],
            no_asks=[(0.45, 150.0), (0.46, 100.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 600+500+500+400 = 2000, NO depth = 200+150+150+100 = 600
        self.assertEqual(metrics["total_yes_depth"], 2000.0)
        self.assertEqual(metrics["total_no_depth"], 600.0)
        # Imbalance = 2000 - 600 = 1400 (> 300 threshold)
        self.assertEqual(metrics["imbalance"], 1400.0)

        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertEqual(len(imbalance_signals), 1)
        self.assertIn("YES", imbalance_signals[0].reason)
        self.assertEqual(imbalance_signals[0].metrics["deeper_side"], "YES")
        self.assertEqual(imbalance_signals[0].metrics["imbalance"], 1400.0)

    def test_strong_imbalance_no_favored(self):
        """Test strong imbalance signal when NO side has more depth."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 150.0), (0.44, 100.0)],
            yes_asks=[(0.55, 100.0), (0.56, 50.0)],
            no_bids=[(0.55, 600.0), (0.54, 500.0)],
            no_asks=[(0.45, 400.0), (0.46, 300.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 150+100+100+50 = 400, NO depth = 600+500+400+300 = 1800
        self.assertEqual(metrics["total_yes_depth"], 400.0)
        self.assertEqual(metrics["total_no_depth"], 1800.0)
        # Imbalance = 400 - 1800 = -1400 (negative, NO has more)
        self.assertEqual(metrics["imbalance"], -1400.0)

        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertEqual(len(imbalance_signals), 1)
        self.assertIn("NO", imbalance_signals[0].reason)
        self.assertEqual(imbalance_signals[0].metrics["deeper_side"], "NO")
        self.assertEqual(imbalance_signals[0].metrics["imbalance"], -1400.0)

    def test_imbalance_boundary_just_above(self):
        """Test imbalance signal triggered just above threshold."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 401.0)],
            yes_asks=[(0.55, 400.0)],
            no_bids=[(0.55, 250.0)],
            no_asks=[(0.45, 249.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 401 + 400 = 801, NO depth = 250 + 249 = 499
        self.assertEqual(metrics["total_yes_depth"], 801.0)
        self.assertEqual(metrics["total_no_depth"], 499.0)
        # Imbalance = 801 - 499 = 302 (> 300 threshold)
        self.assertEqual(metrics["imbalance"], 302.0)

        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertEqual(len(imbalance_signals), 1)

    def test_extreme_imbalance_one_side_only(self):
        """Test extreme imbalance when one side has almost no depth."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 1000.0), (0.44, 800.0)],
            yes_asks=[(0.55, 900.0), (0.56, 700.0)],
            no_bids=[(0.55, 10.0)],
            no_asks=[(0.45, 5.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 3400, NO depth = 15
        self.assertEqual(metrics["total_yes_depth"], 3400.0)
        self.assertEqual(metrics["total_no_depth"], 15.0)
        # Extreme imbalance = 3400 - 15 = 3385
        self.assertEqual(metrics["imbalance"], 3385.0)

        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertEqual(len(imbalance_signals), 1)
        self.assertEqual(imbalance_signals[0].metrics["deeper_side"], "YES")


class TestNoSignalWithMockedOrderbook(unittest.TestCase):
    """Test healthy orderbooks that should NOT trigger any signals."""

    def test_healthy_orderbook_no_signals(self):
        """Test healthy orderbook with good depth, tight spread, and balance."""
        orderbook = create_mock_orderbook(
            bids=[
                (0.48, 500),
                (0.47, 400),
                (0.46, 300),
            ],
            asks=[
                (0.52, 500),
                (0.53, 400),
                (0.54, 300),
            ],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Total depth = 2400 (> 500), Gap = 0.04 (< 0.10), Imbalance = 0
        self.assertEqual(metrics["total_yes_depth"], 2400.0)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.04, places=6)
        self.assertEqual(metrics["imbalance"], 0.0)
        self.assertEqual(len(signals), 0)

    def test_healthy_normalized_orderbook_no_signals(self):
        """Test healthy normalized orderbook without any signals."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.48, 400.0), (0.47, 300.0), (0.46, 200.0)],
            yes_asks=[(0.52, 400.0), (0.53, 300.0), (0.54, 200.0)],
            no_bids=[(0.48, 400.0), (0.47, 300.0), (0.46, 200.0)],
            no_asks=[(0.52, 400.0), (0.53, 300.0), (0.54, 200.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 1800, NO depth = 1800, total = 3600 (> 500)
        self.assertEqual(metrics["total_yes_depth"], 1800.0)
        self.assertEqual(metrics["total_no_depth"], 1800.0)
        # Gap = 0.04 (< 0.10)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.04, places=6)
        # Imbalance = 0 (< 300)
        self.assertEqual(metrics["imbalance"], 0.0)
        self.assertEqual(len(signals), 0)

    def test_exactly_at_threshold_no_signals(self):
        """Test metrics exactly at thresholds should NOT trigger signals."""
        # Use prices that result in exactly 0.10 gap without floating point issues
        # 0.50 - 0.40 = 0.10 exactly
        orderbook = create_mock_orderbook(
            bids=[(0.40, 250)],
            asks=[(0.50, 250)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Total depth = 500 (= threshold), Gap = 0.10 (= threshold)
        self.assertEqual(metrics["total_yes_depth"], 500.0)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.10, places=6)
        # All thresholds use strict inequality, so exactly at threshold should NOT trigger
        self.assertEqual(len(signals), 0)

    def test_deep_orderbook_tight_spread_no_signals(self):
        """Test very deep orderbook with tight spread."""
        orderbook = create_mock_orderbook(
            bids=[
                (0.495, 2000),
                (0.490, 1500),
                (0.485, 1000),
                (0.480, 800),
                (0.475, 600),
            ],
            asks=[
                (0.505, 2000),
                (0.510, 1500),
                (0.515, 1000),
                (0.520, 800),
                (0.525, 600),
            ],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Total depth = 11800 (very deep)
        self.assertEqual(metrics["total_yes_depth"], 11800.0)
        # Gap = 0.01 (very tight)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.01, places=6)
        self.assertEqual(len(signals), 0)

    def test_moderate_imbalance_below_threshold(self):
        """Test moderate imbalance that doesn't trigger signal."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 400.0), (0.44, 300.0)],
            yes_asks=[(0.55, 350.0), (0.56, 250.0)],
            no_bids=[(0.55, 300.0), (0.54, 250.0)],
            no_asks=[(0.45, 250.0), (0.46, 200.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 1300, NO depth = 1000
        self.assertEqual(metrics["total_yes_depth"], 1300.0)
        self.assertEqual(metrics["total_no_depth"], 1000.0)
        # Imbalance = 300 (= threshold, should NOT trigger)
        self.assertEqual(metrics["imbalance"], 300.0)
        # Total depth = 2300 (> 500), Gap = 0.10 (= threshold)
        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertEqual(len(imbalance_signals), 0)


class TestMultipleSignalsWithMockedOrderbook(unittest.TestCase):
    """Test scenarios where multiple signals are triggered simultaneously."""

    def test_thin_depth_and_large_gap(self):
        """Test both thin depth and large gap signals triggered together."""
        orderbook = create_mock_orderbook(
            bids=[(0.30, 50)],
            asks=[(0.70, 50)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Total depth = 100 (< 500), Gap = 0.40 (> 0.10)
        self.assertEqual(metrics["total_yes_depth"], 100.0)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.40, places=6)

        self.assertEqual(len(signals), 2)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)

    def test_thin_depth_and_imbalance(self):
        """Test thin depth signal with moderate imbalance (below threshold)."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 100.0)],
            yes_asks=[(0.55, 100.0)],
            no_bids=[(0.55, 10.0)],
            no_asks=[(0.45, 10.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 200, NO depth = 20, Total = 220 (< 500)
        # Imbalance = 200 - 20 = 180 (< 300 threshold, so no imbalance signal)
        self.assertEqual(metrics["total_yes_depth"], 200.0)
        self.assertEqual(metrics["total_no_depth"], 20.0)
        # Only thin_depth triggers (imbalance below threshold)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)

    def test_thin_depth_and_large_gap_together(self):
        """Test thin depth and large gap signals (imbalance below threshold)."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.20, 50.0)],
            yes_asks=[(0.60, 50.0)],
            no_bids=[(0.40, 5.0)],
            no_asks=[(0.80, 5.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 100, NO depth = 10, Total = 110 (< 500) -> thin_depth
        self.assertEqual(metrics["total_yes_depth"], 100.0)
        self.assertEqual(metrics["total_no_depth"], 10.0)

        # YES gap = 0.60 - 0.20 = 0.40 (> 0.10) -> large_gap
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.40, places=6)
        # NO gap = 0.80 - 0.40 = 0.40 (> 0.10)
        self.assertAlmostEqual(metrics["top_gap_no"], 0.40, places=6)

        # Imbalance = 100 - 10 = 90 (< 300, no imbalance signal)
        # Should trigger thin_depth and large_gap only
        self.assertEqual(len(signals), 2)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)

    def test_all_signals_triggered_extreme_case(self):
        """Test extreme case where all three signals are triggered."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.10, 200.0)],
            yes_asks=[(0.90, 200.0)],
            no_bids=[(0.10, 1.0)],
            no_asks=[(0.90, 1.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 400, NO depth = 2, Total = 402 (< 500) -> thin_depth
        self.assertEqual(metrics["total_yes_depth"], 400.0)
        self.assertEqual(metrics["total_no_depth"], 2.0)

        # Gap = 0.90 - 0.10 = 0.80 (> 0.10) -> large_gap
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.80, places=6)

        # Imbalance = 400 - 2 = 398 (> 300) -> strong_imbalance
        self.assertEqual(metrics["imbalance"], 398.0)

        self.assertEqual(len(signals), 3)
        signal_types = {s.signal_type for s in signals}
        self.assertIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)
        self.assertIn("strong_imbalance", signal_types)

    def test_gap_and_imbalance_without_thin_depth(self):
        """Test large gap and imbalance without thin depth signal."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.30, 600.0), (0.29, 500.0)],
            yes_asks=[(0.70, 600.0), (0.71, 500.0)],
            no_bids=[(0.30, 100.0)],
            no_asks=[(0.70, 100.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 2200, NO depth = 200, Total = 2400 (> 500, no thin_depth)
        self.assertEqual(metrics["total_yes_depth"], 2200.0)
        self.assertEqual(metrics["total_no_depth"], 200.0)

        # Gap = 0.70 - 0.30 = 0.40 (> 0.10) -> large_gap
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.40, places=6)

        # Imbalance = 2200 - 200 = 2000 (> 300) -> strong_imbalance
        self.assertEqual(metrics["imbalance"], 2000.0)

        self.assertEqual(len(signals), 2)
        signal_types = {s.signal_type for s in signals}
        self.assertNotIn("thin_depth", signal_types)
        self.assertIn("large_gap", signal_types)
        self.assertIn("strong_imbalance", signal_types)


class TestSignalMetricsWithMockedOrderbook(unittest.TestCase):
    """Test that signal metrics contain accurate information."""

    def test_thin_depth_signal_metrics(self):
        """Test thin depth signal contains correct metrics."""
        orderbook = create_mock_orderbook(
            bids=[(0.45, 75)],
            asks=[(0.55, 85)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        thin_signal = next(s for s in signals if s.signal_type == "thin_depth")

        self.assertEqual(thin_signal.metrics["total_depth"], 320.0)
        self.assertEqual(thin_signal.metrics["threshold"], 500.0)
        self.assertEqual(thin_signal.metrics["total_yes_depth"], 160.0)
        self.assertEqual(thin_signal.metrics["total_no_depth"], 160.0)

    def test_large_gap_signal_metrics(self):
        """Test large gap signal contains correct metrics."""
        orderbook = create_mock_orderbook(
            bids=[(0.40, 500)],
            asks=[(0.60, 500)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        gap_signal = next(s for s in signals if s.signal_type == "large_gap")

        self.assertAlmostEqual(gap_signal.metrics["max_gap"], 0.20, places=6)
        self.assertEqual(gap_signal.metrics["threshold"], 0.10)
        self.assertAlmostEqual(gap_signal.metrics["top_gap_yes"], 0.20, places=6)
        self.assertAlmostEqual(gap_signal.metrics["top_gap_no"], 0.20, places=6)

    def test_imbalance_signal_metrics(self):
        """Test imbalance signal contains correct metrics."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 500.0)],
            yes_asks=[(0.55, 500.0)],
            no_bids=[(0.55, 100.0)],
            no_asks=[(0.45, 100.0)],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        imbalance_signal = next(
            s for s in signals if s.signal_type == "strong_imbalance"
        )

        self.assertEqual(imbalance_signal.metrics["imbalance"], 800.0)
        self.assertEqual(imbalance_signal.metrics["abs_imbalance"], 800.0)
        self.assertEqual(imbalance_signal.metrics["threshold"], 300.0)
        self.assertEqual(imbalance_signal.metrics["deeper_side"], "YES")
        self.assertEqual(imbalance_signal.metrics["total_yes_depth"], 1000.0)
        self.assertEqual(imbalance_signal.metrics["total_no_depth"], 200.0)


class TestEdgeCasesWithMockedOrderbook(unittest.TestCase):
    """Test edge cases and unusual orderbook configurations."""

    def test_orderbook_with_only_bids(self):
        """Test orderbook with only bid side."""
        orderbook = create_mock_orderbook(
            bids=[(0.45, 500), (0.44, 400)],
            asks=[],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # total_yes_depth = 500 + 400 = 900, total_no_depth = 900 (binary market)
        # Total depth for threshold = 900 + 900 = 1800 (> 500, no thin_depth)
        self.assertEqual(metrics["total_yes_depth"], 900.0)
        # Gap = 0 (no asks)
        self.assertEqual(metrics["top_gap_yes"], 0.0)

        # Should have no signals (depth OK, gap is 0)
        self.assertEqual(len(signals), 0)

    def test_orderbook_with_only_asks(self):
        """Test orderbook with only ask side."""
        orderbook = create_mock_orderbook(
            bids=[],
            asks=[(0.55, 500), (0.56, 400)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # total_yes_depth = 500 + 400 = 900, total_no_depth = 900 (binary market)
        self.assertEqual(metrics["total_yes_depth"], 900.0)
        self.assertEqual(metrics["top_gap_yes"], 0.0)

        # Should have no signals
        self.assertEqual(len(signals), 0)

    def test_orderbook_with_zero_size_levels(self):
        """Test orderbook with zero size levels mixed in."""
        orderbook = create_mock_orderbook(
            bids=[(0.45, 0), (0.44, 100), (0.43, 0)],
            asks=[(0.55, 0), (0.56, 100), (0.57, 0)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # total_yes_depth = 100 + 100 = 200, total_no_depth = 200 (binary market)
        # Total depth for threshold = 200 + 200 = 400 (< 500) -> thin_depth
        self.assertEqual(metrics["total_yes_depth"], 200.0)
        thin_signals = [s for s in signals if s.signal_type == "thin_depth"]
        self.assertEqual(len(thin_signals), 1)

    def test_normalized_orderbook_partial_empty(self):
        """Test normalized orderbook with some sides empty."""
        yes_bids, yes_asks, no_bids, no_asks = create_mock_normalized_orderbook(
            yes_bids=[(0.45, 500.0)],
            yes_asks=[(0.55, 500.0)],
            no_bids=[],
            no_asks=[],
        )

        metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # YES depth = 1000, NO depth = 0
        self.assertEqual(metrics["total_yes_depth"], 1000.0)
        self.assertEqual(metrics["total_no_depth"], 0.0)
        # Total = 1000 (> 500, no thin_depth)
        # Imbalance = 1000 (> 300) -> strong_imbalance
        imbalance_signals = [s for s in signals if s.signal_type == "strong_imbalance"]
        self.assertEqual(len(imbalance_signals), 1)
        self.assertEqual(imbalance_signals[0].metrics["deeper_side"], "YES")

    def test_small_price_increments(self):
        """Test orderbook with very small price increments."""
        orderbook = create_mock_orderbook(
            bids=[(0.4999, 500), (0.4998, 400)],
            asks=[(0.5001, 500), (0.5002, 400)],
        )

        metrics = analyze_depth(orderbook)
        signals = detect_depth_signals(metrics, DEFAULT_TEST_CONFIG)

        # Gap = 0.5001 - 0.4999 = 0.0002 (very tight)
        self.assertAlmostEqual(metrics["top_gap_yes"], 0.0002, places=6)
        # total_yes_depth = 500 + 400 + 500 + 400 = 1800, total_no_depth = 1800
        # Total depth for threshold = 1800 + 1800 = 3600 (> 500)
        self.assertEqual(metrics["total_yes_depth"], 1800.0)

        # No signals should be triggered
        self.assertEqual(len(signals), 0)


if __name__ == "__main__":
    unittest.main()
