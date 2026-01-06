#!/usr/bin/env python3
"""
Example script demonstrating depth_config.json usage.

This script shows how to:
1. Load the depth configuration
2. Modify configuration values
3. Save configuration back to file
4. Use custom config with detect_depth_signals

Usage:
    python scripts/example_depth_config.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.depth_scanner import (
    load_depth_config,
    save_depth_config,
    detect_depth_signals,
    analyze_depth,
)


def main():
    print("Depth Configuration Demo")
    print("=" * 60)

    # Load current configuration
    print("\n1. Loading configuration from data/depth_config.json:")
    config = load_depth_config()
    print(f"   min_depth: {config['min_depth']}")
    print(f"   max_gap: {config['max_gap']}")
    print(f"   imbalance_ratio: {config['imbalance_ratio']}")
    print(f"   markets_to_watch: {config['markets_to_watch']}")

    # Example: Modify configuration
    print("\n2. Example: Modifying configuration")
    print("   Setting min_depth to 1000.0 for stricter liquidity requirements")
    config["min_depth"] = 1000.0
    config["markets_to_watch"] = ["example_market_1", "example_market_2"]

    # Save modified configuration
    print("\n3. Saving modified configuration")
    save_depth_config(config)
    print("   ✓ Configuration saved to data/depth_config.json")

    # Reload to verify
    print("\n4. Reloading configuration to verify changes")
    reloaded = load_depth_config()
    print(f"   min_depth: {reloaded['min_depth']}")
    print(f"   markets_to_watch: {reloaded['markets_to_watch']}")

    # Example: Using config with detect_depth_signals
    print("\n5. Using configuration with orderbook analysis")
    example_orderbook = {
        "bids": [{"price": "0.48", "size": "300"}, {"price": "0.47", "size": "200"}],
        "asks": [{"price": "0.52", "size": "300"}, {"price": "0.53", "size": "200"}],
    }

    metrics = analyze_depth(example_orderbook)
    signals = detect_depth_signals(metrics)  # Uses loaded config

    print(f"   Total depth: {metrics['total_yes_depth'] + metrics['total_no_depth']}")
    print(f"   Signals triggered: {len(signals)}")
    for signal in signals:
        print(f"     - {signal.signal_type}: {signal.reason}")

    # Reset to defaults
    print("\n6. Resetting to default configuration")
    default_config = {
        "min_depth": 500.0,
        "max_gap": 0.10,
        "imbalance_ratio": 300.0,
        "markets_to_watch": [],
    }
    save_depth_config(default_config)
    print("   ✓ Configuration reset to defaults")

    print("\n" + "=" * 60)
    print("Demo completed!")


if __name__ == "__main__":
    main()
