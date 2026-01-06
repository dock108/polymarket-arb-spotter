"""
Unit tests for the historical replay engine.

Tests loading historical ticks, playback at different speeds,
jump-to-events functionality, and event emission via callbacks.
"""

import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.core.history_store import append_tick, append_ticks
from app.core.replay import (
    HistoricalReplayEngine,
    PlaybackSpeed,
    create_replay_engine,
)


class TestHistoricalReplayEngine(unittest.TestCase):
    """Base test class for replay engine tests."""

    def setUp(self):
        """Set up test database and sample data for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_replay_history.db")

        # Create sample historical data
        self._create_sample_data()

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_sample_data(self):
        """Create sample tick data for testing."""
        base_time = datetime(2024, 1, 5, 12, 0, 0)

        # Market 1: 10 ticks at 1-second intervals
        ticks_market1 = []
        for i in range(10):
            ticks_market1.append(
                {
                    "market_id": "market_1",
                    "timestamp": (base_time + timedelta(seconds=i)).isoformat(),
                    "yes_price": 0.50 + i * 0.01,
                    "no_price": 0.50 - i * 0.01,
                    "volume": 100.0 * (i + 1),
                }
            )
        append_ticks(ticks_market1, db_path=self.test_db_path)

        # Market 2: 5 ticks at 2-second intervals
        ticks_market2 = []
        for i in range(5):
            ticks_market2.append(
                {
                    "market_id": "market_2",
                    "timestamp": (base_time + timedelta(seconds=i * 2)).isoformat(),
                    "yes_price": 0.60 + i * 0.02,
                    "no_price": 0.40 - i * 0.02,
                    "volume": 200.0 * (i + 1),
                }
            )
        append_ticks(ticks_market2, db_path=self.test_db_path)

        # Market 3: Single tick for edge case testing
        append_tick(
            market_id="market_3",
            timestamp=base_time.isoformat(),
            yes_price=0.70,
            no_price=0.30,
            volume=500.0,
            db_path=self.test_db_path,
        )


class TestReplayEngineInitialization(TestHistoricalReplayEngine):
    """Test replay engine initialization."""

    def test_init_default_speed(self):
        """Test initialization with default real-time speed."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        self.assertEqual(engine.speed_multiplier, 1.0)
        self.assertFalse(engine.jump_to_events)
        self.assertFalse(engine.is_playing())
        self.assertFalse(engine.is_paused())

    def test_init_with_enum_real_time(self):
        """Test initialization with PlaybackSpeed.REAL_TIME."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.REAL_TIME
        )
        self.assertEqual(engine.speed_multiplier, 1.0)
        self.assertFalse(engine.jump_to_events)

    def test_init_with_enum_fast_10x(self):
        """Test initialization with PlaybackSpeed.FAST_10X."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.FAST_10X
        )
        self.assertEqual(engine.speed_multiplier, 10.0)
        self.assertFalse(engine.jump_to_events)

    def test_init_with_enum_jump_to_events(self):
        """Test initialization with PlaybackSpeed.JUMP_TO_EVENTS."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )
        self.assertEqual(engine.speed_multiplier, 0.0)
        self.assertTrue(engine.jump_to_events)

    def test_init_with_custom_float_speed(self):
        """Test initialization with custom float speed multiplier."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path, speed=5.0)
        self.assertEqual(engine.speed_multiplier, 5.0)
        self.assertFalse(engine.jump_to_events)

    def test_init_with_zero_speed(self):
        """Test initialization with zero speed (instant playback)."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path, speed=0.0)
        self.assertEqual(engine.speed_multiplier, 0.0)
        self.assertTrue(engine.jump_to_events)

    def test_init_negative_speed_clamped(self):
        """Test that negative speed is clamped to 0."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path, speed=-5.0)
        self.assertEqual(engine.speed_multiplier, 0.0)


class TestSetSpeed(TestHistoricalReplayEngine):
    """Test speed adjustment functionality."""

    def test_set_speed_with_enum(self):
        """Test changing speed with enum value."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        engine.set_speed(PlaybackSpeed.FAST_10X)
        self.assertEqual(engine.speed_multiplier, 10.0)
        self.assertFalse(engine.jump_to_events)

    def test_set_speed_with_float(self):
        """Test changing speed with float value."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        engine.set_speed(3.5)
        self.assertEqual(engine.speed_multiplier, 3.5)
        self.assertFalse(engine.jump_to_events)

    def test_set_speed_to_jump_to_events(self):
        """Test changing to jump-to-events mode."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.REAL_TIME
        )
        engine.set_speed(PlaybackSpeed.JUMP_TO_EVENTS)
        self.assertTrue(engine.jump_to_events)
        self.assertEqual(engine.speed_multiplier, 0.0)


class TestGetAvailableMarkets(TestHistoricalReplayEngine):
    """Test getting available markets from history store."""

    def test_get_available_markets(self):
        """Test retrieving list of available markets."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        markets = engine.get_available_markets()
        self.assertEqual(len(markets), 3)
        self.assertIn("market_1", markets)
        self.assertIn("market_2", markets)
        self.assertIn("market_3", markets)

    def test_get_available_markets_empty_db(self):
        """Test getting markets from empty database."""
        empty_db = os.path.join(self.test_dir, "empty.db")
        engine = HistoricalReplayEngine(db_path=empty_db)
        markets = engine.get_available_markets()
        self.assertEqual(markets, [])


