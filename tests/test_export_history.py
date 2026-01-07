"""
Unit tests for the export_history module.

Tests the market snapshot exporter functionality including CSV and JSONL
export, date range filtering, and market filtering.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.core.history_store import append_ticks, get_market_ids

# Add scripts directory to path for importing export_history
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from export_history import (  # noqa: E402
    get_filtered_ticks,
    export_to_csv,
    export_to_jsonl,
    parse_date,
)


class TestExportHistory(unittest.TestCase):
    """Base test class with common setup and teardown."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_history.db")
        self.test_output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.test_output_dir)

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_data(self):
        """Create test data in the history store."""
        # Insert ticks for multiple markets
        ticks_data = [
            {
                "market_id": "market_a",
                "timestamp": "2024-01-05T10:00:00",
                "yes_price": 0.60,
                "no_price": 0.40,
                "volume": 100.0,
            },
            {
                "market_id": "market_a",
                "timestamp": "2024-01-05T11:00:00",
                "yes_price": 0.61,
                "no_price": 0.39,
                "volume": 150.0,
            },
            {
                "market_id": "market_a",
                "timestamp": "2024-01-05T12:00:00",
                "yes_price": 0.62,
                "no_price": 0.38,
                "volume": 200.0,
            },
            {
                "market_id": "market_b",
                "timestamp": "2024-01-05T10:30:00",
                "yes_price": 0.70,
                "no_price": 0.30,
                "volume": 250.0,
            },
            {
                "market_id": "market_b",
                "timestamp": "2024-01-05T11:30:00",
                "yes_price": 0.71,
                "no_price": 0.29,
                "volume": 300.0,
                "depth_summary": {"total_depth": 1000, "yes_depth": 600},
            },
            {
                "market_id": "market_c",
                "timestamp": "2024-01-06T10:00:00",
                "yes_price": 0.50,
                "no_price": 0.50,
                "volume": 500.0,
            },
        ]
        append_ticks(ticks_data, db_path=self.test_db_path)


class TestGetMarketIds(TestExportHistory):
    """Test get_market_ids function from history_store."""

    def test_empty_database(self):
        """Test getting market IDs from empty database."""
        market_ids = get_market_ids(db_path=self.test_db_path)
        self.assertEqual(market_ids, [])

    def test_returns_unique_market_ids(self):
        """Test that it returns all unique market IDs."""
        self._create_test_data()
        market_ids = get_market_ids(db_path=self.test_db_path)
        self.assertEqual(sorted(market_ids), ["market_a", "market_b", "market_c"])

    def test_market_ids_are_sorted(self):
        """Test that market IDs are returned in sorted order."""
        self._create_test_data()
        market_ids = get_market_ids(db_path=self.test_db_path)
        self.assertEqual(market_ids, sorted(market_ids))


class TestGetFilteredTicks(TestExportHistory):
    """Test get_filtered_ticks function."""

    def test_get_all_ticks(self):
        """Test getting all ticks without filters."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        self.assertEqual(len(ticks), 6)

    def test_filter_by_single_market(self):
        """Test filtering by a single market."""
        self._create_test_data()
        ticks = get_filtered_ticks(market_ids=["market_a"], db_path=self.test_db_path)
        self.assertEqual(len(ticks), 3)
        for tick in ticks:
            self.assertEqual(tick["market_id"], "market_a")

    def test_filter_by_multiple_markets(self):
        """Test filtering by multiple markets."""
        self._create_test_data()
        ticks = get_filtered_ticks(
            market_ids=["market_a", "market_b"], db_path=self.test_db_path
        )
        self.assertEqual(len(ticks), 5)

    def test_filter_by_start_date(self):
        """Test filtering by start date."""
        self._create_test_data()
        ticks = get_filtered_ticks(
            start=datetime(2024, 1, 5, 11, 0, 0), db_path=self.test_db_path
        )
        # Should include: market_a 11:00, 12:00; market_b 11:30; market_c 10:00 (Jan 6)
        self.assertEqual(len(ticks), 4)

    def test_filter_by_end_date(self):
        """Test filtering by end date."""
        self._create_test_data()
        ticks = get_filtered_ticks(
            end=datetime(2024, 1, 5, 11, 0, 0), db_path=self.test_db_path
        )
        # Should include: market_a 10:00, 11:00; market_b 10:30
        self.assertEqual(len(ticks), 3)

    def test_filter_by_date_range(self):
        """Test filtering by both start and end date."""
        self._create_test_data()
        ticks = get_filtered_ticks(
            start=datetime(2024, 1, 5, 10, 30, 0),
            end=datetime(2024, 1, 5, 11, 30, 0),
            db_path=self.test_db_path,
        )
        # Should include: market_a 11:00; market_b 10:30, 11:30
        self.assertEqual(len(ticks), 3)

    def test_combined_filters(self):
        """Test combining market and date filters."""
        self._create_test_data()
        ticks = get_filtered_ticks(
            market_ids=["market_a"],
            start=datetime(2024, 1, 5, 10, 30, 0),
            db_path=self.test_db_path,
        )
        # Should include: market_a 11:00, 12:00
        self.assertEqual(len(ticks), 2)

    def test_ticks_sorted_by_timestamp(self):
        """Test that ticks are sorted by timestamp."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        timestamps = [tick["timestamp"] for tick in ticks]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_empty_result(self):
        """Test filtering that returns no results."""
        self._create_test_data()
        ticks = get_filtered_ticks(
            market_ids=["nonexistent_market"], db_path=self.test_db_path
        )
        self.assertEqual(ticks, [])


