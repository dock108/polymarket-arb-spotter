"""
Unit tests for run_depth_scanner script.

Tests the DepthScannerRunner class with mocked dependencies.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add parent directory to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_depth_scanner import DepthScannerRunner
from app.core.depth_scanner import DepthSignal


class TestDepthScannerRunner(unittest.TestCase):
    """Test DepthScannerRunner class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test config
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.test_dir, "test_depth_config.json")

        # Create test config
        import json

        test_config = {
            "min_depth": 500.0,
            "max_gap": 0.10,
            "imbalance_ratio": 300.0,
            "markets_to_watch": ["test_market_1", "test_market_2"],
        }
        with open(self.test_config_path, "w") as f:
            json.dump(test_config, f)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test DepthScannerRunner initialization."""
        runner = DepthScannerRunner(
            poll_interval=30,
            duration=60,
            log_level="INFO",
            config_path=self.test_config_path,
        )

        self.assertEqual(runner.poll_interval, 30)
        self.assertEqual(runner.duration, 60)
        self.assertEqual(runner.log_level, "INFO")
        self.assertEqual(runner.config_path, self.test_config_path)
        self.assertFalse(runner.running)
        self.assertEqual(runner.retry_count, 0)
        self.assertEqual(runner.max_retries, 5)
        self.assertEqual(runner.stats["markets_scanned"], 0)
        self.assertEqual(runner.stats["signals_detected"], 0)

    def test_compute_signal_hash(self):
        """Test signal hash computation for deduplication."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        signal1 = DepthSignal(
            signal_type="thin_depth",
            triggered=True,
            reason="Test reason",
            metrics={"total_depth": 100.0},
        )

        signal2 = DepthSignal(
            signal_type="large_gap",
            triggered=True,
            reason="Different reason",
            metrics={"max_gap": 0.15},
        )

        # Same market and signal type should produce same hash
        hash1a = runner._compute_signal_hash("market_1", signal1)
        hash1b = runner._compute_signal_hash("market_1", signal1)
        self.assertEqual(hash1a, hash1b)

        # Different signal types should produce different hashes
        hash2 = runner._compute_signal_hash("market_1", signal2)
        self.assertNotEqual(hash1a, hash2)

        # Different markets should produce different hashes
        hash3 = runner._compute_signal_hash("market_2", signal1)
        self.assertNotEqual(hash1a, hash3)

    def test_signal_deduplication(self):
        """Test that duplicate signals are detected."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        signal = DepthSignal(
            signal_type="thin_depth",
            triggered=True,
            reason="Test reason",
            metrics={"total_depth": 100.0},
        )

        # First signal should not be a duplicate
        self.assertFalse(runner._is_signal_duplicate("market_1", signal))

        # Mark signal as sent
        runner._mark_signal_sent("market_1", signal)

        # Now it should be a duplicate
        self.assertTrue(runner._is_signal_duplicate("market_1", signal))

        # Different market should not be a duplicate
        self.assertFalse(runner._is_signal_duplicate("market_2", signal))

    def test_cleanup_stale_dedupe_entries(self):
        """Test cleanup of stale deduplication entries."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        signal = DepthSignal(
            signal_type="thin_depth",
            triggered=True,
            reason="Test reason",
            metrics={"total_depth": 100.0},
        )

        # Mark signal as sent
        runner._mark_signal_sent("market_1", signal)

        # Verify entry exists
        signal_hash = runner._compute_signal_hash("market_1", signal)
        self.assertIn(signal_hash, runner._signal_dedupe)

        # Manually set timestamp to be stale
        from datetime import timedelta

        runner._signal_dedupe[signal_hash] = datetime.now() - timedelta(
            seconds=runner.DEDUPE_WINDOW_SECONDS * 3
        )

        # Run cleanup
        runner._cleanup_stale_dedupe_entries()

        # Entry should be removed
        self.assertNotIn(signal_hash, runner._signal_dedupe)

    def test_calculate_backoff(self):
        """Test exponential backoff calculation."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        # First retry: base_backoff * (2^0) = 2.0
        runner.retry_count = 0
        self.assertAlmostEqual(runner._calculate_backoff(), 2.0, places=2)

        # Second retry: base_backoff * (2^1) = 4.0
        runner.retry_count = 1
        self.assertAlmostEqual(runner._calculate_backoff(), 4.0, places=2)

        # Third retry: base_backoff * (2^2) = 8.0
        runner.retry_count = 2
        self.assertAlmostEqual(runner._calculate_backoff(), 8.0, places=2)

        # Should cap at MAX_BACKOFF_SECONDS
        runner.retry_count = 10
        self.assertLessEqual(runner._calculate_backoff(), runner.MAX_BACKOFF_SECONDS)

    def test_stop(self):
        """Test that stop() sets running to False."""
        runner = DepthScannerRunner(config_path=self.test_config_path)
        runner.running = True

        runner.stop()

        self.assertFalse(runner.running)

    @patch("scripts.run_depth_scanner.PolymarketAPIClient")
    @patch("scripts.run_depth_scanner.init_db")
    @patch("scripts.run_depth_scanner.log_depth_event")
    @patch("scripts.run_depth_scanner.send_depth_alert")
    def test_process_market_with_signals(
        self, mock_send_alert, mock_log_event, mock_init_db, mock_api_client_class
    ):
        """Test processing a market that triggers signals."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        # Setup mock API client
        mock_api_client = MagicMock()
        runner.api_client = mock_api_client

        # Create mock orderbook with thin depth (should trigger signal)
        mock_orderbook = MagicMock()
        mock_orderbook.yes_bids = [[0.45, 50.0]]
        mock_orderbook.yes_asks = [[0.55, 50.0]]
        mock_orderbook.no_bids = [[0.45, 50.0]]
        mock_orderbook.no_asks = [[0.55, 50.0]]
        mock_api_client.fetch_orderbook.return_value = mock_orderbook

        # Mock send_depth_alert to return False (notifications disabled)
        mock_send_alert.return_value = False

        # Load config
        from app.core.depth_scanner import load_depth_config

        depth_config = load_depth_config(self.test_config_path)

        # Process market
        runner._process_market("test_market_1", depth_config)

        # Verify API was called
        mock_api_client.fetch_orderbook.assert_called_once_with(
            "test_market_1", depth=10
        )

        # Verify signal was detected (thin depth with total 200 < 500)
        self.assertEqual(runner.stats["markets_scanned"], 1)
        self.assertGreater(runner.stats["signals_detected"], 0)

        # Verify logging was called
        self.assertTrue(mock_log_event.called)

    @patch("scripts.run_depth_scanner.PolymarketAPIClient")
    def test_process_market_no_orderbook(self, mock_api_client_class):
        """Test processing a market when orderbook fetch fails."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        # Setup mock API client that returns None
        mock_api_client = MagicMock()
        runner.api_client = mock_api_client
        mock_api_client.fetch_orderbook.return_value = None

        # Load config
        from app.core.depth_scanner import load_depth_config

        depth_config = load_depth_config(self.test_config_path)

        # Process market
        runner._process_market("test_market_1", depth_config)

        # Verify no signals were detected (market not scanned)
        self.assertEqual(runner.stats["markets_scanned"], 0)
        self.assertEqual(runner.stats["signals_detected"], 0)

    @patch("scripts.run_depth_scanner.PolymarketAPIClient")
    @patch("scripts.run_depth_scanner.init_db")
    @patch("scripts.run_depth_scanner.log_depth_event")
    @patch("scripts.run_depth_scanner.send_depth_alert")
    def test_signal_deduplication_in_process_market(
        self, mock_send_alert, mock_log_event, mock_init_db, mock_api_client_class
    ):
        """Test that duplicate signals are not sent again."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        # Setup mock API client
        mock_api_client = MagicMock()
        runner.api_client = mock_api_client

        # Create mock orderbook with thin depth
        mock_orderbook = MagicMock()
        mock_orderbook.yes_bids = [[0.45, 50.0]]
        mock_orderbook.yes_asks = [[0.55, 50.0]]
        mock_orderbook.no_bids = [[0.45, 50.0]]
        mock_orderbook.no_asks = [[0.55, 50.0]]
        mock_api_client.fetch_orderbook.return_value = mock_orderbook

        mock_send_alert.return_value = False

        from app.core.depth_scanner import load_depth_config

        depth_config = load_depth_config(self.test_config_path)

        # Process market first time
        runner._process_market("test_market_1", depth_config)
        first_signals_detected = runner.stats["signals_detected"]
        first_alerts_deduplicated = runner.stats["alerts_deduplicated"]

        # Process same market again (signals should be deduplicated)
        runner._process_market("test_market_1", depth_config)
        second_signals_detected = runner.stats["signals_detected"]
        second_alerts_deduplicated = runner.stats["alerts_deduplicated"]

        # More signals should be detected
        self.assertGreater(second_signals_detected, first_signals_detected)

        # More alerts should be deduplicated
        self.assertGreater(second_alerts_deduplicated, first_alerts_deduplicated)


