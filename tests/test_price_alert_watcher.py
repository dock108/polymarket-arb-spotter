"""
Unit tests for PriceAlertWatcher functionality.

Tests the watcher's ability to subscribe to markets, monitor prices,
fire alerts when thresholds are crossed, and prevent duplicate alerts.
"""

import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

from app.core.api_client import NormalizedOrderBook
from app.core.price_alerts import (
    PriceAlertWatcher,
    PriceAlert,
    add_alert,
    list_alerts,
)


class TestPriceAlertWatcher(unittest.TestCase):
    """Test PriceAlertWatcher class."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

        # Create mock API client
        self.mock_api_client = MagicMock()
        self.mock_api_client.stop_websocket = MagicMock()

        # Create watcher with short cooldown for testing
        self.watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,  # 1 second for testing
        )

    def tearDown(self):
        """Clean up temporary files and stop watcher."""
        if self.watcher.is_running():
            self.watcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_watcher_initialization(self):
        """Test that watcher initializes correctly."""
        self.assertFalse(self.watcher.is_running())
        self.assertEqual(self.watcher.alert_cooldown, 1.0)
        self.assertEqual(self.watcher.storage_path, self.storage_path)
        self.assertIsNotNone(self.watcher.api_client)

    def test_watcher_with_no_alerts(self):
        """Test starting watcher with no alerts."""
        # Should handle gracefully
        self.watcher.start()
        time.sleep(0.1)

        # Should not have started thread since no markets to watch
        self.assertFalse(self.watcher.is_running())

    def test_watcher_start_and_stop(self):
        """Test starting and stopping the watcher."""
        # Add an alert
        add_alert("market_123", "above", 0.60, storage_path=self.storage_path)

        # Mock subscribe_to_markets to not actually connect
        def mock_subscribe(*args, **kwargs):
            while self.watcher._running:
                time.sleep(0.1)

        self.mock_api_client.subscribe_to_markets = mock_subscribe

        # Start watcher
        self.watcher.start()
        time.sleep(0.2)

        self.assertTrue(self.watcher.is_running())

        # Stop watcher
        self.watcher.stop()
        time.sleep(0.2)

        self.assertFalse(self.watcher.is_running())

    def test_watcher_start_already_running(self):
        """Test that starting an already running watcher logs warning."""
        add_alert("market_123", "above", 0.60, storage_path=self.storage_path)

        def mock_subscribe(*args, **kwargs):
            while self.watcher._running:
                time.sleep(0.1)

        self.mock_api_client.subscribe_to_markets = mock_subscribe

        self.watcher.start()
        time.sleep(0.1)

        # Try to start again
        with patch("app.core.price_alerts.logger") as mock_logger:
            self.watcher.start()
            mock_logger.warning.assert_called()

        self.watcher.stop()

    def test_handle_price_update_triggers_alert(self):
        """Test that price updates trigger alerts when conditions are met."""
        # Add an "above" alert
        add_alert("market_123", "above", 0.60, storage_path=self.storage_path)

        # Create a mock orderbook with price above threshold
        orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="market_123",
            timestamp=datetime.now(),
        )

        # Track fired alerts
        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Simulate price update
        self.watcher._running = True
        self.watcher._handle_price_update("market_123", orderbook)

        # Should have fired one alert
        self.assertEqual(len(fired_alerts), 1)
        self.assertTrue(fired_alerts[0].triggered)
        self.assertEqual(fired_alerts[0].market_id, "market_123")
        self.assertEqual(fired_alerts[0].current_price, 0.71)

    def test_handle_price_update_does_not_trigger_below_threshold(self):
        """Test that alerts don't trigger when price is below threshold."""
        # Add an "above" alert
        add_alert("market_123", "above", 0.80, storage_path=self.storage_path)

        # Create a mock orderbook with price below threshold
        orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="market_123",
            timestamp=datetime.now(),
        )

        # Track fired alerts
        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Simulate price update
        self.watcher._running = True
        self.watcher._handle_price_update("market_123", orderbook)

        # Should not have fired any alerts
        self.assertEqual(len(fired_alerts), 0)

    def test_handle_price_update_below_alert(self):
        """Test that 'below' alerts trigger correctly."""
        # Add a "below" alert
        add_alert("market_456", "below", 0.30, storage_path=self.storage_path)

        # Create a mock orderbook with price below threshold
        orderbook = NormalizedOrderBook(
            yes_best_bid=0.24,
            yes_best_ask=0.26,
            no_best_bid=0.74,
            no_best_ask=0.76,
            market_id="market_456",
            timestamp=datetime.now(),
        )

        # Track fired alerts
        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Simulate price update
        self.watcher._running = True
        self.watcher._handle_price_update("market_456", orderbook)

        # Should have fired one alert
        self.assertEqual(len(fired_alerts), 1)
        self.assertTrue(fired_alerts[0].triggered)
        self.assertEqual(fired_alerts[0].direction, "below")

    def test_cooldown_prevents_duplicate_alerts(self):
        """Test that cooldown period prevents duplicate alerts."""
        # Add an alert
        alert_id = add_alert(
            "market_123",
            "above",
            0.60,
            alert_id="test_alert_1",
            storage_path=self.storage_path,
        )

        # Create a mock orderbook that triggers the alert
        orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="market_123",
            timestamp=datetime.now(),
        )

        # Track fired alerts
        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Simulate first price update
        self.watcher._running = True
        self.watcher._handle_price_update("market_123", orderbook)

        # Should have fired one alert
        self.assertEqual(len(fired_alerts), 1)

        # Simulate immediate second update (within cooldown)
        self.watcher._handle_price_update("market_123", orderbook)

        # Should still be only one alert (duplicate prevented)
        self.assertEqual(len(fired_alerts), 1)

        # Wait for cooldown period to pass
        time.sleep(1.1)

        # Simulate third update (after cooldown)
        self.watcher._handle_price_update("market_123", orderbook)

        # Should now have two alerts
        self.assertEqual(len(fired_alerts), 2)

    def test_should_fire_alert_first_time(self):
        """Test that alert fires the first time."""
        should_fire = self.watcher._should_fire_alert("new_alert_id")
        self.assertTrue(should_fire)

    def test_should_fire_alert_within_cooldown(self):
        """Test that alert doesn't fire within cooldown period."""
        alert_id = "test_alert"

        # Fire alert
        self.watcher._last_trigger_times[alert_id] = datetime.now()

        # Check immediately (within cooldown)
        should_fire = self.watcher._should_fire_alert(alert_id)
        self.assertFalse(should_fire)

    def test_should_fire_alert_after_cooldown(self):
        """Test that alert fires after cooldown period."""
        alert_id = "test_alert"

        # Fire alert in the past (before cooldown)
        self.watcher._last_trigger_times[alert_id] = datetime.now() - timedelta(
            seconds=2
        )

        # Check after cooldown (1 second)
        should_fire = self.watcher._should_fire_alert(alert_id)
        self.assertTrue(should_fire)

    def test_fire_alert_updates_trigger_time(self):
        """Test that firing alert updates the last trigger time."""
        alert = PriceAlert(
            market_id="market_123",
            direction="above",
            target_price=0.60,
            current_price=0.70,
            triggered=True,
            triggered_at=datetime.now(),
        )

        alert_id = "test_alert"

        # Fire alert
        self.watcher._fire_alert(alert_id, alert)

        # Check that trigger time was recorded
        self.assertIn(alert_id, self.watcher._last_trigger_times)
        self.assertIsNotNone(self.watcher._last_trigger_times[alert_id])

    def test_fire_alert_calls_callback(self):
        """Test that firing alert calls the callback function."""
        callback_called = []

        def mock_callback(alert):
            callback_called.append(alert)

        self.watcher.on_alert_triggered = mock_callback

        alert = PriceAlert(
            market_id="market_123",
            direction="above",
            target_price=0.60,
            current_price=0.70,
            triggered=True,
            triggered_at=datetime.now(),
        )

        self.watcher._fire_alert("test_alert", alert)

        # Callback should have been called once
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0].market_id, "market_123")

    def test_fire_alert_handles_callback_exception(self):
        """Test that alert still fires even if callback raises exception."""

        def mock_callback(alert):
            raise ValueError("Test error")

        self.watcher.on_alert_triggered = mock_callback

        alert = PriceAlert(
            market_id="market_123",
            direction="above",
            target_price=0.60,
            current_price=0.70,
            triggered=True,
            triggered_at=datetime.now(),
        )

        # Should not raise exception
        with patch("app.core.price_alerts.logger") as mock_logger:
            self.watcher._fire_alert("test_alert", alert)
            # Should log error
            mock_logger.error.assert_called()

    def test_handle_price_update_no_price_available(self):
        """Test handling price update when orderbook has no price."""
        add_alert("market_123", "above", 0.60, storage_path=self.storage_path)

        # Create orderbook with no price
        orderbook = NormalizedOrderBook(
            yes_best_bid=None,
            yes_best_ask=None,
            no_best_bid=None,
            no_best_ask=None,
            market_id="market_123",
            timestamp=datetime.now(),
        )

        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        self.watcher._running = True
        self.watcher._handle_price_update("market_123", orderbook)

        # Should not fire any alerts
        self.assertEqual(len(fired_alerts), 0)

    def test_handle_price_update_no_alerts_for_market(self):
        """Test handling price update for market with no alerts."""
        # Add alert for different market
        add_alert("market_999", "above", 0.60, storage_path=self.storage_path)

        orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="market_123",
            timestamp=datetime.now(),
        )

        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        self.watcher._running = True
        self.watcher._handle_price_update("market_123", orderbook)

        # Should not fire any alerts
        self.assertEqual(len(fired_alerts), 0)

    def test_handle_price_update_multiple_alerts_same_market(self):
        """Test handling multiple alerts for the same market."""
        # Add two alerts for the same market
        add_alert("market_123", "above", 0.60, storage_path=self.storage_path)
        add_alert("market_123", "below", 0.40, storage_path=self.storage_path)

        # Price is 0.71, should trigger "above" but not "below"
        orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="market_123",
            timestamp=datetime.now(),
        )

        fired_alerts = []
        self.watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        self.watcher._running = True
        self.watcher._handle_price_update("market_123", orderbook)

        # Should have fired one alert (the "above" one)
        self.assertEqual(len(fired_alerts), 1)
        self.assertEqual(fired_alerts[0].direction, "above")

    def test_handle_error(self):
        """Test error handler logs errors."""
        error = Exception("Test error")

        with patch("app.core.price_alerts.logger") as mock_logger:
            self.watcher._handle_error(error)
            mock_logger.error.assert_called()

    def test_reload_alerts(self):
        """Test reload_alerts method."""
        # Currently just logs, but should not raise
        with patch("app.core.price_alerts.logger") as mock_logger:
            self.watcher.reload_alerts()
            mock_logger.info.assert_called()


