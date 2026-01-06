"""
Comprehensive tests for price_alerts module.

This test suite explicitly demonstrates:
1. Threshold detection - alerts trigger when prices cross configured thresholds
2. Dedupe behavior - cooldown period prevents duplicate alert firing
3. Persistence file - JSON file storage and retrieval of alerts
4. Alert logging - proper logging when alerts are triggered

All tests use mock market data with no network calls.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.core.api_client import NormalizedOrderBook
from app.core.price_alerts import (
    PriceAlert,
    PriceAlertWatcher,
    create_price_alert,
    check_price_alert,
    watch_market_price,
    add_alert,
    remove_alert,
    list_alerts,
    _load_alerts,
)


class TestThresholdDetection(unittest.TestCase):
    """
    Test Suite 1: Threshold Detection

    Validates that price alerts correctly detect when market prices
    cross configured thresholds (above/below) using mock market data.
    """

    def test_threshold_above_triggered_with_mock_data(self):
        """Test 'above' threshold detection with mock market data."""
        # Mock market data with YES price at 0.72
        mock_market_data = {
            "id": "mock_market_001",
            "name": "Mock Election Market",
            "outcomes": [
                {"name": "Yes", "price": 0.72},
                {"name": "No", "price": 0.28},
            ],
        }

        # Watch market with 'above' threshold at 0.65
        alert = watch_market_price(
            market_id="mock_market_001",
            direction="above",
            target_price=0.65,
            market_data=mock_market_data,
        )

        # Verify threshold was crossed and alert triggered
        self.assertTrue(alert.triggered)
        self.assertEqual(alert.current_price, 0.72)
        self.assertGreater(alert.current_price, alert.target_price)
        self.assertIsNotNone(alert.triggered_at)
        self.assertIn("above", alert.alert_message.lower())

    def test_threshold_above_not_triggered_with_mock_data(self):
        """Test 'above' threshold NOT triggered when price below target."""
        # Mock market data with YES price at 0.58
        mock_market_data = {
            "id": "mock_market_002",
            "name": "Mock Sports Market",
            "outcomes": [
                {"name": "Yes", "price": 0.58},
                {"name": "No", "price": 0.42},
            ],
        }

        # Watch market with 'above' threshold at 0.65
        alert = watch_market_price(
            market_id="mock_market_002",
            direction="above",
            target_price=0.65,
            market_data=mock_market_data,
        )

        # Verify threshold was NOT crossed
        self.assertFalse(alert.triggered)
        self.assertEqual(alert.current_price, 0.58)
        self.assertLess(alert.current_price, alert.target_price)
        self.assertIsNone(alert.triggered_at)

    def test_threshold_below_triggered_with_mock_data(self):
        """Test 'below' threshold detection with mock market data."""
        # Mock market data with YES price at 0.22
        mock_market_data = {
            "id": "mock_market_003",
            "name": "Mock Weather Market",
            "outcomes": [
                {"name": "Yes", "price": 0.22},
                {"name": "No", "price": 0.78},
            ],
        }

        # Watch market with 'below' threshold at 0.30
        alert = watch_market_price(
            market_id="mock_market_003",
            direction="below",
            target_price=0.30,
            market_data=mock_market_data,
        )

        # Verify threshold was crossed and alert triggered
        self.assertTrue(alert.triggered)
        self.assertEqual(alert.current_price, 0.22)
        self.assertLess(alert.current_price, alert.target_price)
        self.assertIsNotNone(alert.triggered_at)
        self.assertIn("below", alert.alert_message.lower())

    def test_threshold_below_not_triggered_with_mock_data(self):
        """Test 'below' threshold NOT triggered when price above target."""
        # Mock market data with YES price at 0.45
        mock_market_data = {
            "id": "mock_market_004",
            "name": "Mock Crypto Market",
            "outcomes": [
                {"name": "Yes", "price": 0.45},
                {"name": "No", "price": 0.55},
            ],
        }

        # Watch market with 'below' threshold at 0.30
        alert = watch_market_price(
            market_id="mock_market_004",
            direction="below",
            target_price=0.30,
            market_data=mock_market_data,
        )

        # Verify threshold was NOT crossed
        self.assertFalse(alert.triggered)
        self.assertEqual(alert.current_price, 0.45)
        self.assertGreater(alert.current_price, alert.target_price)
        self.assertIsNone(alert.triggered_at)

    def test_threshold_exact_boundary_conditions(self):
        """Test threshold detection at exact boundary values."""
        # Test 'above' with price exactly at threshold (should NOT trigger)
        mock_data_exact = {
            "id": "mock_market_005",
            "outcomes": [{"name": "Yes", "price": 0.50}],
        }

        alert_above = watch_market_price(
            "mock_market_005", "above", 0.50, mock_data_exact
        )
        self.assertFalse(alert_above.triggered)

        # Test 'below' with price exactly at threshold (should NOT trigger)
        alert_below = watch_market_price(
            "mock_market_005", "below", 0.50, mock_data_exact
        )
        self.assertFalse(alert_below.triggered)

        # Test 'above' with price just above threshold (should trigger)
        mock_data_above = {
            "id": "mock_market_006",
            "outcomes": [{"name": "Yes", "price": 0.5001}],
        }
        alert_above_triggered = watch_market_price(
            "mock_market_006", "above", 0.50, mock_data_above
        )
        self.assertTrue(alert_above_triggered.triggered)

        # Test 'below' with price just below threshold (should trigger)
        mock_data_below = {
            "id": "mock_market_007",
            "outcomes": [{"name": "Yes", "price": 0.4999}],
        }
        alert_below_triggered = watch_market_price(
            "mock_market_007", "below", 0.50, mock_data_below
        )
        self.assertTrue(alert_below_triggered.triggered)

    def test_threshold_detection_with_multiple_outcomes(self):
        """Test that threshold detection uses first outcome price."""
        # Mock market data with multiple outcomes
        mock_market_data = {
            "id": "mock_market_008",
            "name": "Mock Multi-Outcome Market",
            "outcomes": [
                {"name": "Outcome A", "price": 0.75},  # First outcome
                {"name": "Outcome B", "price": 0.15},
                {"name": "Outcome C", "price": 0.10},
            ],
        }

        # Alert should use first outcome's price (0.75)
        alert = watch_market_price(
            market_id="mock_market_008",
            direction="above",
            target_price=0.70,
            market_data=mock_market_data,
        )

        self.assertTrue(alert.triggered)
        self.assertEqual(alert.current_price, 0.75)


class TestDedupeBehavior(unittest.TestCase):
    """
    Test Suite 2: Dedupe Behavior

    Validates that the price alert watcher prevents duplicate alerts
    using cooldown periods, even when prices continuously exceed thresholds.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

        # Create mock API client (no network calls)
        self.mock_api_client = MagicMock()
        self.mock_api_client.stop_websocket = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dedupe_prevents_immediate_duplicate_alerts(self):
        """Test that cooldown prevents immediate duplicate alerts."""
        # Add alert to storage
        add_alert(
            "mock_market_100",
            "above",
            0.60,
            alert_id="test_dedupe_001",
            storage_path=self.storage_path,
        )

        # Create watcher with 1-second cooldown
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,
        )

        # Track fired alerts
        fired_alerts = []
        watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Mock orderbook that triggers alert (price 0.71 > threshold 0.60)
        mock_orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="mock_market_100",
            timestamp=datetime.now(),
        )

        # Simulate first price update - should trigger
        watcher._running = True
        watcher._handle_price_update("mock_market_100", mock_orderbook)
        self.assertEqual(len(fired_alerts), 1, "First alert should fire")

        # Simulate second price update immediately - should NOT trigger (dedupe)
        watcher._handle_price_update("mock_market_100", mock_orderbook)
        self.assertEqual(len(fired_alerts), 1, "Second alert should be deduped")

        # Simulate third price update immediately - should still NOT trigger
        watcher._handle_price_update("mock_market_100", mock_orderbook)
        self.assertEqual(len(fired_alerts), 1, "Third alert should be deduped")

    def test_dedupe_allows_alert_after_cooldown_period(self):
        """Test that alert can fire again after cooldown period expires."""
        # Add alert to storage
        add_alert(
            "mock_market_101",
            "above",
            0.60,
            alert_id="test_dedupe_002",
            storage_path=self.storage_path,
        )

        # Create watcher with 0.5-second cooldown (short for testing)
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=0.5,
        )

        # Track fired alerts
        fired_alerts = []
        watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Mock orderbook that triggers alert
        mock_orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="mock_market_101",
            timestamp=datetime.now(),
        )

        # First alert - should fire
        watcher._running = True
        watcher._handle_price_update("mock_market_101", mock_orderbook)
        self.assertEqual(len(fired_alerts), 1, "First alert should fire")

        # Immediate second update - should NOT fire (within cooldown)
        watcher._handle_price_update("mock_market_101", mock_orderbook)
        self.assertEqual(len(fired_alerts), 1, "Alert should be deduped")

        # Wait for cooldown to expire
        time.sleep(0.6)

        # Third update after cooldown - should fire again
        watcher._handle_price_update("mock_market_101", mock_orderbook)
        self.assertEqual(len(fired_alerts), 2, "Alert should fire after cooldown")

    def test_dedupe_tracks_separate_cooldowns_per_alert(self):
        """Test that each alert has independent cooldown tracking."""
        # Add two different alerts
        add_alert(
            "mock_market_102",
            "above",
            0.60,
            alert_id="test_dedupe_003a",
            storage_path=self.storage_path,
        )
        add_alert(
            "mock_market_103",
            "below",
            0.40,
            alert_id="test_dedupe_003b",
            storage_path=self.storage_path,
        )

        # Create watcher with 1-second cooldown
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,
        )

        fired_alerts = []
        watcher.on_alert_triggered = lambda alert: fired_alerts.append(alert)

        # Mock orderbooks for both markets
        orderbook1 = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="mock_market_102",
            timestamp=datetime.now(),
        )
        orderbook2 = NormalizedOrderBook(
            yes_best_bid=0.34,
            yes_best_ask=0.36,
            no_best_bid=0.64,
            no_best_ask=0.66,
            market_id="mock_market_103",
            timestamp=datetime.now(),
        )

        watcher._running = True

        # Fire first alert
        watcher._handle_price_update("mock_market_102", orderbook1)
        self.assertEqual(len(fired_alerts), 1)

        # Fire second alert (different market, should not be affected by first cooldown)
        watcher._handle_price_update("mock_market_103", orderbook2)
        self.assertEqual(len(fired_alerts), 2)

        # Try to fire first alert again (should be blocked by cooldown)
        watcher._handle_price_update("mock_market_102", orderbook1)
        self.assertEqual(len(fired_alerts), 2)

        # Try to fire second alert again (should also be blocked by its cooldown)
        watcher._handle_price_update("mock_market_103", orderbook2)
        self.assertEqual(len(fired_alerts), 2)

    def test_dedupe_should_fire_alert_method(self):
        """Test _should_fire_alert method logic."""
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,
        )

        alert_id = "test_alert_id"

        # First time - should fire (no previous trigger)
        self.assertTrue(watcher._should_fire_alert(alert_id))

        # Record a trigger
        watcher._last_trigger_times[alert_id] = datetime.now()

        # Immediately after - should NOT fire (within cooldown)
        self.assertFalse(watcher._should_fire_alert(alert_id))

        # Simulate trigger in the past (beyond cooldown)
        watcher._last_trigger_times[alert_id] = datetime.now() - timedelta(seconds=1.5)

        # After cooldown - should fire again
        self.assertTrue(watcher._should_fire_alert(alert_id))


