"""
Unit tests for price alert functionality.

Tests price alert creation, checking, and watching functionality.
"""

import unittest
from datetime import datetime
from app.core.price_alerts import (
    PriceAlert,
    create_price_alert,
    check_price_alert,
    watch_market_price,
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


if __name__ == "__main__":
    unittest.main()
