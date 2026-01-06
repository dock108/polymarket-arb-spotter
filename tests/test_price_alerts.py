"""
Unit tests for price alert functionality.

Tests price alert creation, checking, watching functionality,
and persistent JSON storage.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime
from app.core.price_alerts import (
    PriceAlert,
    create_price_alert,
    check_price_alert,
    watch_market_price,
    add_alert,
    remove_alert,
    list_alerts,
    _load_alerts,
    _save_alerts,
    _validate_market_id_format,
)


class TestPriceAlert(unittest.TestCase):
    """Test PriceAlert dataclass."""

    def test_price_alert_creation(self):
        """Test creating a PriceAlert object."""
        alert = PriceAlert(
            market_id="test_market_1",
            direction="above",
            target_price=0.75,
        )

        self.assertEqual(alert.market_id, "test_market_1")
        self.assertEqual(alert.direction, "above")
        self.assertEqual(alert.target_price, 0.75)
        self.assertIsNone(alert.current_price)
        self.assertFalse(alert.triggered)
        self.assertIsNone(alert.triggered_at)

    def test_price_alert_to_dict(self):
        """Test converting PriceAlert to dictionary."""
        alert = PriceAlert(
            market_id="test_market_1",
            direction="below",
            target_price=0.30,
            current_price=0.25,
            triggered=True,
            triggered_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        alert_dict = alert.to_dict()

        self.assertEqual(alert_dict["market_id"], "test_market_1")
        self.assertEqual(alert_dict["direction"], "below")
        self.assertEqual(alert_dict["target_price"], 0.30)
        self.assertEqual(alert_dict["current_price"], 0.25)
        self.assertTrue(alert_dict["triggered"])
        self.assertEqual(alert_dict["triggered_at"], "2024-01-01T12:00:00")


class TestCreatePriceAlert(unittest.TestCase):
    """Test create_price_alert function."""

    def test_create_alert_above(self):
        """Test creating an 'above' alert."""
        alert = create_price_alert("market_123", "above", 0.60)

        self.assertEqual(alert.market_id, "market_123")
        self.assertEqual(alert.direction, "above")
        self.assertEqual(alert.target_price, 0.60)
        self.assertFalse(alert.triggered)
        self.assertIn("above", alert.alert_message)

    def test_create_alert_below(self):
        """Test creating a 'below' alert."""
        alert = create_price_alert("market_456", "below", 0.40)

        self.assertEqual(alert.market_id, "market_456")
        self.assertEqual(alert.direction, "below")
        self.assertEqual(alert.target_price, 0.40)
        self.assertFalse(alert.triggered)
        self.assertIn("below", alert.alert_message)

    def test_create_alert_invalid_market_id(self):
        """Test that empty market_id raises ValueError."""
        with self.assertRaises(ValueError) as context:
            create_price_alert("", "above", 0.5)
        self.assertIn("market_id", str(context.exception))

    def test_create_alert_invalid_direction(self):
        """Test that invalid direction raises ValueError."""
        with self.assertRaises(ValueError) as context:
            create_price_alert("market_1", "sideways", 0.5)
        self.assertIn("direction", str(context.exception))

    def test_create_alert_invalid_price_type(self):
        """Test that non-numeric target_price raises ValueError."""
        with self.assertRaises(ValueError) as context:
            create_price_alert("market_1", "above", "not_a_number")
        self.assertIn("target_price", str(context.exception))

    def test_create_alert_price_out_of_range_negative(self):
        """Test that negative target_price raises ValueError."""
        with self.assertRaises(ValueError) as context:
            create_price_alert("market_1", "above", -0.5)
        self.assertIn("between 0 and 1", str(context.exception))

    def test_create_alert_price_out_of_range_high(self):
        """Test that target_price > 1 raises ValueError."""
        with self.assertRaises(ValueError) as context:
            create_price_alert("market_1", "above", 1.5)
        self.assertIn("between 0 and 1", str(context.exception))

    def test_create_alert_boundary_values(self):
        """Test creating alerts with boundary values (0 and 1)."""
        alert_zero = create_price_alert("market_1", "above", 0.0)
        self.assertEqual(alert_zero.target_price, 0.0)

        alert_one = create_price_alert("market_2", "below", 1.0)
        self.assertEqual(alert_one.target_price, 1.0)


class TestCheckPriceAlert(unittest.TestCase):
    """Test check_price_alert function."""

    def test_check_alert_above_triggered(self):
        """Test that 'above' alert triggers when price exceeds target."""
        alert = PriceAlert(
            market_id="market_1",
            direction="above",
            target_price=0.60,
        )

        result = check_price_alert(alert, 0.70)

        self.assertTrue(result.triggered)
        self.assertEqual(result.current_price, 0.70)
        self.assertIsNotNone(result.triggered_at)
        self.assertIn("above", result.alert_message)

    def test_check_alert_above_not_triggered(self):
        """Test that 'above' alert doesn't trigger when price is below target."""
        alert = PriceAlert(
            market_id="market_1",
            direction="above",
            target_price=0.60,
        )

        result = check_price_alert(alert, 0.50)

        self.assertFalse(result.triggered)
        self.assertEqual(result.current_price, 0.50)
        self.assertIsNone(result.triggered_at)
        self.assertIn("not triggered", result.alert_message)

    def test_check_alert_below_triggered(self):
        """Test that 'below' alert triggers when price falls below target."""
        alert = PriceAlert(
            market_id="market_2",
            direction="below",
            target_price=0.40,
        )

        result = check_price_alert(alert, 0.30)

        self.assertTrue(result.triggered)
        self.assertEqual(result.current_price, 0.30)
        self.assertIsNotNone(result.triggered_at)
        self.assertIn("below", result.alert_message)

    def test_check_alert_below_not_triggered(self):
        """Test that 'below' alert doesn't trigger when price is above target."""
        alert = PriceAlert(
            market_id="market_2",
            direction="below",
            target_price=0.40,
        )

        result = check_price_alert(alert, 0.50)

        self.assertFalse(result.triggered)
        self.assertEqual(result.current_price, 0.50)
        self.assertIsNone(result.triggered_at)
        self.assertIn("not triggered", result.alert_message)

    def test_check_alert_exact_target_price(self):
        """Test behavior when current price equals target price."""
        # For 'above', price must be strictly greater
        alert_above = PriceAlert(
            market_id="market_1",
            direction="above",
            target_price=0.50,
        )
        result_above = check_price_alert(alert_above, 0.50)
        self.assertFalse(result_above.triggered)

        # For 'below', price must be strictly less
        alert_below = PriceAlert(
            market_id="market_2",
            direction="below",
            target_price=0.50,
        )
        result_below = check_price_alert(alert_below, 0.50)
        self.assertFalse(result_below.triggered)

    def test_check_alert_invalid_current_price_type(self):
        """Test that non-numeric current_price raises ValueError."""
        alert = PriceAlert(
            market_id="market_1",
            direction="above",
            target_price=0.50,
        )

        with self.assertRaises(ValueError) as context:
            check_price_alert(alert, "not_a_number")
        self.assertIn("current_price", str(context.exception))

    def test_check_alert_current_price_out_of_range(self):
        """Test that current_price outside [0, 1] raises ValueError."""
        alert = PriceAlert(
            market_id="market_1",
            direction="above",
            target_price=0.50,
        )

        with self.assertRaises(ValueError):
            check_price_alert(alert, -0.1)

        with self.assertRaises(ValueError):
            check_price_alert(alert, 1.5)

    def test_check_alert_updates_existing_alert(self):
        """Test that checking alert multiple times updates it correctly."""
        alert = PriceAlert(
            market_id="market_1",
            direction="above",
            target_price=0.50,
        )

        # First check - not triggered
        result1 = check_price_alert(alert, 0.40)
        self.assertFalse(result1.triggered)

        # Second check - triggered
        result2 = check_price_alert(alert, 0.60)
        self.assertTrue(result2.triggered)
        self.assertIsNotNone(result2.triggered_at)


