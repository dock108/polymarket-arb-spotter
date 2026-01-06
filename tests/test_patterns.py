"""
Unit tests for event correlation analyzer module.

Tests pattern analysis, signal outcome computation, and statistics aggregation.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from app.core.patterns import (
    EventCorrelationAnalyzer,
    PatternStatistics,
    SignalOutcome,
    CorrelationSummary,
    create_analyzer,
)
from app.core.history_store import append_ticks
from app.core.logger import save_history_label


class TestPatternDataClasses(unittest.TestCase):
    """Test pattern analysis data classes."""

    def test_pattern_statistics_to_dict(self):
        """Test PatternStatistics conversion to dictionary."""
        stats = PatternStatistics(
            pattern_type="whale entry",
            total_occurrences=10,
            avg_price_move=0.05,
            avg_time_to_resolution_minutes=15.5,
            positive_outcome_rate=0.7,
            false_positive_rate=0.1,
            avg_volume_change=500.0,
            sample_timestamps=["2024-01-01T12:00:00", "2024-01-02T13:00:00"],
        )

        result = stats.to_dict()

        self.assertEqual(result["pattern_type"], "whale entry")
        self.assertEqual(result["total_occurrences"], 10)
        self.assertEqual(result["avg_price_move"], 0.05)
        self.assertEqual(result["avg_time_to_resolution_minutes"], 15.5)
        self.assertEqual(result["positive_outcome_rate"], 0.7)
        self.assertEqual(result["false_positive_rate"], 0.1)
        self.assertEqual(result["avg_volume_change"], 500.0)
        self.assertEqual(len(result["sample_timestamps"]), 2)

    def test_signal_outcome_to_dict(self):
        """Test SignalOutcome conversion to dictionary."""
        outcome = SignalOutcome(
            signal_timestamp="2024-01-01T12:00:00",
            signal_type="whale entry",
            market_id="market_123",
            initial_price=0.50,
            price_after_5m=0.52,
            price_after_15m=0.55,
            price_after_60m=0.58,
            max_price_move=0.08,
            time_to_resolution_minutes=20.0,
            volume_before=1000.0,
            volume_after=1500.0,
            was_profitable=True,
        )

        result = outcome.to_dict()

        self.assertEqual(result["signal_timestamp"], "2024-01-01T12:00:00")
        self.assertEqual(result["signal_type"], "whale entry")
        self.assertEqual(result["market_id"], "market_123")
        self.assertEqual(result["initial_price"], 0.50)
        self.assertEqual(result["price_after_5m"], 0.52)
        self.assertEqual(result["was_profitable"], True)

    def test_correlation_summary_to_dict(self):
        """Test CorrelationSummary conversion to dictionary."""
        stats = PatternStatistics(
            pattern_type="test",
            total_occurrences=5,
            avg_price_move=0.03,
            avg_time_to_resolution_minutes=10.0,
            positive_outcome_rate=0.6,
            false_positive_rate=0.2,
            avg_volume_change=200.0,
            sample_timestamps=["2024-01-01T12:00:00"],
        )

        summary = CorrelationSummary(
            analysis_timestamp="2024-01-01T12:00:00",
            markets_analyzed=2,
            total_labels=10,
            pattern_stats={"test": stats},
            overall_false_positive_rate=0.15,
            time_to_resolution_curve=[(5, 25.0), (10, 50.0), (30, 90.0)],
            signal_outcomes=[],
        )

        result = summary.to_dict()

        self.assertEqual(result["analysis_timestamp"], "2024-01-01T12:00:00")
        self.assertEqual(result["markets_analyzed"], 2)
        self.assertEqual(result["total_labels"], 10)
        self.assertEqual(result["overall_false_positive_rate"], 0.15)
        self.assertIn("test", result["pattern_stats"])
        self.assertEqual(len(result["time_to_resolution_curve"]), 3)


class TestEventCorrelationAnalyzer(unittest.TestCase):
    """Test event correlation analyzer functionality."""

    def setUp(self):
        """Set up test databases for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.history_db_path = os.path.join(self.test_dir, "test_history.db")
        self.labels_db_path = os.path.join(self.test_dir, "test_labels.db")

        self.analyzer = EventCorrelationAnalyzer(
            history_db_path=self.history_db_path,
            labels_db_path=self.labels_db_path,
            resolution_window_minutes=60,
            price_stability_threshold=0.01,
        )

    def tearDown(self):
        """Clean up test databases after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        self.assertIsNotNone(self.analyzer)
        self.assertEqual(self.analyzer.resolution_window_minutes, 60)
        self.assertEqual(self.analyzer.price_stability_threshold, 0.01)

    def test_create_analyzer_convenience_function(self):
        """Test create_analyzer convenience function."""
        analyzer = create_analyzer(
            history_db_path=self.history_db_path,
            labels_db_path=self.labels_db_path,
            resolution_window_minutes=30,
        )

        self.assertIsNotNone(analyzer)
        self.assertIsInstance(analyzer, EventCorrelationAnalyzer)
        self.assertEqual(analyzer.resolution_window_minutes, 30)

    def test_analyze_patterns_empty_labels(self):
        """Test analysis with no labels."""
        summary = self.analyzer.analyze_patterns()

        self.assertEqual(summary.total_labels, 0)
        self.assertEqual(summary.markets_analyzed, 0)
        self.assertEqual(len(summary.pattern_stats), 0)
        self.assertEqual(summary.overall_false_positive_rate, 0.0)

    def test_analyze_patterns_with_data(self):
        """Test analysis with sample data."""
        # Create sample market data
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        ticks = []

        # Generate ticks: price starts at 0.50, moves to 0.55 over 30 minutes
        for i in range(61):  # 61 minutes of data
            timestamp = base_time + timedelta(minutes=i)
            # Price increases gradually
            price = 0.50 + (i / 60) * 0.05
            ticks.append({
                "market_id": "market_test_1",
                "timestamp": timestamp.isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "volume": 1000.0 + i * 10,
            })

        append_ticks(ticks, db_path=self.history_db_path)

        # Create a label at the start
        save_history_label(
            {
                "timestamp": base_time.isoformat(),
                "market_id": "market_test_1",
                "label_type": "whale entry",
                "notes": "Large buy detected",
            },
            db_path=self.labels_db_path,
        )

        # Run analysis
        summary = self.analyzer.analyze_patterns()

        # Verify results
        self.assertEqual(summary.total_labels, 1)
        self.assertEqual(summary.markets_analyzed, 1)
        self.assertGreater(len(summary.signal_outcomes), 0)

        # Check if whale entry pattern was analyzed
        if "whale entry" in summary.pattern_stats:
            whale_stats = summary.pattern_stats["whale entry"]
            self.assertEqual(whale_stats.pattern_type, "whale entry")
            self.assertEqual(whale_stats.total_occurrences, 1)

    def test_analyze_patterns_with_false_positives(self):
        """Test false positive rate calculation."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Create minimal tick data
        ticks = [
            {
                "market_id": "market_test_2",
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": 0.50,
                "no_price": 0.50,
                "volume": 1000.0,
            }
            for i in range(10)
        ]
        append_ticks(ticks, db_path=self.history_db_path)

        # Create labels: 2 whale entries, 1 false signal
        save_history_label(
            {
                "timestamp": base_time.isoformat(),
                "market_id": "market_test_2",
                "label_type": "whale entry",
                "notes": "First entry",
            },
            db_path=self.labels_db_path,
        )

        save_history_label(
            {
                "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
                "market_id": "market_test_2",
                "label_type": "whale entry",
                "notes": "Second entry",
            },
            db_path=self.labels_db_path,
        )

        save_history_label(
            {
                "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
                "market_id": "market_test_2",
                "label_type": "false signal",
                "notes": "whale entry was incorrect",
            },
            db_path=self.labels_db_path,
        )

        # Run analysis
        summary = self.analyzer.analyze_patterns()

        # Verify false positive rate is computed
        self.assertEqual(summary.total_labels, 3)
        # Overall FP rate should be 1/3 ≈ 0.33
        self.assertGreater(summary.overall_false_positive_rate, 0.0)

    def test_analyze_patterns_filter_by_market(self):
        """Test filtering analysis by market ID."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Create data for two markets
        for market_id in ["market_a", "market_b"]:
            ticks = [
                {
                    "market_id": market_id,
                    "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                    "yes_price": 0.50,
                    "no_price": 0.50,
                    "volume": 1000.0,
                }
                for i in range(10)
            ]
            append_ticks(ticks, db_path=self.history_db_path)

            save_history_label(
                {
                    "timestamp": base_time.isoformat(),
                    "market_id": market_id,
                    "label_type": "whale entry",
                    "notes": f"Entry in {market_id}",
                },
                db_path=self.labels_db_path,
            )

        # Analyze only market_a
        summary = self.analyzer.analyze_patterns(market_id="market_a")

        self.assertEqual(summary.total_labels, 1)
        self.assertEqual(summary.markets_analyzed, 1)

    def test_analyze_patterns_filter_by_label_type(self):
        """Test filtering analysis by label type."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Create tick data
        ticks = [
            {
                "market_id": "market_test_3",
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": 0.50,
                "no_price": 0.50,
                "volume": 1000.0,
            }
            for i in range(10)
        ]
        append_ticks(ticks, db_path=self.history_db_path)

        # Create multiple label types
        save_history_label(
            {
                "timestamp": base_time.isoformat(),
                "market_id": "market_test_3",
                "label_type": "whale entry",
                "notes": "Whale",
            },
            db_path=self.labels_db_path,
        )

        save_history_label(
            {
                "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
                "market_id": "market_test_3",
                "label_type": "news-driven move",
                "notes": "News",
            },
            db_path=self.labels_db_path,
        )

        # Analyze only whale entry
        summary = self.analyzer.analyze_patterns(label_types=["whale entry"])

        self.assertEqual(summary.total_labels, 1)

    def test_compute_resolution_curve(self):
        """Test time-to-resolution curve computation."""
        # Create sample outcomes with varying resolution times
        outcomes = [
            SignalOutcome(
                signal_timestamp="2024-01-01T12:00:00",
                signal_type="test",
                market_id="m1",
                initial_price=0.50,
                price_after_5m=0.51,
                price_after_15m=0.52,
                price_after_60m=0.53,
                max_price_move=0.03,
                time_to_resolution_minutes=float(t),
                volume_before=1000.0,
                volume_after=1100.0,
                was_profitable=True,
            )
            for t in [5, 10, 15, 20, 30, 45, 60]
        ]

        curve = self.analyzer._compute_resolution_curve(outcomes)

        # Verify curve structure
        self.assertGreater(len(curve), 0)
        for time_point, pct in curve:
            self.assertIsInstance(time_point, int)
            self.assertIsInstance(pct, float)
            self.assertGreaterEqual(pct, 0.0)
            self.assertLessEqual(pct, 100.0)

        # Verify curve is monotonically increasing
        percentages = [pct for _, pct in curve]
        self.assertEqual(percentages, sorted(percentages))

    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        # Test valid ISO format
        timestamp = "2024-01-01T12:00:00"
        result = self.analyzer._parse_timestamp(timestamp)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)

        # Test invalid timestamp
        result = self.analyzer._parse_timestamp("invalid")
        self.assertIsNone(result)

    def test_find_closest_tick(self):
        """Test finding closest tick to target time."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        ticks = [
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": 0.50 + i * 0.01,
                "no_price": 0.50 - i * 0.01,
                "market_id": "test",
                "volume": 1000.0,
            }
            for i in range(5)
        ]

        # Find tick closest to 2.5 minutes
        target = base_time + timedelta(minutes=2, seconds=30)
        closest = self.analyzer._find_closest_tick(ticks, target)

        self.assertIsNotNone(closest)
        # Should be either tick at minute 2 or 3
        closest_time = self.analyzer._parse_timestamp(closest["timestamp"])
        self.assertIn(
            closest_time,
            [base_time + timedelta(minutes=2), base_time + timedelta(minutes=3)]
        )

    def test_find_price_at_offset(self):
        """Test finding price at specific offset."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        ticks = [
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": 0.50 + i * 0.01,
                "no_price": 0.50 - i * 0.01,
                "market_id": "test",
                "volume": 1000.0,
            }
            for i in range(20)
        ]

        # Find price 10 minutes after base_time
        price = self.analyzer._find_price_at_offset(ticks, base_time, 10)

        self.assertIsNotNone(price)
        # Should be close to 0.50 + 10 * 0.01 = 0.60
        self.assertAlmostEqual(price, 0.60, places=2)

    def test_compute_resolution_metrics(self):
        """Test computing resolution metrics."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        initial_price = 0.50

        # Price moves up then stabilizes
        ticks = []
        for i in range(30):
            if i < 10:
                # Price increases
                price = 0.50 + i * 0.01
            else:
                # Price stabilizes around 0.60
                price = 0.60

            ticks.append({
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "market_id": "test",
                "volume": 1000.0,
            })

        max_move, time_to_resolution = self.analyzer._compute_resolution_metrics(
            ticks, base_time, initial_price
        )

        # Verify max move is around 0.10
        self.assertGreater(max_move, 0.05)
        self.assertLess(max_move, 0.15)

        # Verify time to resolution is detected (when price stabilizes)
        self.assertIsNotNone(time_to_resolution)
        self.assertGreater(time_to_resolution, 0)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete analysis scenarios."""

    def setUp(self):
        """Set up test databases for integration tests."""
        self.test_dir = tempfile.mkdtemp()
        self.history_db_path = os.path.join(self.test_dir, "integration_history.db")
        self.labels_db_path = os.path.join(self.test_dir, "integration_labels.db")

        self.analyzer = EventCorrelationAnalyzer(
            history_db_path=self.history_db_path,
            labels_db_path=self.labels_db_path,
        )

    def tearDown(self):
        """Clean up test databases."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_complete_analysis_workflow(self):
        """Test complete analysis workflow with realistic data."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Create realistic market data: price spike followed by stabilization
        ticks = []
        for i in range(90):
            if i < 10:
                # Normal trading
                price = 0.50
            elif i < 30:
                # Price spike (whale entry)
                price = 0.50 + (i - 10) * 0.02
            else:
                # Price stabilizes
                price = 0.70

            ticks.append({
                "market_id": "realistic_market",
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "yes_price": price,
                "no_price": 1.0 - price,
                "volume": 1000.0 + i * 50,
            })

        append_ticks(ticks, db_path=self.history_db_path)

        # Label the whale entry
        save_history_label(
            {
                "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "market_id": "realistic_market",
                "label_type": "whale entry",
                "notes": "Large buy order detected",
            },
            db_path=self.labels_db_path,
        )

        # Run complete analysis
        summary = self.analyzer.analyze_patterns()

        # Verify comprehensive results
        self.assertEqual(summary.total_labels, 1)
        self.assertEqual(summary.markets_analyzed, 1)
        self.assertGreater(len(summary.signal_outcomes), 0)

        # Verify pattern statistics were computed
        if "whale entry" in summary.pattern_stats:
            stats = summary.pattern_stats["whale entry"]
            self.assertGreater(stats.avg_price_move, 0)
            self.assertEqual(stats.total_occurrences, 1)

        # Verify resolution curve exists
        self.assertGreater(len(summary.time_to_resolution_curve), 0)


if __name__ == "__main__":
    unittest.main()
