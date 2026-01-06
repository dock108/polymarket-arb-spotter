"""
Unit tests for depth event logging functionality in logger.py.

Tests database initialization, event logging, and data retrieval
for the depth event logging system.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime
from sqlite_utils import Database

from app.core.logger import (
    init_db,
    log_depth_event,
    fetch_recent_depth_events,
    fetch_recent,
    _get_table_columns,
)


class TestDepthEventLogger(unittest.TestCase):
    """Test depth event logging system."""

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

    def test_init_db_creates_depth_events_table(self):
        """Test that init_db creates the depth_events table with correct schema."""
        # Initialize database
        init_db(self.test_db_path)

        # Verify database file was created
        self.assertTrue(os.path.exists(self.test_db_path))

        # Verify table schema
        db = Database(self.test_db_path)
        self.assertIn("depth_events", db.table_names())

        # Verify columns
        table = db["depth_events"]
        columns = {col.name for col in table.columns}
        expected_columns = {
            "id",
            "timestamp",
            "market_id",
            "metrics",
            "signal_type",
            "threshold_hit",
            "mode",
        }
        self.assertEqual(columns, expected_columns)

    def test_init_db_creates_all_tables(self):
        """Test that init_db creates all three tables."""
        # Initialize database
        init_db(self.test_db_path)

        # Verify all tables exist
        db = Database(self.test_db_path)
        self.assertIn("arbitrage_events", db.table_names())
        self.assertIn("price_alert_events", db.table_names())
        self.assertIn("depth_events", db.table_names())

    def test_log_depth_event(self):
        """Test that log_depth_event successfully adds data to the database."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample depth event data
        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_456",
            "metrics": {"total_depth": 500.0, "top_gap": 0.05},
            "signal_type": "thin_depth",
            "threshold_hit": "total_depth < 1000",
            "mode": "live",
        }

        # Log the event
        log_depth_event(event_data, self.test_db_path)

        # Verify data was inserted
        db = Database(self.test_db_path)
        rows = list(db["depth_events"].rows)
        self.assertEqual(len(rows), 1)

        # Verify data matches
        row = rows[0]
        self.assertEqual(row["timestamp"], "2024-01-05T12:00:00")
        self.assertEqual(row["market_id"], "market_456")
        self.assertEqual(row["signal_type"], "thin_depth")
        self.assertEqual(row["threshold_hit"], "total_depth < 1000")
        self.assertEqual(row["mode"], "live")
        # Metrics should be stored as JSON string
        self.assertIn("total_depth", row["metrics"])

    def test_log_depth_event_with_datetime(self):
        """Test that log_depth_event handles datetime objects correctly."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample event data with datetime object
        timestamp = datetime(2024, 1, 5, 14, 30, 45)
        event_data = {
            "timestamp": timestamp,
            "market_id": "market_abc",
            "metrics": {"imbalance": 100.0},
            "signal_type": "strong_imbalance",
            "threshold_hit": "imbalance > 50",
            "mode": "mock",
        }

        # Log the event
        log_depth_event(event_data, self.test_db_path)

        # Verify data was inserted with timestamp converted to string
        db = Database(self.test_db_path)
        rows = list(db["depth_events"].rows)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["timestamp"], "2024-01-05T14:30:45")
        self.assertEqual(row["market_id"], "market_abc")

    def test_log_depth_event_with_string_metrics(self):
        """Test that log_depth_event handles metrics as string correctly."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample event data with metrics already as JSON string
        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_xyz",
            "metrics": '{"total_depth": 200.0}',  # Already a string
            "signal_type": "large_gap",
            "threshold_hit": "gap > 0.10",
            "mode": "live",
        }

        # Log the event
        log_depth_event(event_data, self.test_db_path)

        # Verify data was inserted
        db = Database(self.test_db_path)
        rows = list(db["depth_events"].rows)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["metrics"], '{"total_depth": 200.0}')

    def test_log_multiple_depth_events(self):
        """Test logging multiple depth events."""
        # Initialize database
        init_db(self.test_db_path)

        # Log multiple events
        events = [
            {
                "timestamp": "2024-01-05T10:00:00",
                "market_id": "market_1",
                "metrics": {"depth": 100},
                "signal_type": "thin_depth",
                "threshold_hit": "depth < 500",
                "mode": "live",
            },
            {
                "timestamp": "2024-01-05T11:00:00",
                "market_id": "market_2",
                "metrics": {"gap": 0.15},
                "signal_type": "large_gap",
                "threshold_hit": "gap > 0.10",
                "mode": "live",
            },
            {
                "timestamp": "2024-01-05T12:00:00",
                "market_id": "market_3",
                "metrics": {"imbalance": 400},
                "signal_type": "strong_imbalance",
                "threshold_hit": "imbalance > 300",
                "mode": "mock",
            },
        ]

        for event in events:
            log_depth_event(event, self.test_db_path)

        # Verify all events were inserted
        db = Database(self.test_db_path)
        rows = list(db["depth_events"].rows)
        self.assertEqual(len(rows), 3)

    def test_fetch_recent_depth_events_empty_database(self):
        """Test fetch_recent_depth_events returns empty list for empty database."""
        # Initialize database
        init_db(self.test_db_path)

        # Fetch recent events
        results = fetch_recent_depth_events(limit=10, db_path=self.test_db_path)

        # Verify empty list is returned
        self.assertEqual(results, [])

    def test_fetch_recent_depth_events_no_table(self):
        """Test fetch_recent_depth_events returns empty list when table doesn't exist."""
        # Create database without initializing table
        Database(self.test_db_path)

        # Fetch recent events
        results = fetch_recent_depth_events(limit=10, db_path=self.test_db_path)

        # Verify empty list is returned
        self.assertEqual(results, [])

    def test_fetch_recent_depth_events_single_entry(self):
        """Test fetch_recent_depth_events retrieves a single entry correctly."""
        # Initialize database and log an event
        init_db(self.test_db_path)

        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_single",
            "metrics": {"total_depth": 750.0, "gap": 0.03},
            "signal_type": "thin_depth",
            "threshold_hit": "depth < 1000",
            "mode": "live",
        }
        log_depth_event(event_data, self.test_db_path)

        # Fetch recent events
        results = fetch_recent_depth_events(limit=10, db_path=self.test_db_path)

        # Verify one entry is returned
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["market_id"], "market_single")
        self.assertEqual(results[0]["signal_type"], "thin_depth")
        # Verify metrics are deserialized to dict
        self.assertIsInstance(results[0]["metrics"], dict)
        self.assertEqual(results[0]["metrics"]["total_depth"], 750.0)

    def test_fetch_recent_depth_events_order(self):
        """Test fetch_recent_depth_events returns entries in correct order (most recent first)."""
        # Initialize database
        init_db(self.test_db_path)

        # Log multiple events with different timestamps
        events = [
            {
                "timestamp": "2024-01-05T10:00:00",
                "market_id": "market_1",
                "metrics": {"depth": 100},
                "signal_type": "thin_depth",
                "threshold_hit": "depth < 500",
                "mode": "live",
            },
            {
                "timestamp": "2024-01-05T12:00:00",
                "market_id": "market_2",
                "metrics": {"gap": 0.15},
                "signal_type": "large_gap",
                "threshold_hit": "gap > 0.10",
                "mode": "live",
            },
            {
                "timestamp": "2024-01-05T11:00:00",
                "market_id": "market_3",
                "metrics": {"imbalance": 400},
                "signal_type": "strong_imbalance",
                "threshold_hit": "imbalance > 300",
                "mode": "mock",
            },
        ]

        for event in events:
            log_depth_event(event, self.test_db_path)

        # Fetch recent events
        results = fetch_recent_depth_events(limit=10, db_path=self.test_db_path)

        # Verify order (most recent first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["market_id"], "market_2")  # Latest (12:00)
        self.assertEqual(results[1]["market_id"], "market_3")  # Middle (11:00)
        self.assertEqual(results[2]["market_id"], "market_1")  # Earliest (10:00)

    def test_fetch_recent_depth_events_limit(self):
        """Test fetch_recent_depth_events respects the limit parameter."""
        # Initialize database
        init_db(self.test_db_path)

        # Log 10 events
        for i in range(10):
            event_data = {
                "timestamp": f"2024-01-05T{10+i:02d}:00:00",
                "market_id": f"market_{i}",
                "metrics": {"depth": 100 + i * 10},
                "signal_type": "thin_depth",
                "threshold_hit": "depth < 500",
                "mode": "live",
            }
            log_depth_event(event_data, self.test_db_path)

        # Fetch with limit of 5
        results = fetch_recent_depth_events(limit=5, db_path=self.test_db_path)

        # Verify only 5 entries are returned
        self.assertEqual(len(results), 5)

        # Verify they are the most recent 5
        for i, result in enumerate(results):
            expected_market_id = f"market_{9-i}"  # Most recent first
            self.assertEqual(result["market_id"], expected_market_id)

    def test_fetch_recent_depth_events_default_limit(self):
        """Test fetch_recent_depth_events uses default limit of 100."""
        # Initialize database
        init_db(self.test_db_path)

        # Log 5 events (less than default limit)
        for i in range(5):
            event_data = {
                "timestamp": f"2024-01-05T{10+i:02d}:00:00",
                "market_id": f"market_{i}",
                "metrics": {"depth": 100},
                "signal_type": "thin_depth",
                "threshold_hit": "depth < 500",
                "mode": "mock",
            }
            log_depth_event(event_data, self.test_db_path)

        # Fetch without specifying limit
        results = fetch_recent_depth_events(db_path=self.test_db_path)

        # Verify all 5 entries are returned
        self.assertEqual(len(results), 5)

    def test_depth_events_independent_from_other_events(self):
        """Test that depth events are stored independently from arbitrage and price alert events."""
        # Initialize database
        init_db(self.test_db_path)

        # Log a depth event
        depth_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_456",
            "metrics": {"total_depth": 500.0},
            "signal_type": "thin_depth",
            "threshold_hit": "depth < 1000",
            "mode": "live",
        }
        log_depth_event(depth_data, self.test_db_path)

        # Verify depth events table has 1 entry
        depth_events = fetch_recent_depth_events(db_path=self.test_db_path)
        self.assertEqual(len(depth_events), 1)

        # Verify arbitrage events table is still empty
        arb_events = fetch_recent(db_path=self.test_db_path)
        self.assertEqual(len(arb_events), 0)

    def test_get_table_columns_validates_depth_events(self):
        """Test that _get_table_columns validates depth_events as valid table name."""
        # Initialize database
        init_db(self.test_db_path)
        db = Database(self.test_db_path)

        # Valid table name should work
        try:
            columns = _get_table_columns(db, "depth_events")
            self.assertIsInstance(columns, list)
            self.assertIn("market_id", columns)
            self.assertIn("metrics", columns)
            self.assertIn("signal_type", columns)
        except ValueError:
            self.fail("Valid table name 'depth_events' raised ValueError")

    def test_metrics_json_deserialization(self):
        """Test that metrics field is properly deserialized from JSON."""
        # Initialize database
        init_db(self.test_db_path)

        # Create event with complex metrics
        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_complex",
            "metrics": {
                "total_yes_depth": 1500.0,
                "total_no_depth": 1200.0,
                "top_gap_yes": 0.05,
                "top_gap_no": 0.06,
                "imbalance": 300.0,
                "nested": {"value": 42},
            },
            "signal_type": "strong_imbalance",
            "threshold_hit": "imbalance > 300",
            "mode": "live",
        }
        log_depth_event(event_data, self.test_db_path)

        # Fetch and verify deserialization
        results = fetch_recent_depth_events(db_path=self.test_db_path)
        self.assertEqual(len(results), 1)

        metrics = results[0]["metrics"]
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics["total_yes_depth"], 1500.0)
        self.assertEqual(metrics["total_no_depth"], 1200.0)
        self.assertEqual(metrics["top_gap_yes"], 0.05)
        self.assertEqual(metrics["imbalance"], 300.0)
        self.assertEqual(metrics["nested"]["value"], 42)


if __name__ == "__main__":
    unittest.main()