class TestWatchMarketPrice(unittest.TestCase):
    """Test watch_market_price function."""

    def test_watch_market_above_triggered(self):
        """Test watching market with 'above' alert that triggers."""
        market_data = {
            "id": "market_1",
            "name": "Test Market",
            "outcomes": [
                {"name": "Yes", "price": 0.75},
                {"name": "No", "price": 0.25},
            ],
        }

        alert = watch_market_price("market_1", "above", 0.60, market_data)

        self.assertEqual(alert.market_id, "market_1")
        self.assertTrue(alert.triggered)
        self.assertEqual(alert.current_price, 0.75)

    def test_watch_market_below_triggered(self):
        """Test watching market with 'below' alert that triggers."""
        market_data = {
            "id": "market_2",
            "name": "Test Market",
            "outcomes": [
                {"name": "Yes", "price": 0.25},
                {"name": "No", "price": 0.75},
            ],
        }

        alert = watch_market_price("market_2", "below", 0.40, market_data)

        self.assertEqual(alert.market_id, "market_2")
        self.assertTrue(alert.triggered)
        self.assertEqual(alert.current_price, 0.25)

    def test_watch_market_not_triggered(self):
        """Test watching market with alert that doesn't trigger."""
        market_data = {
            "id": "market_3",
            "name": "Test Market",
            "outcomes": [
                {"name": "Yes", "price": 0.50},
                {"name": "No", "price": 0.50},
            ],
        }

        alert = watch_market_price("market_3", "above", 0.70, market_data)

        self.assertEqual(alert.market_id, "market_3")
        self.assertFalse(alert.triggered)
        self.assertEqual(alert.current_price, 0.50)

    def test_watch_market_missing_outcomes(self):
        """Test that market_data without outcomes raises ValueError."""
        market_data = {"id": "market_1", "name": "Test Market"}

        with self.assertRaises(ValueError) as context:
            watch_market_price("market_1", "above", 0.5, market_data)
        self.assertIn("outcome", str(context.exception))

    def test_watch_market_empty_outcomes(self):
        """Test that market_data with empty outcomes raises ValueError."""
        market_data = {
            "id": "market_1",
            "name": "Test Market",
            "outcomes": [],
        }

        with self.assertRaises(ValueError) as context:
            watch_market_price("market_1", "above", 0.5, market_data)
        self.assertIn("outcome", str(context.exception))

    def test_watch_market_missing_price(self):
        """Test that outcome without price raises ValueError."""
        market_data = {
            "id": "market_1",
            "name": "Test Market",
            "outcomes": [
                {"name": "Yes"},  # Missing price
            ],
        }

        with self.assertRaises(ValueError) as context:
            watch_market_price("market_1", "above", 0.5, market_data)
        self.assertIn("price", str(context.exception))

    def test_watch_market_multiple_outcomes(self):
        """Test that watch_market uses first outcome's price."""
        market_data = {
            "id": "market_1",
            "name": "Test Market",
            "outcomes": [
                {"name": "Yes", "price": 0.60},
                {"name": "No", "price": 0.40},
                {"name": "Maybe", "price": 0.50},
            ],
        }

        alert = watch_market_price("market_1", "above", 0.55, market_data)

        # Should use first outcome's price (0.60)
        self.assertTrue(alert.triggered)
        self.assertEqual(alert.current_price, 0.60)