class TestReplayMarket(TestHistoricalReplayEngine):
    """Test replaying a single market."""

    def test_replay_market_basic(self):
        """Test basic replay of market with callback."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            received_ticks.append(tick)

        count = engine.replay_market("market_1", on_tick=on_tick)

        self.assertEqual(count, 10)
        self.assertEqual(len(received_ticks), 10)
        # Verify first and last tick
        self.assertEqual(received_ticks[0]["yes_price"], 0.50)
        self.assertEqual(received_ticks[-1]["yes_price"], 0.59)

    def test_replay_market_with_time_range(self):
        """Test replay with start and end time filters."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        base_time = datetime(2024, 1, 5, 12, 0, 0)
        start = base_time + timedelta(seconds=2)
        end = base_time + timedelta(seconds=5)

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            received_ticks.append(tick)

        count = engine.replay_market(
            "market_1", start=start, end=end, on_tick=on_tick
        )

        # Should get ticks at t=2,3,4,5 (4 ticks)
        self.assertEqual(count, 4)
        self.assertEqual(len(received_ticks), 4)

    def test_replay_market_nonexistent(self):
        """Test replaying nonexistent market returns 0."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        count = engine.replay_market("nonexistent_market")
        self.assertEqual(count, 0)

    def test_replay_market_with_limit(self):
        """Test replay respects limit parameter."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            received_ticks.append(tick)

        count = engine.replay_market("market_1", on_tick=on_tick, limit=5)

        self.assertEqual(count, 5)
        self.assertEqual(len(received_ticks), 5)

    def test_replay_market_without_callback(self):
        """Test replay without callback doesn't crash."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        count = engine.replay_market("market_1")
        self.assertEqual(count, 10)

    def test_replay_market_callback_exception_handled(self):
        """Test that exceptions in callback don't stop replay."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        call_count = [0]

        def failing_callback(tick: Dict[str, Any]):
            call_count[0] += 1
            if call_count[0] == 3:
                raise ValueError("Test exception in callback")

        count = engine.replay_market("market_1", on_tick=failing_callback)

        # Should complete all 10 ticks despite exception
        self.assertEqual(count, 10)
        self.assertEqual(call_count[0], 10)

    def test_replay_market_single_tick(self):
        """Test replaying market with single tick."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            received_ticks.append(tick)

        count = engine.replay_market("market_3", on_tick=on_tick)

        self.assertEqual(count, 1)
        self.assertEqual(len(received_ticks), 1)
        self.assertEqual(received_ticks[0]["yes_price"], 0.70)


class TestReplayTiming(TestHistoricalReplayEngine):
    """Test replay timing with different speeds."""

    def test_replay_jump_to_events_is_fast(self):
        """Test that jump-to-events mode is very fast."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        start_time = time.time()
        count = engine.replay_market("market_1")
        elapsed = time.time() - start_time

        self.assertEqual(count, 10)
        # Should complete almost instantly (< 0.5 seconds)
        self.assertLess(elapsed, 0.5)

    def test_replay_fast_10x_speed(self):
        """Test that 10× speed is faster than real-time."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.FAST_10X
        )

        start_time = time.time()
        count = engine.replay_market("market_1")
        elapsed = time.time() - start_time

        self.assertEqual(count, 10)
        # 10 ticks at 1-second intervals = 9 seconds real-time
        # At 10× speed = 0.9 seconds, allow some overhead
        self.assertLess(elapsed, 2.0)
        self.assertGreater(elapsed, 0.5)  # Should have some delay

    def test_replay_custom_speed(self):
        """Test replay with custom speed multiplier."""
        # Use very fast speed for quick test (100× speed)
        engine = HistoricalReplayEngine(db_path=self.test_db_path, speed=100.0)

        start_time = time.time()
        count = engine.replay_market("market_1")
        elapsed = time.time() - start_time

        self.assertEqual(count, 10)
        # At 100× speed, 9 seconds becomes 0.09 seconds
        self.assertLess(elapsed, 1.0)


class TestReplayControl(TestHistoricalReplayEngine):
    """Test replay control functions (stop, pause, resume)."""

    def test_stop_replay(self):
        """Test stopping replay mid-execution."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_count = [0]

        def on_tick(tick: Dict[str, Any]):
            received_count[0] += 1
            if received_count[0] == 5:
                engine.stop()

        count = engine.replay_market("market_1", on_tick=on_tick)

        # Should stop after 5 ticks
        self.assertEqual(count, 5)
        self.assertEqual(received_count[0], 5)
        self.assertFalse(engine.is_playing())

    def test_is_playing_during_replay(self):
        """Test is_playing status during replay."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        playing_status = []

        def on_tick(tick: Dict[str, Any]):
            playing_status.append(engine.is_playing())

        engine.replay_market("market_1", on_tick=on_tick)

        # Should be playing during all ticks
        self.assertTrue(all(playing_status))
        # Should not be playing after completion
        self.assertFalse(engine.is_playing())


class TestReplayMarkets(TestHistoricalReplayEngine):
    """Test replaying multiple markets."""

    def test_replay_markets_multiple(self):
        """Test replaying multiple markets sequentially."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            received_ticks.append(tick)

        results = engine.replay_markets(
            ["market_1", "market_2"], on_tick=on_tick
        )

        self.assertEqual(results["market_1"], 10)
        self.assertEqual(results["market_2"], 5)
        self.assertEqual(len(received_ticks), 15)

    def test_replay_markets_with_nonexistent(self):
        """Test replaying includes nonexistent market."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        results = engine.replay_markets(["market_1", "nonexistent", "market_2"])

        self.assertEqual(results["market_1"], 10)
        self.assertEqual(results["nonexistent"], 0)
        self.assertEqual(results["market_2"], 5)

    def test_replay_all_markets(self):
        """Test replaying all available markets."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            received_ticks.append(tick)

        results = engine.replay_all_markets(on_tick=on_tick)

        self.assertEqual(len(results), 3)
        self.assertEqual(results["market_1"], 10)
        self.assertEqual(results["market_2"], 5)
        self.assertEqual(results["market_3"], 1)
        self.assertEqual(len(received_ticks), 16)

    def test_replay_all_markets_empty_db(self):
        """Test replay_all_markets with empty database."""
        empty_db = os.path.join(self.test_dir, "empty.db")
        engine = HistoricalReplayEngine(db_path=empty_db)

        results = engine.replay_all_markets()
        self.assertEqual(results, {})


