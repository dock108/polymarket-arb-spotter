"""
Unit tests for health heartbeat monitoring.
"""

import unittest
import time
import logging
from unittest.mock import MagicMock, patch
from io import StringIO

from app.core.logger import HealthHeartbeat, start_heartbeat


class TestHealthHeartbeat(unittest.TestCase):
    """Test HealthHeartbeat class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a test logger that captures output
        self.test_logger = logging.getLogger("test_heartbeat")
        self.test_logger.setLevel(logging.INFO)
        self.log_capture = StringIO()
        handler = logging.StreamHandler(self.log_capture)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.test_logger.addHandler(handler)

    def tearDown(self):
        """Clean up after tests."""
        self.test_logger.handlers.clear()

    def test_heartbeat_initialization(self):
        """Test that heartbeat initializes with correct settings."""
        heartbeat = HealthHeartbeat(interval=30)

        self.assertEqual(heartbeat.interval, 30)
        self.assertIsNone(heartbeat.callback)
        self.assertFalse(heartbeat._running)
        self.assertIsNone(heartbeat._thread)

    def test_heartbeat_start_stop(self):
        """Test that heartbeat can be started and stopped."""
        heartbeat = HealthHeartbeat(interval=1, logger_instance=self.test_logger)

        # Start heartbeat
        heartbeat.start()
        self.assertTrue(heartbeat._running)
        self.assertIsNotNone(heartbeat._thread)

        # Wait a bit for at least one heartbeat
        time.sleep(1.5)

        # Stop heartbeat
        heartbeat.stop()
        self.assertFalse(heartbeat._running)

        # Check that heartbeat was logged
        log_output = self.log_capture.getvalue()
        self.assertIn("Health heartbeat started", log_output)
        self.assertIn("HEARTBEAT", log_output)
        self.assertIn("Status: healthy", log_output)
        self.assertIn("Health heartbeat stopped", log_output)

    def test_heartbeat_with_callback(self):
        """Test heartbeat with custom callback providing metrics."""
        test_metrics = {"cpu": 45.2, "memory": 1024}

        def metrics_callback():
            return test_metrics

        heartbeat = HealthHeartbeat(
            interval=1, callback=metrics_callback, logger_instance=self.test_logger
        )

        heartbeat.start()
        time.sleep(1.5)
        heartbeat.stop()

        # Check that metrics were logged
        log_output = self.log_capture.getvalue()
        self.assertIn("HEARTBEAT", log_output)
        self.assertIn("Metrics:", log_output)
        self.assertIn("cpu", log_output)

    def test_heartbeat_callback_exception_handling(self):
        """Test that heartbeat handles callback exceptions gracefully."""

        def failing_callback():
            raise ValueError("Test error")

        heartbeat = HealthHeartbeat(
            interval=1, callback=failing_callback, logger_instance=self.test_logger
        )

        heartbeat.start()
        time.sleep(1.5)
        heartbeat.stop()

        # Check that error was logged but heartbeat continued
        log_output = self.log_capture.getvalue()
        self.assertIn("HEARTBEAT", log_output)
        self.assertIn("Error getting health metrics", log_output)

    def test_heartbeat_prevents_double_start(self):
        """Test that starting an already running heartbeat logs a warning."""
        heartbeat = HealthHeartbeat(interval=1, logger_instance=self.test_logger)

        heartbeat.start()
        heartbeat.start()  # Try to start again

        heartbeat.stop()

        log_output = self.log_capture.getvalue()
        self.assertIn("Heartbeat already running", log_output)

    def test_heartbeat_context_manager(self):
        """Test heartbeat can be used as a context manager."""
        with HealthHeartbeat(interval=1, logger_instance=self.test_logger) as heartbeat:
            self.assertTrue(heartbeat._running)
            time.sleep(1.5)

        # Should be stopped after exiting context
        self.assertFalse(heartbeat._running)

        log_output = self.log_capture.getvalue()
        self.assertIn("HEARTBEAT", log_output)

    def test_heartbeat_stops_gracefully_if_not_running(self):
        """Test that stopping a non-running heartbeat doesn't cause errors."""
        heartbeat = HealthHeartbeat(interval=1, logger_instance=self.test_logger)

        # Stop without starting
        heartbeat.stop()  # Should not raise any exception

    def test_start_heartbeat_helper(self):
        """Test the start_heartbeat convenience function."""
        heartbeat = start_heartbeat(interval=1, logger_instance=self.test_logger)

        # Should be running
        self.assertTrue(heartbeat._running)

        time.sleep(1.5)

        # Clean up
        heartbeat.stop()

        log_output = self.log_capture.getvalue()
        self.assertIn("HEARTBEAT", log_output)


class TestHeartbeatTiming(unittest.TestCase):
    """Test heartbeat timing accuracy."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_logger = logging.getLogger("test_timing")
        self.test_logger.setLevel(logging.INFO)
        self.log_capture = StringIO()
        handler = logging.StreamHandler(self.log_capture)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.test_logger.addHandler(handler)

    def tearDown(self):
        """Clean up after tests."""
        self.test_logger.handlers.clear()

    def test_heartbeat_interval_accuracy(self):
        """Test that heartbeat interval is approximately correct."""
        interval = 2
        heartbeat = HealthHeartbeat(interval=interval, logger_instance=self.test_logger)

        start_time = time.time()
        heartbeat.start()

        # Wait for a few heartbeats
        time.sleep(interval * 2.5)

        heartbeat.stop()
        elapsed = time.time() - start_time

        # Count heartbeats in log
        log_output = self.log_capture.getvalue()
        heartbeat_count = log_output.count("HEARTBEAT")

        # Should have approximately 2-3 heartbeats
        self.assertGreaterEqual(heartbeat_count, 2)
        self.assertLessEqual(heartbeat_count, 3)


class TestHeartbeatThreadSafety(unittest.TestCase):
    """Test heartbeat thread safety."""

    def test_multiple_heartbeats_independent(self):
        """Test that multiple heartbeat instances work independently."""
        logger1 = logging.getLogger("heartbeat1")
        logger2 = logging.getLogger("heartbeat2")

        logger1.setLevel(logging.INFO)
        logger2.setLevel(logging.INFO)

        capture1 = StringIO()
        capture2 = StringIO()

        handler1 = logging.StreamHandler(capture1)
        handler2 = logging.StreamHandler(capture2)

        logger1.addHandler(handler1)
        logger2.addHandler(handler2)

        heartbeat1 = HealthHeartbeat(interval=1, logger_instance=logger1)
        heartbeat2 = HealthHeartbeat(interval=1, logger_instance=logger2)

        heartbeat1.start()
        heartbeat2.start()

        time.sleep(1.5)

        heartbeat1.stop()
        heartbeat2.stop()

        # Both should have logged independently
        log1 = capture1.getvalue()
        log2 = capture2.getvalue()

        self.assertIn("HEARTBEAT", log1)
        self.assertIn("HEARTBEAT", log2)

        # Clean up
        logger1.handlers.clear()
        logger2.handlers.clear()


if __name__ == "__main__":
    unittest.main()
