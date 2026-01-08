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
    expires_at: Optional[datetime] = None  # Section 6.1
    category: Optional[str] = None         # Section 6.1

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
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "category": self.category,
            "outcomes": [
                {"name": "Yes", "price": self.yes_price},
                {"name": "No", "price": self.no_price}
            ],
            "clobTokenIds": self.clob_token_ids,
            "active": self.active,
            "closed": self.closed
        }

