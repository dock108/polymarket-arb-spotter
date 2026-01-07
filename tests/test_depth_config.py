"""
Unit tests for depth configuration load/save helpers.

Tests the load_depth_config and save_depth_config functions.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.core.depth_scanner import (
    load_depth_config,
    save_depth_config,
    DEFAULT_CONFIG,
    detect_depth_signals,
)


class TestDepthConfigHelpers(unittest.TestCase):
    """Test depth configuration load/save helpers."""

    def setUp(self):
        """Create a temporary directory for test config files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.test_dir, "test_depth_config.json")

    def tearDown(self):
        """Clean up temporary test files."""
        # Clean up any files in test directory
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

        # Clean up any nested directories that might have been created
        if os.path.exists(self.test_dir):
            for root, dirs, files in os.walk(self.test_dir, topdown=False):
                for name in files:
                    try:
                        os.remove(os.path.join(root, name))
                    except OSError:
                        pass
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except OSError:
                        pass
            try:
                os.rmdir(self.test_dir)
            except OSError:
                pass

    def test_load_default_config_creates_file(self):
        """Test that loading config creates default file if it doesn't exist."""
        config = load_depth_config(self.test_config_path)

        # Should return default config
        self.assertEqual(config["min_depth"], DEFAULT_CONFIG["min_depth"])
        self.assertEqual(config["max_gap"], DEFAULT_CONFIG["max_gap"])
        self.assertEqual(config["imbalance_ratio"], DEFAULT_CONFIG["imbalance_ratio"])
        self.assertEqual(config["markets_to_watch"], DEFAULT_CONFIG["markets_to_watch"])

        # File should have been created
        self.assertTrue(os.path.exists(self.test_config_path))

    def test_save_and_load_config(self):
        """Test saving and loading custom configuration."""
        custom_config = {
            "min_depth": 1000.0,
            "max_gap": 0.05,
            "imbalance_ratio": 500.0,
            "markets_to_watch": ["market1", "market2", "market3"],
        }

        # Save custom config
        save_depth_config(custom_config, self.test_config_path)

        # Load it back
        loaded_config = load_depth_config(self.test_config_path)

        # Verify all values match
        self.assertEqual(loaded_config["min_depth"], 1000.0)
        self.assertEqual(loaded_config["max_gap"], 0.05)
        self.assertEqual(loaded_config["imbalance_ratio"], 500.0)
        self.assertEqual(
            loaded_config["markets_to_watch"], ["market1", "market2", "market3"]
        )

    def test_load_config_with_missing_keys(self):
        """Test that loading config with missing keys merges with defaults."""
        # Create config with only some keys
        partial_config = {"min_depth": 2000.0}

        # Save partial config
        with open(self.test_config_path, "w") as f:
            json.dump(partial_config, f)

        # Load config
        loaded_config = load_depth_config(self.test_config_path)

        # Should have custom value for min_depth
        self.assertEqual(loaded_config["min_depth"], 2000.0)
        # Should have defaults for other keys
        self.assertEqual(loaded_config["max_gap"], DEFAULT_CONFIG["max_gap"])
        self.assertEqual(
            loaded_config["imbalance_ratio"], DEFAULT_CONFIG["imbalance_ratio"]
        )
        self.assertEqual(
            loaded_config["markets_to_watch"], DEFAULT_CONFIG["markets_to_watch"]
        )

    def test_save_config_creates_directory(self):
        """Test that save_config creates parent directory if it doesn't exist."""
        nested_path = os.path.join(self.test_dir, "subdir", "config.json")

        config = {
            "min_depth": 750.0,
            "max_gap": 0.08,
            "imbalance_ratio": 400.0,
            "markets_to_watch": [],
        }

        # Save to nested path
        save_depth_config(config, nested_path)

        # Verify file was created
        self.assertTrue(os.path.exists(nested_path))

        # Verify content
        with open(nested_path, "r") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["min_depth"], 750.0)

        # Cleanup
        os.remove(nested_path)
        os.rmdir(os.path.dirname(nested_path))

    def test_config_json_format(self):
        """Test that saved config is properly formatted JSON."""
        config = {
            "min_depth": 600.0,
            "max_gap": 0.12,
            "imbalance_ratio": 350.0,
            "markets_to_watch": ["test_market"],
        }

        save_depth_config(config, self.test_config_path)

        # Read raw file content
        with open(self.test_config_path, "r") as f:
            content = f.read()

        # Should be valid JSON
        parsed = json.loads(content)
        self.assertEqual(parsed["min_depth"], 600.0)

        # Should be pretty-printed (indented)
        self.assertIn("\n", content)
        self.assertIn("  ", content)

    def test_load_config_with_invalid_json(self):
        """Test that loading invalid JSON raises JSONDecodeError."""
        # Write invalid JSON to file
        with open(self.test_config_path, "w") as f:
            f.write("{ invalid json }")

        # Should raise JSONDecodeError
        with self.assertRaises(json.JSONDecodeError):
            load_depth_config(self.test_config_path)

    def test_markets_to_watch_list(self):
        """Test that markets_to_watch can be a list of strings."""
        config = {
            "min_depth": 500.0,
            "max_gap": 0.10,
            "imbalance_ratio": 300.0,
            "markets_to_watch": [
                "market_id_1",
                "market_id_2",
                "market_id_3",
                "market_id_4",
            ],
        }

        save_depth_config(config, self.test_config_path)
        loaded = load_depth_config(self.test_config_path)

        self.assertIsInstance(loaded["markets_to_watch"], list)
        self.assertEqual(len(loaded["markets_to_watch"]), 4)
        self.assertIn("market_id_1", loaded["markets_to_watch"])

    def test_detect_signals_uses_custom_config(self):
        """Test that detect_depth_signals uses custom config values."""
        # Create metrics that would trigger with default thresholds
        # but not with custom higher thresholds
        metrics = {
            "total_yes_depth": 300.0,
            "total_no_depth": 300.0,
            "top_gap_yes": 0.08,
            "top_gap_no": 0.08,
            "imbalance": 0.0,
        }

        # With default thresholds, total depth is 600 which is above 500 threshold
        # so it should NOT trigger thin_depth signal
        default_signals = detect_depth_signals(metrics)
        self.assertEqual(len(default_signals), 0)

        # Now with custom config that has higher min_depth threshold
        custom_config = {
            "min_depth": 1000.0,  # Higher threshold
            "max_gap": 0.10,
            "imbalance_ratio": 300.0,
            "markets_to_watch": [],
        }

        custom_signals = detect_depth_signals(metrics, config=custom_config)
        # Should trigger thin_depth (600 < 1000)
        self.assertEqual(len(custom_signals), 1)
        self.assertEqual(custom_signals[0].signal_type, "thin_depth")

    def test_detect_signals_uses_custom_gap_threshold(self):
        """Test that detect_depth_signals uses custom max_gap threshold."""
        metrics = {
            "total_yes_depth": 1000.0,
            "total_no_depth": 1000.0,
            "top_gap_yes": 0.07,  # Between 0.05 and 0.10
            "top_gap_no": 0.07,
            "imbalance": 0.0,
        }

        # With default threshold (0.10), should not trigger
        default_signals = detect_depth_signals(metrics)
        self.assertEqual(len(default_signals), 0)

        # With custom lower threshold, should trigger
        custom_config = {
            "min_depth": 500.0,
            "max_gap": 0.05,  # Lower threshold
            "imbalance_ratio": 300.0,
            "markets_to_watch": [],
        }

        custom_signals = detect_depth_signals(metrics, config=custom_config)
        self.assertEqual(len(custom_signals), 1)
        self.assertEqual(custom_signals[0].signal_type, "large_gap")

    def test_detect_signals_uses_custom_imbalance_threshold(self):
        """Test that detect_depth_signals uses custom imbalance_ratio threshold."""
        metrics = {
            "total_yes_depth": 1000.0,
            "total_no_depth": 800.0,
            "top_gap_yes": 0.05,
            "top_gap_no": 0.05,
            "imbalance": 200.0,  # Between 100 and 300
        }

        # With default threshold (300), should not trigger
        default_signals = detect_depth_signals(metrics)
        self.assertEqual(len(default_signals), 0)

        # With custom lower threshold, should trigger
        custom_config = {
            "min_depth": 500.0,
            "max_gap": 0.10,
            "imbalance_ratio": 100.0,  # Lower threshold
            "markets_to_watch": [],
        }

        custom_signals = detect_depth_signals(metrics, config=custom_config)
        self.assertEqual(len(custom_signals), 1)
        self.assertEqual(custom_signals[0].signal_type, "strong_imbalance")

    def test_empty_markets_to_watch(self):
        """Test that empty markets_to_watch list is handled correctly."""
        config = {
            "min_depth": 500.0,
            "max_gap": 0.10,
            "imbalance_ratio": 300.0,
            "markets_to_watch": [],
        }

        save_depth_config(config, self.test_config_path)
        loaded = load_depth_config(self.test_config_path)

        self.assertEqual(loaded["markets_to_watch"], [])
        self.assertIsInstance(loaded["markets_to_watch"], list)


if __name__ == "__main__":
    unittest.main()