class TestExportToCsv(TestExportHistory):
    """Test export_to_csv function."""

    def test_export_empty_list(self):
        """Test exporting empty list returns 0."""
        output_path = os.path.join(self.test_output_dir, "empty.csv")
        count = export_to_csv([], output_path)
        self.assertEqual(count, 0)

    def test_export_basic(self):
        """Test basic CSV export."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.csv")

        count = export_to_csv(ticks, output_path)

        self.assertEqual(count, 6)
        self.assertTrue(os.path.exists(output_path))

    def test_csv_has_correct_columns(self):
        """Test that CSV has correct column headers."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.csv")

        export_to_csv(ticks, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            self.assertIn("market_id", fieldnames)
            self.assertIn("timestamp", fieldnames)
            self.assertIn("yes_price", fieldnames)
            self.assertIn("no_price", fieldnames)
            self.assertIn("volume", fieldnames)
            self.assertIn("depth_summary", fieldnames)

    def test_csv_content_correct(self):
        """Test that CSV content is correct."""
        self._create_test_data()
        ticks = get_filtered_ticks(market_ids=["market_a"], db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.csv")

        export_to_csv(ticks, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["market_id"], "market_a")
        self.assertEqual(float(rows[0]["yes_price"]), 0.60)

    def test_csv_depth_summary_serialized(self):
        """Test that depth_summary is serialized as JSON in CSV."""
        self._create_test_data()
        ticks = get_filtered_ticks(market_ids=["market_b"], db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.csv")

        export_to_csv(ticks, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find the row with depth_summary
        depth_row = [r for r in rows if r["depth_summary"]][0]
        depth_data = json.loads(depth_row["depth_summary"])
        self.assertEqual(depth_data["total_depth"], 1000)

    def test_creates_output_directory(self):
        """Test that export creates output directory if needed."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        nested_path = os.path.join(self.test_dir, "nested", "dir", "export.csv")

        export_to_csv(ticks, nested_path)

        self.assertTrue(os.path.exists(nested_path))


class TestExportToJsonl(TestExportHistory):
    """Test export_to_jsonl function."""

    def test_export_empty_list(self):
        """Test exporting empty list returns 0."""
        output_path = os.path.join(self.test_output_dir, "empty.jsonl")
        count = export_to_jsonl([], output_path)
        self.assertEqual(count, 0)

    def test_export_basic(self):
        """Test basic JSONL export."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.jsonl")

        count = export_to_jsonl(ticks, output_path)

        self.assertEqual(count, 6)
        self.assertTrue(os.path.exists(output_path))

    def test_jsonl_each_line_valid_json(self):
        """Test that each line in JSONL is valid JSON."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.jsonl")

        export_to_jsonl(ticks, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                # This should not raise
                data = json.loads(line.strip())
                self.assertIsInstance(data, dict)

    def test_jsonl_content_correct(self):
        """Test that JSONL content is correct."""
        self._create_test_data()
        ticks = get_filtered_ticks(market_ids=["market_a"], db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.jsonl")

        export_to_jsonl(ticks, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 3)
        first_tick = json.loads(lines[0])
        self.assertEqual(first_tick["market_id"], "market_a")
        self.assertEqual(first_tick["yes_price"], 0.60)

    def test_jsonl_preserves_depth_summary_dict(self):
        """Test that depth_summary is preserved as dict in JSONL."""
        self._create_test_data()
        ticks = get_filtered_ticks(market_ids=["market_b"], db_path=self.test_db_path)
        output_path = os.path.join(self.test_output_dir, "export.jsonl")

        export_to_jsonl(ticks, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the line with depth_summary
        for line in lines:
            tick = json.loads(line)
            if tick.get("depth_summary"):
                self.assertIsInstance(tick["depth_summary"], dict)
                self.assertEqual(tick["depth_summary"]["total_depth"], 1000)
                break

    def test_creates_output_directory(self):
        """Test that export creates output directory if needed."""
        self._create_test_data()
        ticks = get_filtered_ticks(db_path=self.test_db_path)
        nested_path = os.path.join(self.test_dir, "nested", "dir", "export.jsonl")

        export_to_jsonl(ticks, nested_path)

        self.assertTrue(os.path.exists(nested_path))


class TestParseDate(TestExportHistory):
    """Test parse_date function."""

    def test_parse_none(self):
        """Test parsing None returns None."""
        result = parse_date(None)
        self.assertIsNone(result)

    def test_parse_date_only(self):
        """Test parsing date-only string."""
        result = parse_date("2024-01-15")
        self.assertEqual(result, datetime(2024, 1, 15, 0, 0, 0))

    def test_parse_datetime(self):
        """Test parsing datetime string."""
        result = parse_date("2024-01-15T10:30:00")
        self.assertEqual(result, datetime(2024, 1, 15, 10, 30, 0))

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_date("15-01-2024")
        self.assertIn("Invalid date format", str(context.exception))

    def test_parse_invalid_string(self):
        """Test parsing invalid string raises ValueError."""
        with self.assertRaises(ValueError):
            parse_date("not-a-date")


if __name__ == "__main__":
    unittest.main()
