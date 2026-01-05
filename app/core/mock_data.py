"""
Mock data generator for testing and simulation.

TODO: Add realistic market price generators
TODO: Add market volatility simulation
TODO: Implement time-series data generation
TODO: Add configurable market scenarios
TODO: Add edge case generators for testing
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any


class MockDataGenerator:
    """Generate mock market data for testing."""
    
    def __init__(self, seed: int = 42):
        """
        Initialize mock data generator.
        
        Args:
            seed: Random seed for reproducibility
            
        TODO: Add more sophisticated data generation
        """
        random.seed(seed)
        self.market_counter = 0
    
    def generate_market(self) -> Dict[str, Any]:
        """
        Generate a single mock market.
        
        Returns:
            Dictionary containing market data
            
        TODO: Add more realistic market parameters
        TODO: Add market metadata (volume, liquidity, etc.)
        """
        self.market_counter += 1
        market_id = f"market_{self.market_counter}"
        
        # Generate binary outcome market
        yes_price = random.uniform(0.3, 0.7)
        # Introduce small inefficiency but keep within bounds
        inefficiency = random.uniform(-0.02, 0.02)
        no_price = max(0.01, min(0.99, 1.0 - yes_price + inefficiency))
        
        return {
            'id': market_id,
            'name': f"Mock Market {self.market_counter}",
            'question': f"Will event {self.market_counter} occur?",
            'outcomes': [
                {'name': 'Yes', 'price': yes_price, 'volume': random.uniform(1000, 100000)},
                {'name': 'No', 'price': no_price, 'volume': random.uniform(1000, 100000)}
            ],
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=random.randint(1, 30))).isoformat(),
            'volume': random.uniform(10000, 1000000),
            'liquidity': random.uniform(5000, 500000)
        }
    
    def generate_markets(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Generate multiple mock markets.
        
        Args:
            count: Number of markets to generate
            
        Returns:
            List of market data dictionaries
            
        TODO: Add correlation between markets
        TODO: Add time-series progression
        """
        return [self.generate_market() for _ in range(count)]
    
    def generate_arbitrage_opportunity(self) -> Dict[str, Any]:
        """
        Generate a mock arbitrage opportunity.
        
        Returns:
            Dictionary containing arbitrage opportunity data
            
        TODO: Make opportunities more realistic
        TODO: Add various opportunity types
        """
        market = self.generate_market()
        
        # Create an obvious arbitrage by manipulating prices
        market['outcomes'][0]['price'] = 0.45
        market['outcomes'][1]['price'] = 0.45
        
        return market
    
    def generate_price_update(self, market: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a price update for an existing market.
        
        Args:
            market: Existing market data
            
        Returns:
            Updated market data
            
        TODO: Add realistic price movement patterns
        TODO: Add volume-based price impact
        """
        updated_market = market.copy()
        
        # Add small random price changes
        for outcome in updated_market['outcomes']:
            price_change = random.uniform(-0.02, 0.02)
            outcome['price'] = max(0.01, min(0.99, outcome['price'] + price_change))
        
        return updated_market