class TestPersistenceFile(unittest.TestCase):
    """
    Test Suite 3: Persistence File

    Validates that alerts are correctly saved to and loaded from JSON files,
    supporting create, read, update, and delete operations.
    """

    def setUp(self):
        """Set up temporary storage for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary storage."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_persistence_create_alert_writes_to_json_file(self):
        """Test that creating an alert writes to JSON file."""
        # Add alert (create)
        alert_id = add_alert(
            market_id="mock_market_200",
            direction="above",
            target_price=0.75,
            storage_path=self.storage_path,
        )

        # Verify file was created
        self.assertTrue(os.path.exists(self.storage_path))

        # Verify JSON structure
        with open(self.storage_path, "r") as f:
            data = json.load(f)

        self.assertIn(alert_id, data)
        self.assertEqual(data[alert_id]["market_id"], "mock_market_200")
        self.assertEqual(data[alert_id]["direction"], "above")
        self.assertEqual(data[alert_id]["target_price"], 0.75)
        self.assertIn("created_at", data[alert_id])

    def test_persistence_read_alerts_from_json_file(self):
        """Test that alerts can be read from JSON file."""
        # Create multiple alerts
        id1 = add_alert("market_201", "above", 0.60, storage_path=self.storage_path)
        id2 = add_alert("market_202", "below", 0.40, storage_path=self.storage_path)
        id3 = add_alert("market_203", "above", 0.80, storage_path=self.storage_path)

        # Read alerts (read)
        alerts = list_alerts(storage_path=self.storage_path)

        # Verify all alerts are present
        self.assertEqual(len(alerts), 3)
        alert_ids = [a["id"] for a in alerts]
        self.assertIn(id1, alert_ids)
        self.assertIn(id2, alert_ids)
        self.assertIn(id3, alert_ids)

    def test_persistence_update_alert_in_json_file(self):
        """Test that alerts can be updated (remove + add pattern)."""
        # Create initial alert
        id1 = add_alert("market_204", "above", 0.65, storage_path=self.storage_path)

        # Read it back
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["target_price"], 0.65)

        # "Update" by removing old and adding new (simulates update pattern)
        remove_alert(id1, storage_path=self.storage_path)
        id2 = add_alert("market_204", "above", 0.70, storage_path=self.storage_path)

        # Verify update
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["target_price"], 0.70)
        self.assertEqual(alerts[0]["id"], id2)

    def test_persistence_delete_alert_from_json_file(self):
        """Test that alerts can be deleted from JSON file."""
        # Create alerts
        id1 = add_alert("market_205", "above", 0.60, storage_path=self.storage_path)
        id2 = add_alert("market_206", "below", 0.40, storage_path=self.storage_path)

        # Verify both exist
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 2)

        # Delete one (delete)
        result = remove_alert(id1, storage_path=self.storage_path)
        self.assertTrue(result)

        # Verify deletion
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["id"], id2)

        # Verify file still exists and is valid JSON
        with open(self.storage_path, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertIn(id2, data)
        self.assertNotIn(id1, data)

    def test_persistence_survives_process_restart(self):
        """Test that alerts persist across simulated process restarts."""
        # Session 1: Create alerts
        id1 = add_alert("market_207", "above", 0.65, storage_path=self.storage_path)
        id2 = add_alert("market_208", "below", 0.35, storage_path=self.storage_path)

        # Simulate process restart by clearing in-memory state
        # (just re-read from file)
        alerts_after_restart = list_alerts(storage_path=self.storage_path)

        # Verify alerts survived
        self.assertEqual(len(alerts_after_restart), 2)
        alert_ids = [a["id"] for a in alerts_after_restart]
        self.assertIn(id1, alert_ids)
        self.assertIn(id2, alert_ids)

    def test_persistence_handles_corrupted_json_gracefully(self):
        """Test that corrupted JSON file is handled gracefully."""
        # Create directory
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        # Write corrupted JSON
        with open(self.storage_path, "w") as f:
            f.write("{invalid json content {{")

        # Try to load - should handle gracefully
        loaded_alerts = _load_alerts(self.storage_path)

        # Should return empty dict and create backup
        self.assertEqual(loaded_alerts, {})
        self.assertTrue(os.path.exists(f"{self.storage_path}.backup"))

    def test_persistence_json_file_format(self):
        """Test that JSON file has correct structure and formatting."""
        # Add alerts
        add_alert("market_209", "above", 0.70, storage_path=self.storage_path)
        add_alert("market_210", "below", 0.30, storage_path=self.storage_path)

        # Read and verify JSON structure
        with open(self.storage_path, "r") as f:
            content = f.read()
            data = json.loads(content)

        # Verify it's properly formatted (indented)
        self.assertIn("\n", content)  # Should have newlines (formatted)
        self.assertIn("  ", content)  # Should have indentation

        # Verify structure
        self.assertIsInstance(data, dict)
        for alert_id, alert_data in data.items():
            self.assertIsInstance(alert_id, str)
            self.assertIsInstance(alert_data, dict)
            self.assertIn("id", alert_data)
            self.assertIn("market_id", alert_data)
            self.assertIn("direction", alert_data)
            self.assertIn("target_price", alert_data)
            self.assertIn("created_at", alert_data)


class TestAlertLogging(unittest.TestCase):
    """
    Test Suite 4: Alert Logging

    Validates that alerts are properly logged when triggered,
    including log messages and callback invocations.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")
        self.mock_api_client = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("app.core.price_alerts.logger")
    def test_logging_alert_creation(self, mock_logger):
        """Test that alert creation is logged."""
        # Create alert
        create_price_alert("mock_market_300", "above", 0.75)

        # Verify logging occurred
        mock_logger.info.assert_called()
        call_args = str(mock_logger.info.call_args)
        self.assertIn("mock_market_300", call_args)
        self.assertIn("above", call_args)

    @patch("app.core.price_alerts.logger")
    def test_logging_alert_triggered(self, mock_logger):
        """Test that alert triggers are logged."""
        # Create and check alert
        alert = create_price_alert("mock_market_301", "above", 0.60)
        check_price_alert(alert, 0.75)  # Price above threshold

        # Verify trigger was logged
        mock_logger.info.assert_called()
        call_args_list = [str(call) for call in mock_logger.info.call_args_list]
        logged_text = " ".join(call_args_list)
        self.assertIn("triggered", logged_text.lower())

    @patch("app.core.price_alerts.logger")
    def test_logging_watcher_alert_fired(self, mock_logger):
        """Test that watcher logs when firing alerts."""
        # Add alert
        add_alert(
            "mock_market_302",
            "above",
            0.60,
            alert_id="test_log_001",
            storage_path=self.storage_path,
        )

        # Create watcher
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,
        )

        # Mock orderbook that triggers alert
        mock_orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="mock_market_302",
            timestamp=datetime.now(),
        )

        # Trigger alert
        watcher._running = True
        watcher._handle_price_update("mock_market_302", mock_orderbook)

        # Verify "ALERT FIRED" was logged
        mock_logger.info.assert_called()
        call_args_list = [str(call) for call in mock_logger.info.call_args_list]
        logged_text = " ".join(call_args_list)
        self.assertIn("ALERT FIRED", logged_text)
        self.assertIn("test_log_001", logged_text)

    def test_logging_callback_invocation(self):
        """Test that callback is invoked with correct alert data."""
        # Add alert
        add_alert(
            "mock_market_303",
            "below",
            0.40,
            storage_path=self.storage_path,
        )

        # Track callback invocations
        callback_calls = []

        def mock_callback(alert: PriceAlert):
            callback_calls.append(
                {
                    "market_id": alert.market_id,
                    "triggered": alert.triggered,
                    "current_price": alert.current_price,
                    "target_price": alert.target_price,
                    "message": alert.alert_message,
                }
            )

        # Create watcher with callback
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,
            on_alert_triggered=mock_callback,
        )

        # Mock orderbook that triggers alert
        mock_orderbook = NormalizedOrderBook(
            yes_best_bid=0.34,
            yes_best_ask=0.36,
            no_best_bid=0.64,
            no_best_ask=0.66,
            market_id="mock_market_303",
            timestamp=datetime.now(),
        )

        # Trigger alert
        watcher._running = True
        watcher._handle_price_update("mock_market_303", mock_orderbook)

        # Verify callback was invoked with correct data
        self.assertEqual(len(callback_calls), 1)
        self.assertEqual(callback_calls[0]["market_id"], "mock_market_303")
        self.assertTrue(callback_calls[0]["triggered"])
        self.assertEqual(callback_calls[0]["current_price"], 0.36)
        self.assertEqual(callback_calls[0]["target_price"], 0.40)
        self.assertIn("below", callback_calls[0]["message"].lower())

    @patch("app.core.price_alerts.logger")
    def test_logging_callback_exception_handling(self, mock_logger):
        """Test that callback exceptions are logged and don't crash watcher."""
        # Add alert
        add_alert(
            "mock_market_304",
            "above",
            0.60,
            storage_path=self.storage_path,
        )

        # Create callback that raises exception
        def failing_callback(alert):
            raise ValueError("Intentional test exception")

        # Create watcher with failing callback
        watcher = PriceAlertWatcher(
            api_client=self.mock_api_client,
            storage_path=self.storage_path,
            alert_cooldown=1.0,
            on_alert_triggered=failing_callback,
        )

        # Mock orderbook
        mock_orderbook = NormalizedOrderBook(
            yes_best_bid=0.69,
            yes_best_ask=0.71,
            no_best_bid=0.29,
            no_best_ask=0.31,
            market_id="mock_market_304",
            timestamp=datetime.now(),
        )

        # Trigger alert - should not crash
        watcher._running = True
        watcher._handle_price_update("mock_market_304", mock_orderbook)

        # Verify error was logged
        mock_logger.error.assert_called()
        call_args = str(mock_logger.error.call_args)
        self.assertIn("callback", call_args.lower())

    @patch("app.core.price_alerts.logger")
    def test_logging_add_and_remove_alerts(self, mock_logger):
        """Test that adding and removing alerts is logged."""
        # Add alert
        alert_id = add_alert(
            "mock_market_305",
            "above",
            0.75,
            storage_path=self.storage_path,
        )

        # Verify add was logged
        mock_logger.info.assert_called()
        call_args = str(mock_logger.info.call_args)
        self.assertIn("Added", call_args)
        self.assertIn(alert_id, call_args)

        # Remove alert
        remove_alert(alert_id, storage_path=self.storage_path)

        # Verify remove was logged
        call_args_list = [str(call) for call in mock_logger.info.call_args_list]
        logged_text = " ".join(call_args_list)
        self.assertIn("Removed", logged_text)
        self.assertIn(alert_id, logged_text)