class TestCreateReplayEngine(TestHistoricalReplayEngine):
    """Test convenience factory function."""

    def test_create_replay_engine_default(self):
        """Test creating engine with default parameters."""
        engine = create_replay_engine(db_path=self.test_db_path)
        self.assertIsInstance(engine, HistoricalReplayEngine)
        self.assertEqual(engine.speed_multiplier, 1.0)

    def test_create_replay_engine_with_speed(self):
        """Test creating engine with custom speed."""
        engine = create_replay_engine(
            db_path=self.test_db_path, speed=PlaybackSpeed.FAST_10X
        )
        self.assertIsInstance(engine, HistoricalReplayEngine)
        self.assertEqual(engine.speed_multiplier, 10.0)


class TestTimestampParsing(TestHistoricalReplayEngine):
    """Test timestamp parsing functionality."""

    def test_parse_timestamp_iso_format(self):
        """Test parsing ISO format timestamp."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        timestamp_str = "2024-01-05T12:00:00"
        result = engine._parse_timestamp(timestamp_str)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 5)

    def test_parse_timestamp_datetime_object(self):
        """Test parsing datetime object returns same object."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        dt = datetime(2024, 1, 5, 12, 0, 0)
        result = engine._parse_timestamp(dt)
        self.assertEqual(result, dt)

    def test_parse_timestamp_invalid_returns_none(self):
        """Test parsing invalid timestamp returns None."""
        engine = HistoricalReplayEngine(db_path=self.test_db_path)
        result = engine._parse_timestamp("invalid-timestamp")
        self.assertIsNone(result)


class TestReplayEngineIntegration(TestHistoricalReplayEngine):
    """Integration tests for replay engine with realistic scenarios."""

    def test_replay_simulates_live_data_stream(self):
        """Test that replay accurately simulates live data stream."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        received_ticks = []

        def on_tick(tick: Dict[str, Any]):
            # Simulate processing like with live WebSocket data
            received_ticks.append(
                {
                    "market_id": tick["market_id"],
                    "yes_price": tick["yes_price"],
                    "no_price": tick["no_price"],
                    "timestamp": tick["timestamp"],
                }
            )

        count = engine.replay_market("market_1", on_tick=on_tick)

        self.assertEqual(count, 10)
        # Verify data integrity
        for i, tick in enumerate(received_ticks):
            self.assertEqual(tick["market_id"], "market_1")
            expected_yes_price = 0.50 + i * 0.01
            self.assertAlmostEqual(tick["yes_price"], expected_yes_price, places=2)

    def test_replay_with_multiple_consumers(self):
        """Test replay with multiple callback consumers."""
        engine = HistoricalReplayEngine(
            db_path=self.test_db_path, speed=PlaybackSpeed.JUMP_TO_EVENTS
        )

        consumer1_data = []
        consumer2_data = []

        def on_tick(tick: Dict[str, Any]):
            # Simulate two consumers processing same tick
            consumer1_data.append(tick["yes_price"])
            consumer2_data.append(tick["no_price"])

        engine.replay_market("market_1", on_tick=on_tick)

        self.assertEqual(len(consumer1_data), 10)
        self.assertEqual(len(consumer2_data), 10)
        # Verify prices are complementary
        for yes_price, no_price in zip(consumer1_data, consumer2_data):
            # Should be approximately complementary (sum close to 1.0)
            self.assertAlmostEqual(yes_price + no_price, 1.0, delta=0.02)


if __name__ == "__main__":
    unittest.main()
