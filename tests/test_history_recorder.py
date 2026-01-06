"""
Unit tests for the history recorder module.

Tests the non-blocking queue-based history recorder functionality,
including sampling, threading, and integration with history_store.
"""

import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.core.history_recorder import (
    HistoryRecorder,
    get_history_recorder,
    start_history_recorder,
    stop_history_recorder,
    record_market_tick,
)
from app.core.history_store import get_ticks


class TestHistoryRecorder(unittest.TestCase):
    """Test HistoryRecorder class."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_history.db")

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization_disabled(self):
        """Test HistoryRecorder initialization when disabled."""
        recorder = HistoryRecorder(enabled=False, sampling_ms=1000)
        self.assertFalse(recorder.enabled)
        self.assertEqual(recorder.sampling_ms, 1000)
        self.assertEqual(recorder.stats["queued"], 0)
        self.assertEqual(recorder.stats["recorded"], 0)

    def test_initialization_enabled(self):
        """Test HistoryRecorder initialization when enabled."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=500)
        self.assertTrue(recorder.enabled)
        self.assertEqual(recorder.sampling_ms, 500)

    def test_record_tick_when_disabled(self):
        """Test that record_tick returns False when disabled."""
        recorder = HistoryRecorder(enabled=False)
        result = recorder.record_tick(
            market_id="market_1",
            yes_price=0.65,
            no_price=0.35,
            volume=100.0,
        )
        self.assertFalse(result)
        self.assertEqual(recorder.stats["queued"], 0)

    def test_record_tick_sampling(self):
        """Test that sampling throttles recording."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=1000)
        recorder.start()

        try:
            # First tick should be recorded
            result1 = recorder.record_tick(
                market_id="market_1",
                yes_price=0.65,
                no_price=0.35,
                volume=100.0,
            )
            self.assertTrue(result1)
            self.assertEqual(recorder.stats["queued"], 1)

            # Second tick immediately after should be skipped (sampling)
            result2 = recorder.record_tick(
                market_id="market_1",
                yes_price=0.66,
                no_price=0.34,
                volume=100.0,
            )
            self.assertFalse(result2)
            self.assertEqual(recorder.stats["queued"], 1)
            self.assertEqual(recorder.stats["skipped_sampling"], 1)

            # Different market should still be recorded
            result3 = recorder.record_tick(
                market_id="market_2",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
            )
            self.assertTrue(result3)
            self.assertEqual(recorder.stats["queued"], 2)

        finally:
            recorder.stop()

    def test_start_stop(self):
        """Test starting and stopping the recorder."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=100)

        # Start the recorder
        recorder.start()
        self.assertTrue(recorder._worker_thread.is_alive())

        # Stop the recorder
        recorder.stop()
        time.sleep(0.1)  # Give thread time to stop
        self.assertFalse(recorder._worker_thread.is_alive())

    def test_start_when_disabled(self):
        """Test that start() does nothing when disabled."""
        recorder = HistoryRecorder(enabled=False)
        recorder.start()
        self.assertIsNone(recorder._worker_thread)

    @patch("app.core.history_recorder.append_tick")
    def test_worker_writes_ticks(self, mock_append_tick):
        """Test that worker thread writes ticks to history store."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=100)
        recorder.start()

        try:
            # Record a tick
            recorder.record_tick(
                market_id="market_1",
                yes_price=0.65,
                no_price=0.35,
                volume=100.0,
            )

            # Wait for worker to process
            time.sleep(0.5)

            # Verify append_tick was called
            self.assertTrue(mock_append_tick.called)
            self.assertEqual(recorder.stats["recorded"], 1)

        finally:
            recorder.stop()

    def test_stats_tracking(self):
        """Test that statistics are tracked correctly."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=100)
        recorder.start()

        try:
            # Record first tick (should be queued)
            recorder.record_tick("market_1", 0.65, 0.35, 100.0)
            self.assertEqual(recorder.stats["queued"], 1)

            # Record second tick immediately (should be skipped due to sampling)
            recorder.record_tick("market_1", 0.66, 0.34, 100.0)
            self.assertEqual(recorder.stats["skipped_sampling"], 1)

            # Wait for worker to process
            time.sleep(0.3)

        finally:
            recorder.stop()

    def test_record_tick_with_depth_summary(self):
        """Test recording tick with depth summary."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=100)
        recorder.start()

        try:
            depth_summary = {"total_depth": 1000, "yes_depth": 600, "no_depth": 400}
            result = recorder.record_tick(
                market_id="market_1",
                yes_price=0.65,
                no_price=0.35,
                volume=100.0,
                depth_summary=depth_summary,
            )
            self.assertTrue(result)
            self.assertEqual(recorder.stats["queued"], 1)

        finally:
            recorder.stop()

    def test_record_tick_with_timestamp(self):
        """Test recording tick with custom timestamp."""
        recorder = HistoryRecorder(enabled=True, sampling_ms=100)
        recorder.start()

        try:
            custom_time = datetime(2024, 1, 5, 12, 0, 0)
            result = recorder.record_tick(
                market_id="market_1",
                yes_price=0.65,
                no_price=0.35,
                volume=100.0,
                timestamp=custom_time,
            )
            self.assertTrue(result)

        finally:
            recorder.stop()


class TestHistoryRecorderSingleton(unittest.TestCase):
    """Test singleton pattern for history recorder."""

    def setUp(self):
        """Reset singleton before each test."""
        import app.core.history_recorder as hr

        hr._recorder = None

    def tearDown(self):
        """Stop singleton after each test."""
        import app.core.history_recorder as hr

        if hr._recorder is not None:
            hr._recorder.stop()
            hr._recorder = None

    @patch("app.core.history_recorder.get_config")
    def test_get_history_recorder_creates_singleton(self, mock_get_config):
        """Test that get_history_recorder creates and returns singleton."""
        mock_config = MagicMock()
        mock_config.enable_history = False
        mock_config.history_sampling_ms = 1500
        mock_get_config.return_value = mock_config

        recorder1 = get_history_recorder()
        recorder2 = get_history_recorder()
        self.assertIs(recorder1, recorder2)

    @patch("app.core.history_recorder.get_config")
    def test_start_history_recorder(self, mock_get_config):
        """Test start_history_recorder convenience function."""
        mock_config = MagicMock()
        mock_config.enable_history = True
        mock_config.history_sampling_ms = 1500
        mock_get_config.return_value = mock_config

        recorder = start_history_recorder()
        self.assertIsNotNone(recorder)
        self.assertTrue(recorder._worker_thread.is_alive())
        recorder.stop()

    @patch("app.core.history_recorder.get_config")
    def test_stop_history_recorder(self, mock_get_config):
        """Test stop_history_recorder convenience function."""
        mock_config = MagicMock()
        mock_config.enable_history = True
        mock_config.history_sampling_ms = 1500
        mock_get_config.return_value = mock_config

        # Start first
        recorder = start_history_recorder()
        self.assertTrue(recorder._worker_thread.is_alive())

        # Stop
        stop_history_recorder()
        time.sleep(0.1)
        self.assertFalse(recorder._worker_thread.is_alive())

    @patch("app.core.history_recorder.get_config")
    def test_record_market_tick_convenience(self, mock_get_config):
        """Test record_market_tick convenience function."""
        mock_config = MagicMock()
        mock_config.enable_history = True
        mock_config.history_sampling_ms = 100
        mock_get_config.return_value = mock_config

        # Start recorder
        start_history_recorder()

        try:
            result = record_market_tick(
                market_id="market_1",
                yes_price=0.65,
                no_price=0.35,
                volume=100.0,
            )
            self.assertTrue(result)

        finally:
            stop_history_recorder()


class TestHistoryRecorderConfig(unittest.TestCase):
    """Test config integration for history recorder."""

    @patch("app.core.history_recorder.get_config")
    def test_uses_config_values(self, mock_get_config):
        """Test that recorder uses config values when not overridden."""
        mock_config = MagicMock()
        mock_config.enable_history = True
        mock_config.history_sampling_ms = 2000
        mock_get_config.return_value = mock_config

        recorder = HistoryRecorder()
        self.assertTrue(recorder.enabled)
        self.assertEqual(recorder.sampling_ms, 2000)

    def test_override_config_values(self):
        """Test that explicit values override config."""
        recorder = HistoryRecorder(enabled=False, sampling_ms=500)
        self.assertFalse(recorder.enabled)
        self.assertEqual(recorder.sampling_ms, 500)


class TestConfigWithHistory(unittest.TestCase):
    """Test Config class with history settings."""

    @patch.dict(
        os.environ,
        {
            "ENABLE_HISTORY": "true",
            "HISTORY_SAMPLING_MS": "2000",
        },
    )
    def test_from_env_with_history_enabled(self):
        """Test loading history config from environment variables."""
        from app.core.config import Config

        config = Config.from_env()
        self.assertTrue(config.enable_history)
        self.assertEqual(config.history_sampling_ms, 2000)

    @patch.dict(
        os.environ,
        {
            "ENABLE_HISTORY": "false",
        },
    )
    def test_from_env_with_history_disabled(self):
        """Test loading history config when disabled."""
        from app.core.config import Config

        config = Config.from_env()
        self.assertFalse(config.enable_history)

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_history_defaults(self):
        """Test that history config has defaults."""
        from app.core.config import Config

        config = Config.from_env()
        self.assertFalse(config.enable_history)
        self.assertEqual(config.history_sampling_ms, 1500)

    @patch.dict(
        os.environ,
        {
            "ENABLE_HISTORY": "1",  # Test "1" as truthy
        },
    )
    def test_from_env_history_truthy_values(self):
        """Test various truthy values for ENABLE_HISTORY."""
        from app.core.config import Config

        config = Config.from_env()
        self.assertTrue(config.enable_history)


if __name__ == "__main__":
    unittest.main()