class TestNoNetworkCalls(unittest.TestCase):
    """
    Test Suite 5: No Network Calls

    Validates that all tests use mock data and no actual network calls are made.
    """

    def test_mock_market_data_structure(self):
        """Test that mock market data has correct structure."""
        # Example mock market data
        mock_data = {
            "id": "mock_market_400",
            "name": "Test Market",
            "outcomes": [
                {"name": "Yes", "price": 0.65},
                {"name": "No", "price": 0.35},
            ],
        }

        # Verify structure
        self.assertIn("id", mock_data)
        self.assertIn("outcomes", mock_data)
        self.assertIsInstance(mock_data["outcomes"], list)
        self.assertGreater(len(mock_data["outcomes"]), 0)
        self.assertIn("price", mock_data["outcomes"][0])

        # Use in alert
        alert = watch_market_price("mock_market_400", "above", 0.60, mock_data)
        self.assertIsNotNone(alert)

    def test_mock_api_client_no_real_connection(self):
        """Test that mock API client doesn't make real connections."""
        # Create mock API client
        mock_client = MagicMock()
        mock_client.subscribe_to_markets = MagicMock()
        mock_client.stop_websocket = MagicMock()

        # Create watcher with mock client
        temp_dir = tempfile.mkdtemp()
        try:
            storage_path = os.path.join(temp_dir, "data", "test_alerts.json")
            add_alert("mock_market_401", "above", 0.60, storage_path=storage_path)

            watcher = PriceAlertWatcher(
                api_client=mock_client,
                storage_path=storage_path,
                alert_cooldown=1.0,
            )

            # Start watcher
            watcher.start()
            time.sleep(0.1)

            # Verify mock was called (not real network)
            mock_client.subscribe_to_markets.assert_called_once()

            # Stop watcher
            watcher.stop()
            mock_client.stop_websocket.assert_called()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_mock_orderbook_structure(self):
        """Test that mock orderbook data structure is correct."""
        # Create mock orderbook
        mock_orderbook = NormalizedOrderBook(
            yes_best_bid=0.64,
            yes_best_ask=0.66,
            no_best_bid=0.34,
            no_best_ask=0.36,
            market_id="mock_market_402",
            timestamp=datetime.now(),
        )

        # Verify structure
        self.assertIsNotNone(mock_orderbook.yes_best_ask)
        self.assertIsNotNone(mock_orderbook.market_id)
        self.assertEqual(mock_orderbook.market_id, "mock_market_402")
        self.assertGreater(mock_orderbook.yes_best_ask, 0)
        self.assertLess(mock_orderbook.yes_best_ask, 1)


if __name__ == "__main__":
    unittest.main()
