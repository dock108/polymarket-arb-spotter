"""
Unit tests for price alert logging functionality in logger.py.

Tests database initialization, event logging, and data retrieval
for the price alert event logging system.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime
from sqlite_utils import Database

from app.core.logger import (
    init_db,
    log_price_alert_event,
    fetch_recent_price_alerts,
    fetch_recent,
)


class TestPriceAlertLogger(unittest.TestCase):
    """Test price alert event logging system."""

    def setUp(self):
        """Set up test database for each test."""
        # Create a temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_arb_logs.sqlite")

    def tearDown(self):
        """Clean up test database after each test."""
        # Remove test database file
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        # Remove test directory and any subdirectories
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_init_db_creates_price_alert_table(self):
        """Test that init_db creates the price_alert_events table with correct schema."""
        # Initialize database
        init_db(self.test_db_path)

        # Verify database file was created
        self.assertTrue(os.path.exists(self.test_db_path))

        # Verify table schema
        db = Database(self.test_db_path)
        self.assertIn("price_alert_events", db.table_names())

        # Verify columns
        table = db["price_alert_events"]
        columns = {col.name for col in table.columns}
        expected_columns = {
            "id",
            "timestamp",
            "alert_id",
            "market_id",
            "direction",
            "target_price",
            "trigger_price",
            "mode",
            "latency_ms",
        }
        self.assertEqual(columns, expected_columns)

    def test_init_db_creates_both_tables(self):
        """Test that init_db creates both arbitrage and price alert tables."""
        # Initialize database
        init_db(self.test_db_path)

        # Verify both tables exist
        db = Database(self.test_db_path)
        self.assertIn("arbitrage_events", db.table_names())
        self.assertIn("price_alert_events", db.table_names())

    def test_log_price_alert_event(self):
        """Test that log_price_alert_event successfully adds data to the database."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample price alert event data
        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "alert_id": "alert_123",
            "market_id": "market_456",
            "direction": "above",
            "target_price": 0.65,
            "trigger_price": 0.68,
            "mode": "live",
            "latency_ms": 150,
        }

        # Log the event
        log_price_alert_event(event_data, self.test_db_path)

        # Verify data was inserted
        db = Database(self.test_db_path)
        rows = list(db["price_alert_events"].rows)
        self.assertEqual(len(rows), 1)

        # Verify data matches
        row = rows[0]
        self.assertEqual(row["timestamp"], "2024-01-05T12:00:00")
        self.assertEqual(row["alert_id"], "alert_123")
        self.assertEqual(row["market_id"], "market_456")
        self.assertEqual(row["direction"], "above")
        self.assertEqual(row["target_price"], 0.65)
        self.assertEqual(row["trigger_price"], 0.68)
        self.assertEqual(row["mode"], "live")
        self.assertEqual(row["latency_ms"], 150)

    def test_log_price_alert_event_with_datetime(self):
        """Test that log_price_alert_event handles datetime objects correctly."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample event data with datetime object
        timestamp = datetime(2024, 1, 5, 14, 30, 45)
        event_data = {
            "timestamp": timestamp,
            "alert_id": "alert_789",
            "market_id": "market_abc",
            "direction": "below",
            "target_price": 0.35,
            "trigger_price": 0.32,
            "mode": "mock",
            "latency_ms": 200,
        }

        # Log the event
        log_price_alert_event(event_data, self.test_db_path)

        # Verify data was inserted with timestamp converted to string
        db = Database(self.test_db_path)
        rows = list(db["price_alert_events"].rows)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["timestamp"], "2024-01-05T14:30:45")
        self.assertEqual(row["alert_id"], "alert_789")

    def test_log_multiple_price_alert_events(self):
        """Test logging multiple price alert events."""
        # Initialize database
        init_db(self.test_db_path)

        # Log multiple events
        events = [
            {
                "timestamp": "2024-01-05T10:00:00",
                "alert_id": "alert_1",
                "market_id": "market_1",
                "direction": "above",
                "target_price": 0.70,
                "trigger_price": 0.72,
                "mode": "live",
                "latency_ms": 100,
            },
            {
                "timestamp": "2024-01-05T11:00:00",
                "alert_id": "alert_2",
                "market_id": "market_2",
                "direction": "below",
                "target_price": 0.30,
                "trigger_price": 0.28,
                "mode": "live",
                "latency_ms": 120,
            },
            {
                "timestamp": "2024-01-05T12:00:00",
                "alert_id": "alert_3",
                "market_id": "market_3",
                "direction": "above",
                "target_price": 0.50,
                "trigger_price": 0.55,
                "mode": "mock",
                "latency_ms": 90,
            },
        ]

        for event in events:
            log_price_alert_event(event, self.test_db_path)

        # Verify all events were inserted
        db = Database(self.test_db_path)
        rows = list(db["price_alert_events"].rows)
        self.assertEqual(len(rows), 3)

    def test_fetch_recent_price_alerts_empty_database(self):
        """Test fetch_recent_price_alerts returns empty list for empty database."""
        # Initialize database
        init_db(self.test_db_path)

        # Fetch recent events
        results = fetch_recent_price_alerts(limit=10, db_path=self.test_db_path)

        # Verify empty list is returned
        self.assertEqual(results, [])

    def test_fetch_recent_price_alerts_no_table(self):
        """Test fetch_recent_price_alerts returns empty list when table doesn't exist."""
        # Create database without initializing table
        Database(self.test_db_path)

        # Fetch recent events
        results = fetch_recent_price_alerts(limit=10, db_path=self.test_db_path)

        # Verify empty list is returned
        self.assertEqual(results, [])

    def test_fetch_recent_price_alerts_single_entry(self):
        """Test fetch_recent_price_alerts retrieves a single entry correctly."""
        # Initialize database and log an event
        init_db(self.test_db_path)

        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "alert_id": "alert_single",
            "market_id": "market_single",
            "direction": "above",
            "target_price": 0.60,
            "trigger_price": 0.62,
            "mode": "live",
            "latency_ms": 150,
        }
        log_price_alert_event(event_data, self.test_db_path)

        # Fetch recent events
        results = fetch_recent_price_alerts(limit=10, db_path=self.test_db_path)

        # Verify one entry is returned
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["alert_id"], "alert_single")
        self.assertEqual(results[0]["market_id"], "market_single")

    def test_fetch_recent_price_alerts_order(self):
        """Test fetch_recent_price_alerts returns entries in correct order (most recent first)."""
        # Initialize database
        init_db(self.test_db_path)

        # Log multiple events with different timestamps
        events = [
            {
                "timestamp": "2024-01-05T10:00:00",
                "alert_id": "alert_1",
                "market_id": "market_1",
                "direction": "above",
                "target_price": 0.70,
                "trigger_price": 0.72,
                "mode": "live",
                "latency_ms": 100,
            },
            {
                "timestamp": "2024-01-05T12:00:00",
                "alert_id": "alert_2",
                "market_id": "market_2",
                "direction": "below",
                "target_price": 0.30,
                "trigger_price": 0.28,
                "mode": "live",
                "latency_ms": 120,
            },
            {
                "timestamp": "2024-01-05T11:00:00",
                "alert_id": "alert_3",
                "market_id": "market_3",
                "direction": "above",
                "target_price": 0.50,
                "trigger_price": 0.55,
                "mode": "mock",
                "latency_ms": 90,
            },
        ]

        for event in events:
            log_price_alert_event(event, self.test_db_path)

        # Fetch recent events
        results = fetch_recent_price_alerts(limit=10, db_path=self.test_db_path)

        # Verify order (most recent first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["alert_id"], "alert_2")  # Latest (12:00)
        self.assertEqual(results[1]["alert_id"], "alert_3")  # Middle (11:00)
        self.assertEqual(results[2]["alert_id"], "alert_1")  # Earliest (10:00)

    def test_fetch_recent_price_alerts_limit(self):
        """Test fetch_recent_price_alerts respects the limit parameter."""
        # Initialize database
        init_db(self.test_db_path)

        # Log 10 events
        for i in range(10):
            event_data = {
                "timestamp": f"2024-01-05T{10+i:02d}:00:00",
                "alert_id": f"alert_{i}",
                "market_id": f"market_{i}",
                "direction": "above" if i % 2 == 0 else "below",
                "target_price": 0.50 + (i * 0.05),
                "trigger_price": 0.52 + (i * 0.05),
                "mode": "live",
                "latency_ms": 100 + i,
            }
            log_price_alert_event(event_data, self.test_db_path)

        # Fetch with limit of 5
        results = fetch_recent_price_alerts(limit=5, db_path=self.test_db_path)

        # Verify only 5 entries are returned
        self.assertEqual(len(results), 5)

        # Verify they are the most recent 5
        for i, result in enumerate(results):
            expected_alert_id = f"alert_{9-i}"  # Most recent first
            self.assertEqual(result["alert_id"], expected_alert_id)

    def test_fetch_recent_price_alerts_default_limit(self):
        """Test fetch_recent_price_alerts uses default limit of 100."""
        # Initialize database
        init_db(self.test_db_path)

        # Log 5 events (less than default limit)
        for i in range(5):
            event_data = {
                "timestamp": f"2024-01-05T{10+i:02d}:00:00",
                "alert_id": f"alert_{i}",
                "market_id": f"market_{i}",
                "direction": "above",
                "target_price": 0.60,
                "trigger_price": 0.62,
                "mode": "mock",
                "latency_ms": 100,
            }
            log_price_alert_event(event_data, self.test_db_path)

        # Fetch without specifying limit
        results = fetch_recent_price_alerts(db_path=self.test_db_path)

        # Verify all 5 entries are returned
        self.assertEqual(len(results), 5)

    def test_price_alert_events_independent_from_arbitrage_events(self):
        """Test that price alert events and arbitrage events are stored separately."""
        # Initialize database
        init_db(self.test_db_path)

        # Log a price alert event
        price_alert_data = {
            "timestamp": "2024-01-05T12:00:00",
            "alert_id": "alert_123",
            "market_id": "market_456",
            "direction": "above",
            "target_price": 0.65,
            "trigger_price": 0.68,
            "mode": "live",
            "latency_ms": 150,
        }
        log_price_alert_event(price_alert_data, self.test_db_path)

        # Verify price alert events table has 1 entry
        price_alerts = fetch_recent_price_alerts(db_path=self.test_db_path)
        self.assertEqual(len(price_alerts), 1)

        # Verify arbitrage events table is still empty
        arb_events = fetch_recent(db_path=self.test_db_path)
        self.assertEqual(len(arb_events), 0)


if __name__ == "__main__":
    unittest.main()