class TestMarketIdValidation(unittest.TestCase):
    """Test market ID validation."""

    def test_validate_valid_market_id(self):
        """Test that valid market IDs pass validation."""
        # Should not raise
        _validate_market_id_format("market_123")
        _validate_market_id_format("test_market")
        _validate_market_id_format("abc-def-123")

    def test_validate_empty_market_id(self):
        """Test that empty market_id raises ValueError."""
        with self.assertRaises(ValueError) as context:
            _validate_market_id_format("")
        self.assertIn("non-empty string", str(context.exception))

    def test_validate_whitespace_market_id(self):
        """Test that whitespace-only market_id raises ValueError."""
        with self.assertRaises(ValueError) as context:
            _validate_market_id_format("   ")
        self.assertIn("whitespace", str(context.exception))

    def test_validate_non_string_market_id(self):
        """Test that non-string market_id raises ValueError."""
        with self.assertRaises(ValueError):
            _validate_market_id_format(123)
        with self.assertRaises(ValueError):
            _validate_market_id_format(None)


class TestLoadSaveAlerts(unittest.TestCase):
    """Test _load_alerts and _save_alerts functions."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_alerts(self):
        """Test saving and loading alerts."""
        alerts = {
            "alert_1": {
                "id": "alert_1",
                "market_id": "market_123",
                "direction": "above",
                "target_price": 0.75,
                "created_at": "2024-01-01T12:00:00",
            },
            "alert_2": {
                "id": "alert_2",
                "market_id": "market_456",
                "direction": "below",
                "target_price": 0.30,
                "created_at": "2024-01-01T12:30:00",
            },
        }

        _save_alerts(alerts, self.storage_path)
        loaded_alerts = _load_alerts(self.storage_path)

        self.assertEqual(len(loaded_alerts), 2)
        self.assertEqual(loaded_alerts["alert_1"]["market_id"], "market_123")
        self.assertEqual(loaded_alerts["alert_2"]["direction"], "below")

    def test_load_empty_file(self):
        """Test loading from non-existent file creates empty dict."""
        loaded_alerts = _load_alerts(self.storage_path)
        self.assertEqual(loaded_alerts, {})
        # File should have been created
        self.assertTrue(os.path.exists(self.storage_path))

    def test_load_corrupted_file(self):
        """Test loading corrupted JSON file."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            f.write("invalid json {{{")

        loaded_alerts = _load_alerts(self.storage_path)
        self.assertEqual(loaded_alerts, {})
        # Backup should have been created
        self.assertTrue(os.path.exists(f"{self.storage_path}.backup"))


class TestAddAlert(unittest.TestCase):
    """Test add_alert function."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_alert_basic(self):
        """Test adding a basic alert."""
        alert_id = add_alert(
            "market_123",
            "above",
            0.75,
            storage_path=self.storage_path
        )

        self.assertIsNotNone(alert_id)
        self.assertTrue(len(alert_id) > 0)

        # Verify it was saved
        alerts = _load_alerts(self.storage_path)
        self.assertEqual(len(alerts), 1)
        self.assertIn(alert_id, alerts)
        self.assertEqual(alerts[alert_id]["market_id"], "market_123")
        self.assertEqual(alerts[alert_id]["direction"], "above")
        self.assertEqual(alerts[alert_id]["target_price"], 0.75)
        self.assertIn("created_at", alerts[alert_id])

    def test_add_alert_custom_id(self):
        """Test adding alert with custom ID."""
        alert_id = add_alert(
            "market_456",
            "below",
            0.30,
            alert_id="custom_id_123",
            storage_path=self.storage_path
        )

        self.assertEqual(alert_id, "custom_id_123")

        alerts = _load_alerts(self.storage_path)
        self.assertIn("custom_id_123", alerts)

    def test_add_multiple_alerts(self):
        """Test adding multiple alerts."""
        id1 = add_alert("market_1", "above", 0.60, storage_path=self.storage_path)
        id2 = add_alert("market_2", "below", 0.40, storage_path=self.storage_path)
        id3 = add_alert("market_3", "above", 0.80, storage_path=self.storage_path)

        alerts = _load_alerts(self.storage_path)
        self.assertEqual(len(alerts), 3)
        self.assertIn(id1, alerts)
        self.assertIn(id2, alerts)
        self.assertIn(id3, alerts)

    def test_add_alert_duplicate_id(self):
        """Test that duplicate alert ID raises error."""
        add_alert(
            "market_1",
            "above",
            0.50,
            alert_id="duplicate_id",
            storage_path=self.storage_path
        )

        with self.assertRaises(ValueError) as context:
            add_alert(
                "market_2",
                "below",
                0.30,
                alert_id="duplicate_id",
                storage_path=self.storage_path
            )
        self.assertIn("already exists", str(context.exception))

    def test_add_alert_invalid_price(self):
        """Test that invalid price raises error."""
        with self.assertRaises(ValueError):
            add_alert("market_1", "above", -0.5, storage_path=self.storage_path)

        with self.assertRaises(ValueError):
            add_alert("market_1", "above", 1.5, storage_path=self.storage_path)

    def test_add_alert_invalid_direction(self):
        """Test that invalid direction raises error."""
        with self.assertRaises(ValueError):
            add_alert("market_1", "sideways", 0.5, storage_path=self.storage_path)

    def test_add_alert_invalid_market_id(self):
        """Test that invalid market_id raises error."""
        with self.assertRaises(ValueError):
            add_alert("", "above", 0.5, storage_path=self.storage_path)

        with self.assertRaises(ValueError):
            add_alert("   ", "above", 0.5, storage_path=self.storage_path)


class TestRemoveAlert(unittest.TestCase):
    """Test remove_alert function."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_remove_alert_success(self):
        """Test removing an existing alert."""
        alert_id = add_alert(
            "market_123",
            "above",
            0.75,
            storage_path=self.storage_path
        )

        # Verify it exists
        alerts = _load_alerts(self.storage_path)
        self.assertEqual(len(alerts), 1)

        # Remove it
        result = remove_alert(alert_id, storage_path=self.storage_path)
        self.assertTrue(result)

        # Verify it's gone
        alerts = _load_alerts(self.storage_path)
        self.assertEqual(len(alerts), 0)

    def test_remove_alert_not_found(self):
        """Test removing non-existent alert returns False."""
        result = remove_alert("non_existent_id", storage_path=self.storage_path)
        self.assertFalse(result)

    def test_remove_one_of_many(self):
        """Test removing one alert among several."""
        id1 = add_alert("market_1", "above", 0.60, storage_path=self.storage_path)
        id2 = add_alert("market_2", "below", 0.40, storage_path=self.storage_path)
        id3 = add_alert("market_3", "above", 0.80, storage_path=self.storage_path)

        # Remove the middle one
        result = remove_alert(id2, storage_path=self.storage_path)
        self.assertTrue(result)

        # Verify others remain
        alerts = _load_alerts(self.storage_path)
        self.assertEqual(len(alerts), 2)
        self.assertIn(id1, alerts)
        self.assertIn(id3, alerts)
        self.assertNotIn(id2, alerts)


class TestListAlerts(unittest.TestCase):
    """Test list_alerts function."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_empty_alerts(self):
        """Test listing when no alerts exist."""
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(alerts, [])

    def test_list_single_alert(self):
        """Test listing a single alert."""
        add_alert("market_123", "above", 0.75, storage_path=self.storage_path)

        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["market_id"], "market_123")
        self.assertEqual(alerts[0]["direction"], "above")
        self.assertEqual(alerts[0]["target_price"], 0.75)

    def test_list_multiple_alerts(self):
        """Test listing multiple alerts."""
        add_alert("market_1", "above", 0.60, storage_path=self.storage_path)
        add_alert("market_2", "below", 0.40, storage_path=self.storage_path)
        add_alert("market_3", "above", 0.80, storage_path=self.storage_path)

        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 3)

        # Verify all markets are present
        market_ids = [a["market_id"] for a in alerts]
        self.assertIn("market_1", market_ids)
        self.assertIn("market_2", market_ids)
        self.assertIn("market_3", market_ids)

    def test_list_alerts_sorted_by_time(self):
        """Test that alerts are sorted by creation time (newest first)."""
        import time

        # Add alerts with slight delays
        add_alert(
            "market_1", "above", 0.60,
            alert_id="id1",
            storage_path=self.storage_path
        )
        time.sleep(0.01)
        add_alert(
            "market_2", "below", 0.40,
            alert_id="id2",
            storage_path=self.storage_path
        )
        time.sleep(0.01)
        add_alert(
            "market_3", "above", 0.80,
            alert_id="id3",
            storage_path=self.storage_path
        )

        alerts = list_alerts(storage_path=self.storage_path)

        # Newest should be first
        self.assertEqual(alerts[0]["id"], "id3")
        self.assertEqual(alerts[1]["id"], "id2")
        self.assertEqual(alerts[2]["id"], "id1")


class TestAlertPersistence(unittest.TestCase):
    """Test that alerts persist across restarts."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "data", "test_alerts.json")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_alerts_persist_across_sessions(self):
        """Test that alerts persist when reloading from file."""
        # Session 1: Add alerts
        id1 = add_alert("market_1", "above", 0.60, storage_path=self.storage_path)
        id2 = add_alert("market_2", "below", 0.40, storage_path=self.storage_path)

        # Session 2: Load alerts (simulating restart)
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 2)

        # Session 3: Add another alert
        id3 = add_alert("market_3", "above", 0.80, storage_path=self.storage_path)

        # Session 4: Verify all are present
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 3)

        ids = [a["id"] for a in alerts]
        self.assertIn(id1, ids)
        self.assertIn(id2, ids)
        self.assertIn(id3, ids)

    def test_remove_persists_across_sessions(self):
        """Test that removals persist."""
        # Add alerts
        id1 = add_alert("market_1", "above", 0.60, storage_path=self.storage_path)
        id2 = add_alert("market_2", "below", 0.40, storage_path=self.storage_path)

        # Remove one
        remove_alert(id1, storage_path=self.storage_path)

        # Reload (simulating restart)
        alerts = list_alerts(storage_path=self.storage_path)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["id"], id2)


if __name__ == "__main__":
    unittest.main()
