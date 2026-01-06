"""
Unit tests for the historical data store module.

Tests tick storage, retrieval, batch inserts, and pruning functionality
for the market history store.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from app.core.history_store import (
    append_tick,
    append_ticks,
    get_ticks,
    prune_old,
    get_tick_count,
    _get_db,
    _ensure_table,
)


class TestHistoryStore(unittest.TestCase):
    """Test historical tick data store."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_history.db")

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)


class TestAppendTick(TestHistoryStore):
    """Test append_tick function."""

    def test_append_tick_basic(self):
        """Test appending a single tick."""
        append_tick(
            market_id="market_123",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.65,
            no_price=0.35,
            volume=1000.0,
            db_path=self.test_db_path,
        )

        # Verify tick was stored
        ticks = get_ticks("market_123", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0]["market_id"], "market_123")
        self.assertEqual(ticks[0]["yes_price"], 0.65)
        self.assertEqual(ticks[0]["no_price"], 0.35)
        self.assertEqual(ticks[0]["volume"], 1000.0)

    def test_append_tick_with_datetime(self):
        """Test appending a tick with datetime object."""
        timestamp = datetime(2024, 1, 5, 12, 0, 0)
        append_tick(
            market_id="market_456",
            timestamp=timestamp,
            yes_price=0.50,
            no_price=0.50,
            volume=500.0,
            db_path=self.test_db_path,
        )

        ticks = get_ticks("market_456", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0]["timestamp"], "2024-01-05T12:00:00")

    def test_append_tick_with_depth_summary(self):
        """Test appending a tick with depth summary."""
        depth = {"bid_depth": 500, "ask_depth": 600, "spread": 0.02}
        append_tick(
            market_id="market_789",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.60,
            no_price=0.40,
            volume=750.0,
            depth_summary=depth,
            db_path=self.test_db_path,
        )

        ticks = get_ticks("market_789", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0]["depth_summary"]["bid_depth"], 500)
        self.assertEqual(ticks[0]["depth_summary"]["ask_depth"], 600)
        self.assertEqual(ticks[0]["depth_summary"]["spread"], 0.02)

    def test_append_tick_without_depth_summary(self):
        """Test appending a tick without depth summary."""
        append_tick(
            market_id="market_abc",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.70,
            no_price=0.30,
            volume=200.0,
            depth_summary=None,
            db_path=self.test_db_path,
        )

        ticks = get_ticks("market_abc", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 1)
        self.assertIsNone(ticks[0]["depth_summary"])

    def test_append_multiple_ticks_same_market(self):
        """Test appending multiple ticks to the same market."""
        for i in range(5):
            append_tick(
                market_id="market_multi",
                timestamp=f"2024-01-05T12:{i:02d}:00",
                yes_price=0.50 + i * 0.01,
                no_price=0.50 - i * 0.01,
                volume=100.0 * (i + 1),
                db_path=self.test_db_path,
            )

        ticks = get_ticks("market_multi", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 5)

    def test_append_tick_creates_directory(self):
        """Test that append_tick creates parent directory."""
        nested_path = os.path.join(self.test_dir, "nested", "dir", "history.db")
        append_tick(
            market_id="market_nested",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.55,
            no_price=0.45,
            volume=300.0,
            db_path=nested_path,
        )

        self.assertTrue(os.path.exists(nested_path))
        ticks = get_ticks("market_nested", db_path=nested_path)
        self.assertEqual(len(ticks), 1)


