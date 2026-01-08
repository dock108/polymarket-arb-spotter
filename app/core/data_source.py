from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from app.core.models import NormalizedMarket
from app.core.api_client import PolymarketAPIClient
from app.core.mock_data import MockDataGenerator
from app.core.logger import logger

class DataSource(ABC):
    """Abstract base class for market data sources."""
    
    @abstractmethod
    def get_markets(self, limit: int = 100) -> List[NormalizedMarket]:
        """Fetch list of markets."""
        pass

    @abstractmethod
    def get_market_details(self, market_id: str) -> Optional[NormalizedMarket]:
        """Fetch details for a specific market."""
        pass

class MockDataSource(DataSource):
    """Mock data source for testing and development."""
    
    def __init__(self, seed: int = 42, arb_frequency: float = 0.2):
        self.generator = MockDataGenerator(seed=seed, arb_frequency=arb_frequency)

    def get_markets(self, limit: int = 100) -> List[NormalizedMarket]:
        mock_markets = self.generator.generate_markets(count=limit)
        return [self._normalize(m) for m in mock_markets]

    def get_market_details(self, market_id: str) -> Optional[NormalizedMarket]:
        # For mock, we just generate a random one if it doesn't exist
        mock_market = self.generator.generate_market()
        mock_market["id"] = market_id
        return self._normalize(mock_market)

    def _normalize(self, m: Dict[str, Any]) -> NormalizedMarket:
        outcomes = m.get("outcomes", [])
        yes_price = 0.0
        no_price = 0.0
        for o in outcomes:
            if o["name"].lower() == "yes":
                yes_price = o["price"]
            elif o["name"].lower() == "no":
                no_price = o["price"]
        
        return NormalizedMarket(
            id=m["id"],
            title=m.get("name", ""),
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=m.get("volume", 0.0),
            liquidity=m.get("liquidity", 0.0),
            last_updated=datetime.now(),
            clob_token_ids=[],
            question=m.get("question", ""),
            slug=m.get("id", ""),
            active=True,
            closed=False
        )

class PolymarketLiveDataSource(DataSource):
    """Live data source using Polymarket API."""
    
    def __init__(self, api_client: Optional[PolymarketAPIClient] = None):
        self.client = api_client or PolymarketAPIClient()

    def get_markets(self, limit: int = 100) -> List[NormalizedMarket]:
        raw_markets = self.client.fetch_markets(limit=limit)
        normalized = []
        for m in raw_markets:
            try:
                nm = self._normalize(m)
                if nm:
                    normalized.append(nm)
            except Exception as e:
                logger.error(f"Error normalizing market {m.get('id')}: {e}")
        return normalized

    def get_market_details(self, market_id: str) -> Optional[NormalizedMarket]:
        raw_market = self.client.get_market_details(market_id)
        if not raw_market:
            return None
        return self._normalize(raw_market)

    def _normalize(self, m: Dict[str, Any]) -> Optional[NormalizedMarket]:
        try:
            # Handle JSON strings in Gamma API response
            clob_token_ids = m.get("clobTokenIds", [])
            if isinstance(clob_token_ids, str):
                clob_token_ids = json.loads(clob_token_ids)
            
            outcome_prices = m.get("outcomePrices", [])
            if isinstance(outcome_prices, str):
                outcome_prices = json.loads(outcome_prices)
            
            # Gamma prices are often just snapshots, CLOB is better but 
            # for the list view, outcomePrices is sufficient.
            yes_price = 0.0
            no_price = 0.0
            if outcome_prices and len(outcome_prices) >= 2:
                yes_price = float(outcome_prices[0])
                no_price = float(outcome_prices[1])
            
            return NormalizedMarket(
                id=m["id"],
                title=m.get("question", ""),
                yes_price=yes_price,
                no_price=no_price,
                volume_24h=float(m.get("volume24hr", 0.0)),
                liquidity=float(m.get("liquidity", 0.0)),
                last_updated=datetime.now(), # Or parse m.get("updatedAt")
                clob_token_ids=clob_token_ids,
                question=m.get("question", ""),
                slug=m.get("slug", ""),
                active=m.get("active", True),
                closed=m.get("closed", False)
            )
        except Exception as e:
            logger.error(f"Failed to normalize live market data: {e}")
            return None

def get_data_source(mode: Optional[str] = None) -> DataSource:
    """
    Get the appropriate data source based on mode.
    
    Args:
        mode: "mock" or "live". If None, uses config.mode.
        
    Returns:
        DataSource instance
    """
    from app.core.config import config
    
    target_mode = mode or config.mode
    
    if target_mode == "live":
        return PolymarketLiveDataSource()
    else:
        return MockDataSource()