class TestPriceAlertWatcherIntegration(unittest.TestCase):
    """Integration tests for PriceAlertWatcher with mock WebSocket."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_watcher_with_mock_subscription(self):
        """Test watcher with mocked subscription that simulates price updates."""
        # Add alerts
        add_alert("market_123", "above", 0.60, storage_path=self.storage_path)
        add_alert("market_456", "below", 0.40, storage_path=self.storage_path)

        # Create mock API client
        mock_api_client = MagicMock()

        # Track fired alerts
        fired_alerts = []

        def mock_callback(alert):
            fired_alerts.append(alert)

        # Create watcher
        watcher = PriceAlertWatcher(
            api_client=mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=0.5,
            on_alert_triggered=mock_callback,
        )

        # Mock subscribe_to_markets to simulate price updates
        def mock_subscribe(market_ids, on_price_update, on_error):
            # Simulate updates for both markets
            orderbook1 = NormalizedOrderBook(
                yes_best_bid=0.69,
                yes_best_ask=0.71,
                no_best_bid=0.29,
                no_best_ask=0.31,
                market_id="market_123",
                timestamp=datetime.now(),
            )
            on_price_update("market_123", orderbook1)

            orderbook2 = NormalizedOrderBook(
                yes_best_bid=0.34,
                yes_best_ask=0.36,
                no_best_bid=0.64,
                no_best_ask=0.66,
                market_id="market_456",
                timestamp=datetime.now(),
            )
            on_price_update("market_456", orderbook2)

        mock_api_client.subscribe_to_markets = mock_subscribe

        # Start watcher
        watcher._running = True
        watcher._watch_loop(["market_123", "market_456"])

        # Both alerts should have fired
        self.assertEqual(len(fired_alerts), 2)

        market_ids = [alert.market_id for alert in fired_alerts]
        self.assertIn("market_123", market_ids)
        self.assertIn("market_456", market_ids)


if __name__ == "__main__":
    unittest.main()
