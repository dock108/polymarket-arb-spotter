"""
Unit tests for the logging system module.

Tests database initialization, event logging, and data retrieval
for the arbitrage event logging system.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime
from sqlite_utils import Database

from app.core.logger import init_db, log_event, fetch_recent


class TestLogger(unittest.TestCase):
    """Test arbitrage event logging system."""

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

    def test_init_db(self):
        """Test that init_db creates the database with correct schema."""
        # Initialize database
        init_db(self.test_db_path)

        # Verify database file was created
        self.assertTrue(os.path.exists(self.test_db_path))

        # Verify table schema
        db = Database(self.test_db_path)
        self.assertIn("arbitrage_events", db.table_names())

        # Verify columns
        table = db["arbitrage_events"]
        columns = {col.name for col in table.columns}
        expected_columns = {
            "id",
            "timestamp",
            "market_id",
            "market_name",
            "yes_price",
            "no_price",
            "sum",
            "expected_profit_pct",
            "mode",
            "decision",
            "mock_result",
            "failure_reason",
            "latency_ms",
        }
        self.assertEqual(columns, expected_columns)

    def test_init_db_creates_directory(self):
        """Test that init_db creates parent directory if it doesn't exist."""
        # Use a path with non-existent parent directory
        nested_path = os.path.join(self.test_dir, "nested", "dir", "test.sqlite")

        # Initialize database
        init_db(nested_path)

        # Verify database file and parent directories were created
        self.assertTrue(os.path.exists(nested_path))
        self.assertTrue(os.path.exists(os.path.dirname(nested_path)))

    def test_init_db_idempotent(self):
        """Test that init_db can be called multiple times safely."""
        # Initialize database twice
        init_db(self.test_db_path)
        init_db(self.test_db_path)

        # Verify database still exists and is valid
        db = Database(self.test_db_path)
        self.assertIn("arbitrage_events", db.table_names())

    def test_log_event(self):
        """Test that log_event successfully adds data to the database."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample event data
        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_123",
            "market_name": "Test Market",
            "yes_price": 0.45,
            "no_price": 0.60,
            "sum": 1.05,
            "expected_profit_pct": 5.0,
            "mode": "mock",
            "decision": "alerted",
            "mock_result": "success",
            "failure_reason": None,
            "latency_ms": 150,
        }

        # Log the event
        log_event(event_data, self.test_db_path)

        # Verify data was inserted
        db = Database(self.test_db_path)
        rows = list(db["arbitrage_events"].rows)
        self.assertEqual(len(rows), 1)

        # Verify data matches
        row = rows[0]
        self.assertEqual(row["market_id"], "market_123")
        self.assertEqual(row["market_name"], "Test Market")
        self.assertEqual(row["yes_price"], 0.45)
        self.assertEqual(row["no_price"], 0.60)
        self.assertEqual(row["sum"], 1.05)
        self.assertEqual(row["expected_profit_pct"], 5.0)
        self.assertEqual(row["mode"], "mock")
        self.assertEqual(row["decision"], "alerted")
        self.assertEqual(row["mock_result"], "success")
        self.assertIsNone(row["failure_reason"])
        self.assertEqual(row["latency_ms"], 150)

    def test_log_event_with_datetime(self):
        """Test that log_event handles datetime objects correctly."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample event data with datetime object
        timestamp = datetime(2024, 1, 5, 12, 0, 0)
        event_data = {
            "timestamp": timestamp,
            "market_id": "market_456",
            "market_name": "Test Market 2",
            "yes_price": 0.50,
            "no_price": 0.55,
            "sum": 1.05,
            "expected_profit_pct": 5.0,
            "mode": "live",
            "decision": "ignored",
            "mock_result": None,
            "failure_reason": None,
            "latency_ms": 200,
        }

        # Log the event
        log_event(event_data, self.test_db_path)

        # Verify data was inserted with timestamp converted to string
        db = Database(self.test_db_path)
        rows = list(db["arbitrage_events"].rows)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["timestamp"], "2024-01-05T12:00:00")

    def test_log_event_with_failure(self):
        """Test logging an event with failure information."""
        # Initialize database
        init_db(self.test_db_path)

        # Create sample event data with failure
        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_789",
            "market_name": "Failed Market",
            "yes_price": 0.40,
            "no_price": 0.65,
            "sum": 1.05,
            "expected_profit_pct": 5.0,
            "mode": "mock",
            "decision": "alerted",
            "mock_result": "failure",
            "failure_reason": "Insufficient liquidity",
            "latency_ms": 300,
        }

        # Log the event
        log_event(event_data, self.test_db_path)

        # Verify data was inserted
        db = Database(self.test_db_path)
        rows = list(db["arbitrage_events"].rows)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["mock_result"], "failure")
        self.assertEqual(row["failure_reason"], "Insufficient liquidity")

    def test_fetch_recent_empty_database(self):
        """Test fetch_recent returns empty list for empty database."""
        # Initialize database
        init_db(self.test_db_path)

        # Fetch recent events
        results = fetch_recent(limit=10, db_path=self.test_db_path)

        # Verify empty list is returned
        self.assertEqual(results, [])

    def test_fetch_recent_no_table(self):
        """Test fetch_recent returns empty list when table doesn't exist."""
        # Create database without initializing table
        Database(self.test_db_path)

        # Fetch recent events
        results = fetch_recent(limit=10, db_path=self.test_db_path)

        # Verify empty list is returned
        self.assertEqual(results, [])

    def test_fetch_recent_single_entry(self):
        """Test fetch_recent retrieves a single entry correctly."""
        # Initialize database and log an event
        init_db(self.test_db_path)

        event_data = {
            "timestamp": "2024-01-05T12:00:00",
            "market_id": "market_abc",
            "market_name": "Single Entry Market",
            "yes_price": 0.48,
            "no_price": 0.58,
            "sum": 1.06,
            "expected_profit_pct": 6.0,
            "mode": "mock",
            "decision": "alerted",
            "mock_result": "success",
            "failure_reason": None,
            "latency_ms": 100,
        }
        log_event(event_data, self.test_db_path)

        # Fetch recent events
        results = fetch_recent(limit=10, db_path=self.test_db_path)

        # Verify one entry is returned
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["market_id"], "market_abc")

    def test_fetch_recent_order(self):
        """Test fetch_recent returns entries in correct order (most recent first)."""
        # Initialize database
        init_db(self.test_db_path)

        # Log multiple events with different timestamps
        events = [
            {
                "timestamp": "2024-01-05T10:00:00",
                "market_id": "market_1",
                "market_name": "First Market",
                "yes_price": 0.45,
                "no_price": 0.60,
                "sum": 1.05,
                "expected_profit_pct": 5.0,
                "mode": "mock",
                "decision": "alerted",
                "mock_result": "success",
                "failure_reason": None,
                "latency_ms": 100,
            },
            {
                "timestamp": "2024-01-05T12:00:00",
                "market_id": "market_2",
                "market_name": "Second Market",
                "yes_price": 0.46,
                "no_price": 0.59,
                "sum": 1.05,
                "expected_profit_pct": 5.0,
                "mode": "mock",
                "decision": "alerted",
                "mock_result": "success",
                "failure_reason": None,
                "latency_ms": 120,
            },
            {
                "timestamp": "2024-01-05T11:00:00",
                "market_id": "market_3",
                "market_name": "Third Market",
                "yes_price": 0.47,
                "no_price": 0.58,
                "sum": 1.05,
                "expected_profit_pct": 5.0,
                "mode": "mock",
                "decision": "alerted",
                "mock_result": "success",
                "failure_reason": None,
                "latency_ms": 110,
            },
        ]

        for event in events:
            log_event(event, self.test_db_path)

        # Fetch recent events
        results = fetch_recent(limit=10, db_path=self.test_db_path)

        # Verify order (most recent first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["market_id"], "market_2")  # Latest
        self.assertEqual(results[1]["market_id"], "market_3")  # Middle
        self.assertEqual(results[2]["market_id"], "market_1")  # Earliest

    def test_fetch_recent_limit(self):
        """Test fetch_recent respects the limit parameter."""
        # Initialize database
        init_db(self.test_db_path)

        # Log 10 events
        for i in range(10):
            event_data = {
                "timestamp": f"2024-01-05T{10+i:02d}:00:00",
                "market_id": f"market_{i}",
                "market_name": f"Market {i}",
                "yes_price": 0.45,
                "no_price": 0.60,
                "sum": 1.05,
                "expected_profit_pct": 5.0,
                "mode": "mock",
                "decision": "alerted",
                "mock_result": "success",
                "failure_reason": None,
                "latency_ms": 100 + i,
            }
            log_event(event_data, self.test_db_path)

        # Fetch with limit of 5
        results = fetch_recent(limit=5, db_path=self.test_db_path)

        # Verify only 5 entries are returned
        self.assertEqual(len(results), 5)

        # Verify they are the most recent 5
        for i, result in enumerate(results):
            expected_market_id = f"market_{9-i}"  # Most recent first
            self.assertEqual(result["market_id"], expected_market_id)

    def test_fetch_recent_default_limit(self):
        """Test fetch_recent uses default limit of 100."""
        # Initialize database
        init_db(self.test_db_path)

        # Log 5 events (less than default limit)
        for i in range(5):
            event_data = {
                "timestamp": f"2024-01-05T{10+i:02d}:00:00",
                "market_id": f"market_{i}",
                "market_name": f"Market {i}",
                "yes_price": 0.45,
                "no_price": 0.60,
                "sum": 1.05,
                "expected_profit_pct": 5.0,
                "mode": "mock",
                "decision": "alerted",
                "mock_result": "success",
                "failure_reason": None,
                "latency_ms": 100,
            }
            log_event(event_data, self.test_db_path)

        # Fetch without specifying limit
        results = fetch_recent(db_path=self.test_db_path)

        # Verify all 5 entries are returned
        self.assertEqual(len(results), 5)


if __name__ == "__main__":
    unittest.main()
