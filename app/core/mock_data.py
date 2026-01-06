"""
Mock data generator for testing and simulation.

Provides functionality to generate fake market snapshots with configurable
arbitrage frequency for testing and simulating arbitrage detection.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


class MockDataGenerator:
    """Generate mock market data for testing."""

    def __init__(self, seed: int = 42, arb_frequency: float = 0.2):
        """
        Initialize mock data generator.

        Args:
            seed: Random seed for reproducibility
            arb_frequency: Probability (0.0-1.0) that a generated market
                          will contain an arbitrage opportunity (default: 0.2 = 20%)
        """
        random.seed(seed)
        self._seed = seed
        self.market_counter = 0
        self.arb_frequency = max(0.0, min(1.0, arb_frequency))

    def set_arb_frequency(self, frequency: float) -> None:
        """
        Set the frequency of arbitrage opportunities.

        Args:
            frequency: Probability (0.0-1.0) that generated markets contain arbitrage
        """
        self.arb_frequency = max(0.0, min(1.0, frequency))

    def generate_market(self) -> Dict[str, Any]:
        """
        Generate a single mock market.

        Returns:
            Dictionary containing market data
        """
        self.market_counter += 1
        market_id = f"market_{self.market_counter}"

        # Generate binary outcome market
        yes_price = random.uniform(0.3, 0.7)
        # Introduce small inefficiency but keep within bounds
        inefficiency = random.uniform(-0.02, 0.02)
        no_price = max(0.01, min(0.99, 1.0 - yes_price + inefficiency))

        return {
            "id": market_id,
            "name": f"Mock Market {self.market_counter}",
            "question": f"Will event {self.market_counter} occur?",
            "outcomes": [
                {
                    "name": "Yes",
                    "price": yes_price,
                    "volume": random.uniform(1000, 100000),
                },
                {
                    "name": "No",
                    "price": no_price,
                    "volume": random.uniform(1000, 100000),
                },
            ],
            "created_at": datetime.now().isoformat(),
            "expires_at": (
                datetime.now() + timedelta(days=random.randint(1, 30))
            ).isoformat(),
            "volume": random.uniform(10000, 1000000),
            "liquidity": random.uniform(5000, 500000),
        }

    def generate_markets(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Generate multiple mock markets.

        Args:
            count: Number of markets to generate

        Returns:
            List of market data dictionaries
        """
        return [self.generate_market() for _ in range(count)]

    def generate_arbitrage_opportunity(self) -> Dict[str, Any]:
        """
        Generate a mock arbitrage opportunity.

        Returns:
            Dictionary containing market data with arbitrage opportunity
        """
        market = self.generate_market()

        # Create an obvious arbitrage by manipulating prices
        # Sum of prices < 1.0 means buying both YES and NO guarantees profit
        profit_margin = random.uniform(0.03, 0.15)  # 3-15% profit
        base_price = (1.0 - profit_margin) / 2
        variation = random.uniform(-0.1, 0.1)

        market["outcomes"][0]["price"] = max(0.01, min(0.99, base_price + variation))
        market["outcomes"][1]["price"] = max(0.01, min(0.99, base_price - variation))

        return market

    def generate_random_snapshot(self) -> Dict[str, Any]:
        """
        Generate a random market snapshot that may contain arbitrage.

        Uses arb_frequency to determine whether to generate an arbitrage
        opportunity or a normal market.

        Returns:
            Dictionary containing market data, potentially with arbitrage
        """
        if random.random() < self.arb_frequency:
            return self.generate_arbitrage_opportunity()
        return self.generate_market()

    def generate_snapshots(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Generate multiple random snapshots with configurable arbitrage frequency.

        Args:
            count: Number of snapshots to generate

        Returns:
            List of market data dictionaries, some with arbitrage opportunities
        """
        return [self.generate_random_snapshot() for _ in range(count)]

    def generate_price_update(self, market: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a price update for an existing market.

        Args:
            market: Existing market data

        Returns:
            Updated market data
        """
        updated_market = market.copy()
        updated_market["outcomes"] = [outcome.copy() for outcome in market["outcomes"]]

        # Add small random price changes
        for outcome in updated_market["outcomes"]:
            price_change = random.uniform(-0.02, 0.02)
            outcome["price"] = max(0.01, min(0.99, outcome["price"] + price_change))

        return updated_market

    def export_snapshots(
        self, count: int = 100, filepath: str = "data/mock_snapshots.json"
    ) -> str:
        """
        Export mock snapshots to JSON file for repeatable tests.

        Args:
            count: Number of snapshots to generate
            filepath: Path to save the JSON file

        Returns:
            Path to the saved file
        """
        # Use a separate Random instance for reproducible export
        # This avoids modifying global random state
        export_rng = random.Random(self._seed)

        snapshots = []
        for i in range(count):
            # Generate snapshot using local random instance
            market_id = f"market_{i + 1}"

            if export_rng.random() < self.arb_frequency:
                # Create arbitrage opportunity
                profit_margin = export_rng.uniform(0.03, 0.15)
                base_price = (1.0 - profit_margin) / 2
                variation = export_rng.uniform(-0.1, 0.1)
                yes_price = max(0.01, min(0.99, base_price + variation))
                no_price = max(0.01, min(0.99, base_price - variation))
            else:
                # Normal market
                yes_price = export_rng.uniform(0.3, 0.7)
                inefficiency = export_rng.uniform(-0.02, 0.02)
                no_price = max(0.01, min(0.99, 1.0 - yes_price + inefficiency))

            snapshots.append(
                {
                    "id": market_id,
                    "name": f"Mock Market {i + 1}",
                    "question": f"Will event {i + 1} occur?",
                    "outcomes": [
                        {
                            "name": "Yes",
                            "price": yes_price,
                            "volume": export_rng.uniform(1000, 100000),
                        },
                        {
                            "name": "No",
                            "price": no_price,
                            "volume": export_rng.uniform(1000, 100000),
                        },
                    ],
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (
                        datetime.now() + timedelta(days=export_rng.randint(1, 30))
                    ).isoformat(),
                    "volume": export_rng.uniform(10000, 1000000),
                    "liquidity": export_rng.uniform(5000, 500000),
                }
            )

        # Ensure directory exists
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Export with metadata
        export_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "seed": self._seed,
                "arb_frequency": self.arb_frequency,
                "count": count,
            },
            "snapshots": snapshots,
        }

        with open(path, "w") as f:
            json.dump(export_data, f, indent=2)

        return str(path)

    @staticmethod
    def load_snapshots(
        filepath: str = "data/mock_snapshots.json",
    ) -> List[Dict[str, Any]]:
        """
        Load mock snapshots from JSON file.

        Args:
            filepath: Path to the JSON file

        Returns:
            List of market data dictionaries

        Raises:
            FileNotFoundError: If the file does not exist
        """
        with open(filepath, "r") as f:
            data = json.load(f)

        # Handle both new format (with metadata) and old format (list only)
        if isinstance(data, dict) and "snapshots" in data:
            return data["snapshots"]
        return data