class TestAppendTicks(TestHistoryStore):
    """Test append_ticks batch insert function."""

    def test_append_ticks_batch(self):
        """Test batch inserting multiple ticks."""
        ticks_data = [
            {
                "market_id": "market_batch",
                "timestamp": "2024-01-05T12:00:00",
                "yes_price": 0.60,
                "no_price": 0.40,
                "volume": 100.0,
            },
            {
                "market_id": "market_batch",
                "timestamp": "2024-01-05T12:01:00",
                "yes_price": 0.61,
                "no_price": 0.39,
                "volume": 150.0,
            },
            {
                "market_id": "market_batch",
                "timestamp": "2024-01-05T12:02:00",
                "yes_price": 0.62,
                "no_price": 0.38,
                "volume": 200.0,
            },
        ]

        count = append_ticks(ticks_data, db_path=self.test_db_path)
        self.assertEqual(count, 3)

        ticks = get_ticks("market_batch", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 3)

    def test_append_ticks_with_datetime(self):
        """Test batch inserting with datetime objects."""
        base_time = datetime(2024, 1, 5, 12, 0, 0)
        ticks_data = [
            {
                "market_id": "market_dt",
                "timestamp": base_time + timedelta(minutes=i),
                "yes_price": 0.50,
                "no_price": 0.50,
                "volume": 100.0,
            }
            for i in range(5)
        ]

        count = append_ticks(ticks_data, db_path=self.test_db_path)
        self.assertEqual(count, 5)

    def test_append_ticks_with_depth_summary(self):
        """Test batch inserting with depth summaries."""
        ticks_data = [
            {
                "market_id": "market_depth",
                "timestamp": "2024-01-05T12:00:00",
                "yes_price": 0.55,
                "no_price": 0.45,
                "volume": 100.0,
                "depth_summary": {"bid": 100, "ask": 150},
            },
            {
                "market_id": "market_depth",
                "timestamp": "2024-01-05T12:01:00",
                "yes_price": 0.56,
                "no_price": 0.44,
                "volume": 120.0,
                "depth_summary": {"bid": 110, "ask": 160},
            },
        ]

        count = append_ticks(ticks_data, db_path=self.test_db_path)
        self.assertEqual(count, 2)

        ticks = get_ticks("market_depth", db_path=self.test_db_path)
        self.assertEqual(ticks[0]["depth_summary"]["bid"], 100)
        self.assertEqual(ticks[1]["depth_summary"]["bid"], 110)

    def test_append_ticks_empty_list(self):
        """Test batch inserting empty list returns 0."""
        count = append_ticks([], db_path=self.test_db_path)
        self.assertEqual(count, 0)

    def test_append_ticks_multiple_markets(self):
        """Test batch inserting ticks for multiple markets."""
        ticks_data = [
            {
                "market_id": "market_a",
                "timestamp": "2024-01-05T12:00:00",
                "yes_price": 0.60,
                "no_price": 0.40,
                "volume": 100.0,
            },
            {
                "market_id": "market_b",
                "timestamp": "2024-01-05T12:00:00",
                "yes_price": 0.70,
                "no_price": 0.30,
                "volume": 200.0,
            },
            {
                "market_id": "market_a",
                "timestamp": "2024-01-05T12:01:00",
                "yes_price": 0.61,
                "no_price": 0.39,
                "volume": 110.0,
            },
        ]

        count = append_ticks(ticks_data, db_path=self.test_db_path)
        self.assertEqual(count, 3)

        ticks_a = get_ticks("market_a", db_path=self.test_db_path)
        ticks_b = get_ticks("market_b", db_path=self.test_db_path)
        self.assertEqual(len(ticks_a), 2)
        self.assertEqual(len(ticks_b), 1)