class TestDepthScannerRunnerPrintSummary(unittest.TestCase):
    """Test DepthScannerRunner summary printing."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.test_dir, "test_depth_config.json")

        import json

        test_config = {
            "min_depth": 500.0,
            "max_gap": 0.10,
            "imbalance_ratio": 300.0,
            "markets_to_watch": [],
        }
        with open(self.test_config_path, "w") as f:
            json.dump(test_config, f)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_print_summary_with_stats(self):
        """Test summary printing with statistics."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        # Set some stats
        runner.stats["start_time"] = datetime.now()
        runner.stats["markets_scanned"] = 100
        runner.stats["signals_detected"] = 10
        runner.stats["alerts_sent"] = 5
        runner.stats["alerts_deduplicated"] = 3
        runner.stats["errors"] = 2

        # This should not raise an error
        runner._print_summary()

    def test_print_summary_no_start_time(self):
        """Test summary printing without start time."""
        runner = DepthScannerRunner(config_path=self.test_config_path)

        # No start time set
        runner.stats["start_time"] = None

        # This should not raise an error
        runner._print_summary()


class TestDepthScannerRunnerHeartbeat(unittest.TestCase):
    """Test DepthScannerRunner heartbeat functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.test_dir, "test_depth_config.json")

        import json

        test_config = {
            "min_depth": 500.0,
            "max_gap": 0.10,
            "imbalance_ratio": 300.0,
            "markets_to_watch": ["market_1"],
        }
        with open(self.test_config_path, "w") as f:
            json.dump(test_config, f)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_heartbeat_not_printed_before_interval(self):
        """Test heartbeat is not printed before interval."""
        import time

        runner = DepthScannerRunner(config_path=self.test_config_path)
        runner.heartbeat_interval = 60.0
        runner.last_heartbeat = time.time()
        runner.running = True

        # This should not print heartbeat (interval not elapsed)
        runner._print_heartbeat()

        # last_heartbeat should not change
        self.assertAlmostEqual(runner.last_heartbeat, time.time(), delta=1.0)

    def test_heartbeat_printed_after_interval(self):
        """Test heartbeat is printed after interval."""
        import time

        runner = DepthScannerRunner(config_path=self.test_config_path)
        runner.heartbeat_interval = 60.0
        runner.last_heartbeat = time.time() - 61  # More than 60 seconds ago
        runner.running = True

        # This should print heartbeat
        runner._print_heartbeat()

        # last_heartbeat should be updated
        self.assertAlmostEqual(runner.last_heartbeat, time.time(), delta=1.0)


if __name__ == "__main__":
    unittest.main()
