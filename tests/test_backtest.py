"""
Unit tests for backtest functionality.

Tests the BacktestEngine class and backtest_results table operations.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.history_store import (
    append_tick,
    append_ticks,
    append_backtest_result,
    get_backtest_results,
)
from app.core.replay import BacktestEngine, create_backtest_engine, PlaybackSpeed
from app.core.arb_detector import ArbitrageDetector


class TestBacktestResults(unittest.TestCase):
    """Test backtest_results table operations."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_backtest.db")

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_append_backtest_result_basic(self):
        """Test appending a single backtest result."""
        append_backtest_result(
            strategy="arb_detector",
            market_id="market_123",
            timestamp="2024-01-05T12:00:00",
            signal={"profit": 0.05, "type": "two-way"},
            simulated_outcome="would_trigger",
            notes="Test arbitrage",
            db_path=self.test_db_path,
        )

        # Verify result was stored
        results = get_backtest_results(db_path=self.test_db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["strategy"], "arb_detector")
        self.assertEqual(results[0]["market_id"], "market_123")
        self.assertEqual(results[0]["simulated_outcome"], "would_trigger")
        self.assertEqual(results[0]["signal"]["profit"], 0.05)

    def test_append_backtest_result_with_datetime(self):
        """Test appending a backtest result with datetime object."""
        timestamp = datetime(2024, 1, 5, 12, 0, 0)
        append_backtest_result(
            strategy="price_alert",
            market_id="market_456",
            timestamp=timestamp,
            signal={"direction": "above", "target": 0.70},
            simulated_outcome="early",
            notes="Early trigger",
            db_path=self.test_db_path,
        )

        results = get_backtest_results(db_path=self.test_db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["timestamp"], "2024-01-05T12:00:00")

    def test_get_backtest_results_by_strategy(self):
        """Test filtering backtest results by strategy."""
        # Add results for different strategies
        append_backtest_result(
            strategy="arb_detector",
            market_id="market_1",
            timestamp="2024-01-05T12:00:00",
            signal={"profit": 0.05},
            simulated_outcome="would_trigger",
            db_path=self.test_db_path,
        )
        append_backtest_result(
            strategy="price_alert",
            market_id="market_1",
            timestamp="2024-01-05T12:01:00",
            signal={"direction": "above"},
            simulated_outcome="would_trigger",
            db_path=self.test_db_path,
        )
        append_backtest_result(
            strategy="depth_scanner",
            market_id="market_1",
            timestamp="2024-01-05T12:02:00",
            signal={"type": "thin_depth"},
            simulated_outcome="would_trigger",
            db_path=self.test_db_path,
        )

        # Filter by strategy
        arb_results = get_backtest_results(
            strategy="arb_detector", db_path=self.test_db_path
        )
        self.assertEqual(len(arb_results), 1)
        self.assertEqual(arb_results[0]["strategy"], "arb_detector")

        price_results = get_backtest_results(
            strategy="price_alert", db_path=self.test_db_path
        )
        self.assertEqual(len(price_results), 1)
        self.assertEqual(price_results[0]["strategy"], "price_alert")

    def test_get_backtest_results_by_market(self):
        """Test filtering backtest results by market ID."""
        append_backtest_result(
            strategy="arb_detector",
            market_id="market_1",
            timestamp="2024-01-05T12:00:00",
            signal={},
            simulated_outcome="would_trigger",
            db_path=self.test_db_path,
        )
        append_backtest_result(
            strategy="arb_detector",
            market_id="market_2",
            timestamp="2024-01-05T12:01:00",
            signal={},
            simulated_outcome="would_trigger",
            db_path=self.test_db_path,
        )

        # Filter by market
        market1_results = get_backtest_results(
            market_id="market_1", db_path=self.test_db_path
        )
        self.assertEqual(len(market1_results), 1)
        self.assertEqual(market1_results[0]["market_id"], "market_1")

    def test_get_backtest_results_with_time_range(self):
        """Test filtering backtest results by time range."""
        base_time = datetime(2024, 1, 5, 12, 0, 0)

        # Add results at different times
        for i in range(5):
            append_backtest_result(
                strategy="arb_detector",
                market_id="market_1",
                timestamp=(base_time + timedelta(minutes=i)).isoformat(),
                signal={},
                simulated_outcome="would_trigger",
                db_path=self.test_db_path,
            )

        # Get results within time range
        results = get_backtest_results(
            start=base_time + timedelta(minutes=1),
            end=base_time + timedelta(minutes=3),
            db_path=self.test_db_path,
        )
        self.assertEqual(len(results), 3)

    def test_get_backtest_results_with_limit(self):
        """Test limiting number of results returned."""
        for i in range(10):
            append_backtest_result(
                strategy="arb_detector",
                market_id="market_1",
                timestamp=f"2024-01-05T12:0{i}:00",
                signal={},
                simulated_outcome="would_trigger",
                db_path=self.test_db_path,
            )

        results = get_backtest_results(limit=5, db_path=self.test_db_path)
        self.assertEqual(len(results), 5)