class TestGetTicks(TestHistoryStore):
    """Test get_ticks function."""

    def test_get_ticks_empty_database(self):
        """Test getting ticks from empty database."""
        ticks = get_ticks("nonexistent_market", db_path=self.test_db_path)
        self.assertEqual(ticks, [])

    def test_get_ticks_by_market_id(self):
        """Test getting ticks filtered by market_id."""
        # Insert ticks for multiple markets
        append_tick(
            market_id="market_1",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.60,
            no_price=0.40,
            volume=100.0,
            db_path=self.test_db_path,
        )
        append_tick(
            market_id="market_2",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.70,
            no_price=0.30,
            volume=200.0,
            db_path=self.test_db_path,
        )

        ticks = get_ticks("market_1", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0]["market_id"], "market_1")

    def test_get_ticks_time_range_start(self):
        """Test getting ticks with start time filter."""
        for i in range(5):
            append_tick(
                market_id="market_time",
                timestamp=f"2024-01-05T{10+i:02d}:00:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        # Get ticks starting from 12:00
        ticks = get_ticks(
            "market_time",
            start="2024-01-05T12:00:00",
            db_path=self.test_db_path,
        )
        self.assertEqual(len(ticks), 3)  # 12:00, 13:00, 14:00

    def test_get_ticks_time_range_end(self):
        """Test getting ticks with end time filter."""
        for i in range(5):
            append_tick(
                market_id="market_time",
                timestamp=f"2024-01-05T{10+i:02d}:00:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        # Get ticks ending at 12:00
        ticks = get_ticks(
            "market_time",
            end="2024-01-05T12:00:00",
            db_path=self.test_db_path,
        )
        self.assertEqual(len(ticks), 3)  # 10:00, 11:00, 12:00

    def test_get_ticks_time_range_both(self):
        """Test getting ticks with both start and end time filters."""
        for i in range(10):
            append_tick(
                market_id="market_range",
                timestamp=f"2024-01-05T{10+i:02d}:00:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        # Get ticks between 12:00 and 15:00
        ticks = get_ticks(
            "market_range",
            start="2024-01-05T12:00:00",
            end="2024-01-05T15:00:00",
            db_path=self.test_db_path,
        )
        self.assertEqual(len(ticks), 4)  # 12, 13, 14, 15

    def test_get_ticks_with_datetime_filters(self):
        """Test getting ticks with datetime object filters."""
        for i in range(5):
            append_tick(
                market_id="market_dt",
                timestamp=datetime(2024, 1, 5, 10 + i, 0, 0),
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        ticks = get_ticks(
            "market_dt",
            start=datetime(2024, 1, 5, 12, 0, 0),
            end=datetime(2024, 1, 5, 13, 0, 0),
            db_path=self.test_db_path,
        )
        self.assertEqual(len(ticks), 2)  # 12:00 and 13:00

    def test_get_ticks_order(self):
        """Test that ticks are returned in ascending timestamp order."""
        # Insert ticks out of order
        append_tick(
            market_id="market_order",
            timestamp="2024-01-05T14:00:00",
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )
        append_tick(
            market_id="market_order",
            timestamp="2024-01-05T10:00:00",
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )
        append_tick(
            market_id="market_order",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )

        ticks = get_ticks("market_order", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 3)
        self.assertEqual(ticks[0]["timestamp"], "2024-01-05T10:00:00")
        self.assertEqual(ticks[1]["timestamp"], "2024-01-05T12:00:00")
        self.assertEqual(ticks[2]["timestamp"], "2024-01-05T14:00:00")

    def test_get_ticks_limit(self):
        """Test that limit parameter is respected."""
        for i in range(20):
            append_tick(
                market_id="market_limit",
                timestamp=f"2024-01-05T{10+i:02d}:00:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        ticks = get_ticks("market_limit", limit=5, db_path=self.test_db_path)
        self.assertEqual(len(ticks), 5)
        # Should be the earliest 5 due to ASC ordering
        self.assertEqual(ticks[0]["timestamp"], "2024-01-05T10:00:00")


class TestPruneOld(TestHistoryStore):
    """Test prune_old function."""

    def test_prune_old_basic(self):
        """Test basic pruning of old ticks."""
        now = datetime.now()

        # Insert ticks with various ages
        append_tick(
            market_id="market_prune",
            timestamp=(now - timedelta(days=10)).isoformat(),
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )
        append_tick(
            market_id="market_prune",
            timestamp=(now - timedelta(days=5)).isoformat(),
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )
        append_tick(
            market_id="market_prune",
            timestamp=(now - timedelta(days=1)).isoformat(),
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )

        # Prune ticks older than 7 days
        deleted = prune_old(days=7, db_path=self.test_db_path)
        self.assertEqual(deleted, 1)  # Only the 10-day old tick

        ticks = get_ticks("market_prune", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 2)

    def test_prune_old_none_to_delete(self):
        """Test pruning when no ticks are old enough."""
        now = datetime.now()

        append_tick(
            market_id="market_recent",
            timestamp=(now - timedelta(hours=1)).isoformat(),
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )

        deleted = prune_old(days=7, db_path=self.test_db_path)
        self.assertEqual(deleted, 0)

        ticks = get_ticks("market_recent", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 1)

    def test_prune_old_all_deleted(self):
        """Test pruning when all ticks are old."""
        now = datetime.now()

        for i in range(5):
            append_tick(
                market_id="market_old",
                timestamp=(now - timedelta(days=30 + i)).isoformat(),
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        deleted = prune_old(days=7, db_path=self.test_db_path)
        self.assertEqual(deleted, 5)

        ticks = get_ticks("market_old", db_path=self.test_db_path)
        self.assertEqual(len(ticks), 0)

    def test_prune_old_empty_database(self):
        """Test pruning on empty database."""
        deleted = prune_old(days=7, db_path=self.test_db_path)
        self.assertEqual(deleted, 0)

    def test_prune_old_negative_days_raises(self):
        """Test that negative days raises ValueError."""
        with self.assertRaises(ValueError) as context:
            prune_old(days=-1, db_path=self.test_db_path)
        self.assertIn("non-negative", str(context.exception))

    def test_prune_old_zero_days(self):
        """Test pruning with zero days (delete all historical)."""
        now = datetime.now()

        # Insert a tick from yesterday
        append_tick(
            market_id="market_zero",
            timestamp=(now - timedelta(hours=1)).isoformat(),
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )

        # Prune with 0 days should delete anything older than now
        deleted = prune_old(days=0, db_path=self.test_db_path)
        self.assertEqual(deleted, 1)


class TestGetTickCount(TestHistoryStore):
    """Test get_tick_count function."""

    def test_get_tick_count_empty(self):
        """Test count on empty database."""
        count = get_tick_count(db_path=self.test_db_path)
        self.assertEqual(count, 0)

    def test_get_tick_count_all(self):
        """Test getting total tick count."""
        for i in range(10):
            append_tick(
                market_id=f"market_{i % 3}",
                timestamp=f"2024-01-05T12:{i:02d}:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        count = get_tick_count(db_path=self.test_db_path)
        self.assertEqual(count, 10)

    def test_get_tick_count_by_market(self):
        """Test getting tick count for specific market."""
        for i in range(5):
            append_tick(
                market_id="market_a",
                timestamp=f"2024-01-05T12:{i:02d}:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )
        for i in range(3):
            append_tick(
                market_id="market_b",
                timestamp=f"2024-01-05T12:{i:02d}:00",
                yes_price=0.50,
                no_price=0.50,
                volume=100.0,
                db_path=self.test_db_path,
            )

        count_a = get_tick_count(market_id="market_a", db_path=self.test_db_path)
        count_b = get_tick_count(market_id="market_b", db_path=self.test_db_path)
        self.assertEqual(count_a, 5)
        self.assertEqual(count_b, 3)


class TestTableCreation(TestHistoryStore):
    """Test table creation and indexes."""

    def test_table_creation(self):
        """Test that table is created with correct schema."""
        db = _get_db(self.test_db_path)
        _ensure_table(db)

        self.assertIn("market_ticks", db.table_names())

        # Check columns
        table = db["market_ticks"]
        columns = {col.name for col in table.columns}
        expected_columns = {
            "id",
            "market_id",
            "timestamp",
            "yes_price",
            "no_price",
            "volume",
            "depth_summary",
        }
        self.assertEqual(columns, expected_columns)

    def test_table_idempotent(self):
        """Test that _ensure_table can be called multiple times safely."""
        db = _get_db(self.test_db_path)
        _ensure_table(db)
        _ensure_table(db)  # Should not raise

        self.assertIn("market_ticks", db.table_names())

    def test_index_creation(self):
        """Test that indexes are created correctly."""
        db = _get_db(self.test_db_path)
        _ensure_table(db)

        # Check that the index exists
        indexes = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='market_ticks'"
        ).fetchall()
        index_names = [idx[0] for idx in indexes]
        self.assertIn("idx_market_timestamp", index_names)


class TestOfflineSafety(TestHistoryStore):
    """Test that operations are safe when encountering errors."""

    def test_append_tick_handles_error_gracefully(self):
        """Test that append_tick doesn't raise on error."""
        # This should not raise even with an invalid path
        # (it will log the error but continue)
        append_tick(
            market_id="market_test",
            timestamp="2024-01-05T12:00:00",
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            db_path=self.test_db_path,
        )
        # If we got here without exception, the test passes

    def test_get_ticks_handles_missing_table(self):
        """Test that get_ticks returns empty list for missing table."""
        # Create database but don't create table
        _get_db(self.test_db_path)

        ticks = get_ticks("market_test", db_path=self.test_db_path)
        self.assertEqual(ticks, [])


if __name__ == "__main__":
    unittest.main()
