"""
Unit tests for mock data generator.
"""

import json
import os
import tempfile
import unittest
from app.core.mock_data import MockDataGenerator


class TestMockDataGenerator(unittest.TestCase):
    """Test mock data generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = MockDataGenerator(seed=42)

    def test_generate_single_market(self):
        """Test generating a single market."""
        market = self.generator.generate_market()

        self.assertIsNotNone(market)
        self.assertIn("id", market)
        self.assertIn("name", market)
        self.assertIn("outcomes", market)
        self.assertEqual(len(market["outcomes"]), 2)

    def test_generate_multiple_markets(self):
        """Test generating multiple markets."""
        markets = self.generator.generate_markets(count=10)

        self.assertEqual(len(markets), 10)

        # Check that market IDs are unique
        ids = [m["id"] for m in markets]
        self.assertEqual(len(ids), len(set(ids)))

    def test_price_validity(self):
        """Test that generated prices are valid."""
        market = self.generator.generate_market()

        for outcome in market["outcomes"]:
            price = outcome["price"]
            self.assertGreaterEqual(price, 0.0)
            self.assertLessEqual(price, 1.0)

    def test_arb_frequency_default(self):
        """Test default arbitrage frequency is 20%."""
        generator = MockDataGenerator(seed=42)
        self.assertEqual(generator.arb_frequency, 0.2)

    def test_arb_frequency_custom(self):
        """Test custom arbitrage frequency."""
        generator = MockDataGenerator(seed=42, arb_frequency=0.5)
        self.assertEqual(generator.arb_frequency, 0.5)

    def test_arb_frequency_bounds(self):
        """Test arbitrage frequency is clamped to valid range."""
        generator_low = MockDataGenerator(seed=42, arb_frequency=-0.5)
        self.assertEqual(generator_low.arb_frequency, 0.0)

        generator_high = MockDataGenerator(seed=42, arb_frequency=1.5)
        self.assertEqual(generator_high.arb_frequency, 1.0)

    def test_set_arb_frequency(self):
        """Test setting arbitrage frequency dynamically."""
        self.generator.set_arb_frequency(0.7)
        self.assertEqual(self.generator.arb_frequency, 0.7)

        self.generator.set_arb_frequency(-0.1)
        self.assertEqual(self.generator.arb_frequency, 0.0)

        self.generator.set_arb_frequency(1.2)
        self.assertEqual(self.generator.arb_frequency, 1.0)

    def test_generate_arbitrage_opportunity(self):
        """Test generating an arbitrage opportunity."""
        market = self.generator.generate_arbitrage_opportunity()

        self.assertIsNotNone(market)
        self.assertIn("outcomes", market)

        # Sum of prices should be less than 1 for arbitrage
        price_sum = sum(o["price"] for o in market["outcomes"])
        self.assertLess(price_sum, 1.0)

    def test_generate_random_snapshot(self):
        """Test generate_random_snapshot method."""
        snapshot = self.generator.generate_random_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertIn("id", snapshot)
        self.assertIn("outcomes", snapshot)

    def test_generate_snapshots(self):
        """Test generating multiple snapshots."""
        snapshots = self.generator.generate_snapshots(count=50)

        self.assertEqual(len(snapshots), 50)

        # With default arb_frequency of 0.2, expect roughly some arbitrage opportunities
        arb_count = 0
        for s in snapshots:
            price_sum = sum(o["price"] for o in s["outcomes"])
            if price_sum < 0.98:  # Arbitrage threshold
                arb_count += 1

        # Should have at least a few arbitrage opportunities
        self.assertGreater(arb_count, 0)

    def test_generate_snapshots_high_frequency(self):
        """Test generating snapshots with high arbitrage frequency."""
        generator = MockDataGenerator(seed=42, arb_frequency=1.0)
        snapshots = generator.generate_snapshots(count=20)

        # All should be arbitrage opportunities
        for s in snapshots:
            price_sum = sum(o["price"] for o in s["outcomes"])
            self.assertLess(price_sum, 1.0)

    def test_generate_snapshots_zero_frequency(self):
        """Test generating snapshots with zero arbitrage frequency."""
        generator = MockDataGenerator(seed=42, arb_frequency=0.0)
        snapshots = generator.generate_snapshots(count=20)

        # None should be obvious arbitrage opportunities (sum < 0.98)
        for s in snapshots:
            price_sum = sum(o["price"] for o in s["outcomes"])
            # Normal markets may still have small inefficiencies
            # but won't have the intentional arbitrage
            self.assertGreater(price_sum, 0.85)

    def test_export_snapshots(self):
        """Test exporting snapshots to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_snapshots.json")

            result_path = self.generator.export_snapshots(count=10, filepath=filepath)

            self.assertEqual(result_path, filepath)
            self.assertTrue(os.path.exists(filepath))

            with open(filepath, "r") as f:
                data = json.load(f)

            self.assertIn("metadata", data)
            self.assertIn("snapshots", data)
            self.assertEqual(len(data["snapshots"]), 10)
            self.assertEqual(data["metadata"]["count"], 10)
            self.assertEqual(data["metadata"]["seed"], 42)

    def test_load_snapshots(self):
        """Test loading snapshots from JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_snapshots.json")

            # Export first
            self.generator.export_snapshots(count=15, filepath=filepath)

            # Then load
            snapshots = MockDataGenerator.load_snapshots(filepath)

            self.assertEqual(len(snapshots), 15)
            self.assertIn("id", snapshots[0])

    def test_load_snapshots_file_not_found(self):
        """Test loading snapshots from non-existent file."""
        with self.assertRaises(FileNotFoundError):
            MockDataGenerator.load_snapshots("/nonexistent/path.json")

    def test_export_creates_directory(self):
        """Test export creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "subdir", "snapshots.json")

            result_path = self.generator.export_snapshots(count=5, filepath=filepath)

            self.assertTrue(os.path.exists(filepath))

    def test_price_update_preserves_structure(self):
        """Test that price update preserves market structure."""
        market = self.generator.generate_market()
        original_id = market["id"]
        original_name = market["name"]

        updated = self.generator.generate_price_update(market)

        # Structure should be preserved
        self.assertEqual(updated["id"], original_id)
        self.assertEqual(updated["name"], original_name)
        self.assertEqual(len(updated["outcomes"]), 2)

        # Original should not be modified
        self.assertIsNot(updated, market)
        self.assertIsNot(updated["outcomes"], market["outcomes"])


if __name__ == "__main__":
    unittest.main()
