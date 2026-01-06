#!/usr/bin/env python3
"""
Speed test script for arbitrage detection using mock data.

This is a convenience wrapper that delegates to the main run_mock_speed.py
script at the repository root.

Usage:
    python scripts/run_mock_speed.py [OPTIONS]

    Options are the same as the main script:
        --duration SECONDS        Duration of speed test (default: 60)
        --mode {speed,batch,alert-test}  Test mode
        --arb-frequency FLOAT     Probability of arbitrage (0.0-1.0, default: 0.3)
        --target-alerts N         Target alerts for alert-test mode (default: 50)
        --load-snapshots FILE     Load snapshots from JSON file
        --export-snapshots FILE   Export snapshots to JSON file

Example to generate 50 alerts rapidly:
    python scripts/run_mock_speed.py --mode alert-test --target-alerts 50 --arb-frequency 0.5
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import and run the main module
from run_mock_speed import main

if __name__ == "__main__":
    sys.exit(main())
