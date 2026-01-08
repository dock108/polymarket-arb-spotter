from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

@dataclass
class NormalizedMarket:
    """Normalized market data model."""
    id: str
    title: str
    yes_price: float
    no_price: float
    volume_24h: float
    liquidity: float
    last_updated: datetime
    clob_token_ids: List[str]
    question: str
    slug: str
    active: bool
    closed: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            "id": self.id,
            "name": self.title,  # legacy name
            "question": self.question,
            "title": self.title,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "volume_24h": self.volume_24h,
            "liquidity": self.liquidity,
            "last_updated": self.last_updated.isoformat(),
            "outcomes": [
                {"name": "Yes", "price": self.yes_price},
                {"name": "No", "price": self.no_price}
            ],
            "clobTokenIds": self.clob_token_ids,
            "active": self.active,
            "closed": self.closed
        }