class TestBacktestEngine(unittest.TestCase):
    """Test BacktestEngine class."""

    def setUp(self):
        """Set up test database and sample data for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_backtest_engine.db")

        # Create sample historical data
        self._create_sample_data()

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_sample_data(self):
        """Create sample tick data for testing."""
        base_time = datetime(2024, 1, 5, 12, 0, 0)

        # Create ticks with arbitrage opportunity (price sum < 1.0)
        ticks = []
        for i in range(5):
            # Create arbitrage opportunity (sum < 0.98)
            yes_price = 0.45 + i * 0.01
            no_price = 0.45 - i * 0.01
            ticks.append(
                {
                    "market_id": "market_arb",
                    "timestamp": (base_time + timedelta(seconds=i)).isoformat(),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": 100.0 * (i + 1),
                }
            )

        # Create ticks that trigger price alerts
        for i in range(5):
            yes_price = 0.60 + i * 0.05  # Will cross 0.70 threshold
            no_price = 1.0 - yes_price
            ticks.append(
                {
                    "market_id": "market_price",
                    "timestamp": (base_time + timedelta(seconds=i + 10)).isoformat(),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": 200.0 * (i + 1),
                }
            )

        append_ticks(ticks, db_path=self.test_db_path)

    def test_backtest_engine_initialization(self):
        """Test BacktestEngine initialization."""
        engine = BacktestEngine(db_path=self.test_db_path)
        self.assertIsNotNone(engine.replay_engine)
        self.assertEqual(engine.db_path, self.test_db_path)
        self.assertIsNone(engine.arb_detector)
        self.assertEqual(len(engine.price_alerts), 0)
        self.assertIsNone(engine.depth_config)

    def test_create_backtest_engine(self):
        """Test create_backtest_engine convenience function."""
        engine = create_backtest_engine(db_path=self.test_db_path)
        self.assertIsInstance(engine, BacktestEngine)
        self.assertEqual(engine.db_path, self.test_db_path)

    def test_set_arb_detector(self):
        """Test setting arbitrage detector."""
        engine = BacktestEngine(db_path=self.test_db_path)
        detector = ArbitrageDetector()
        engine.set_arb_detector(detector)
        self.assertIsNotNone(engine.arb_detector)

    def test_add_price_alert(self):
        """Test adding price alerts."""
        engine = BacktestEngine(db_path=self.test_db_path)
        engine.add_price_alert("market_123", "above", 0.70)
        engine.add_price_alert("market_456", "below", 0.30)

        self.assertEqual(len(engine.price_alerts), 2)
        self.assertEqual(engine.price_alerts[0]["market_id"], "market_123")
        self.assertEqual(engine.price_alerts[0]["direction"], "above")
        self.assertEqual(engine.price_alerts[0]["target_price"], 0.70)

    def test_set_depth_config(self):
        """Test setting depth scanner configuration."""
        engine = BacktestEngine(db_path=self.test_db_path)
        config = {"min_depth": 500.0, "max_gap": 0.10}
        engine.set_depth_config(config)
        self.assertEqual(engine.depth_config, config)

    def test_run_backtest_with_arb_detector(self):
        """Test running backtest with arbitrage detector."""
        engine = BacktestEngine(db_path=self.test_db_path)
        detector = ArbitrageDetector()
        engine.set_arb_detector(detector)

        # Run backtest on market with arbitrage opportunities
        stats = engine.run_backtest(
            market_ids=["market_arb"], limit_per_market=10
        )

        # Verify statistics
        self.assertGreater(stats["ticks_processed"], 0)
        self.assertGreater(stats["arb_signals"], 0)
        self.assertEqual(stats["markets_analyzed"], 1)

        # Verify results were stored
        results = get_backtest_results(
            strategy="arb_detector", db_path=self.test_db_path
        )
        self.assertGreater(len(results), 0)

    def test_run_backtest_with_price_alerts(self):
        """Test running backtest with price alerts."""
        engine = BacktestEngine(db_path=self.test_db_path)
        engine.add_price_alert("market_price", "above", 0.70)

        # Run backtest on market with price changes
        stats = engine.run_backtest(
            market_ids=["market_price"], limit_per_market=10
        )

        # Verify statistics
        self.assertGreater(stats["ticks_processed"], 0)
        self.assertGreater(stats["price_alerts_triggered"], 0)

        # Verify results were stored
        results = get_backtest_results(
            strategy="price_alert", db_path=self.test_db_path
        )
        self.assertGreater(len(results), 0)

    def test_run_backtest_all_strategies(self):
        """Test running backtest with all strategies configured."""
        engine = BacktestEngine(db_path=self.test_db_path)

        # Configure all strategies
        engine.set_arb_detector(ArbitrageDetector())
        engine.add_price_alert("market_price", "above", 0.70)
        engine.set_depth_config({"min_depth": 500.0})

        # Run backtest
        stats = engine.run_backtest(limit_per_market=10)

        # Verify statistics
        self.assertGreater(stats["ticks_processed"], 0)
        self.assertGreater(stats["markets_analyzed"], 0)

    def test_get_summary(self):
        """Test getting backtest summary."""
        engine = BacktestEngine(db_path=self.test_db_path)
        detector = ArbitrageDetector()
        engine.set_arb_detector(detector)

        # Run backtest
        engine.run_backtest(market_ids=["market_arb"], limit_per_market=5)

        # Get summary
        summary = engine.get_summary()
        self.assertIn("ticks_processed", summary)
        self.assertIn("arb_signals", summary)
        self.assertIn("price_alerts_triggered", summary)
        self.assertIn("depth_signals", summary)
        self.assertIn("markets_analyzed", summary)

    def test_backtest_with_no_data(self):
        """Test backtest with empty database."""
        empty_db_path = os.path.join(self.test_dir, "empty.db")
        engine = BacktestEngine(db_path=empty_db_path)
        engine.set_arb_detector(ArbitrageDetector())

        stats = engine.run_backtest(market_ids=["nonexistent"])
        self.assertEqual(stats["ticks_processed"], 0)

    def test_backtest_price_alert_not_triggered(self):
        """Test price alert that never gets triggered."""
        engine = BacktestEngine(db_path=self.test_db_path)
        # Set threshold that won't be reached
        engine.add_price_alert("market_arb", "above", 0.99)

        stats = engine.run_backtest(market_ids=["market_arb"], limit_per_market=10)

        # Should have processed ticks but no alerts triggered
        self.assertGreater(stats["ticks_processed"], 0)
        self.assertEqual(stats["price_alerts_triggered"], 0)


if __name__ == "__main__":
    unittest.main()
