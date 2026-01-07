# Wallet Profile Analytics

The wallet profile analytics module provides functionality to track and analyze trading performance of Polymarket wallets. This helps identify "smart wallets" based on their historical trading patterns and outcomes.

## Overview

The wallet profiles system builds on top of the [wallet feed](wallet_feed.md) infrastructure to calculate aggregated statistics and performance metrics for individual wallets. It supports:

- Per-wallet trading statistics
- Performance metrics based on market outcomes
- Ranking wallets by various criteria
- Identifying high-performing traders

## Core Features

### Wallet Statistics

For each wallet, the system tracks:

- **Total Trades**: Number of trades executed
- **Average Entry Price**: Volume-weighted average price across all trades
- **Total Volume**: Sum of all trade sizes
- **Markets Traded**: List of unique market IDs
- **Realized Outcomes**: Number of markets that have resolved
- **Win Rate**: Percentage of winning trades in resolved markets
- **Average ROI**: Return on investment across all resolved positions
- **Total Profit**: Cumulative profit/loss from resolved markets

### Performance Calculation

The system calculates win rate and ROI based on market outcomes:

1. **Win Rate**: For each resolved market, trades are marked as winning or losing based on whether the trade side matches the final outcome
2. **ROI**: Calculated as `(total_profit / total_volume) * 100`
3. **Profit/Loss**: 
   - Winning trade: `size * (1 - price)`
   - Losing trade: `-size * price`

## Usage

### Get Individual Wallet Profile

```python
from app.core.wallet_profiles import get_wallet_profile

# Define market outcomes (optional but recommended for accurate metrics)
market_outcomes = {
    "market_123": {"outcome": "yes", "resolved": True},
    "market_456": {"outcome": "no", "resolved": True},
}

# Get profile for a specific wallet
profile = get_wallet_profile(
    wallet="0x1234567890abcdef",
    market_outcomes=market_outcomes,
)

if profile:
    print(f"Wallet: {profile.wallet}")
    print(f"Total Trades: {profile.total_trades}")
    print(f"Win Rate: {profile.win_rate:.1f}%")
    print(f"Average ROI: {profile.avg_roi:.1f}%")
    print(f"Total Profit: ${profile.total_profit:.2f}")
```

### Rank Wallets

Rank wallets by different performance metrics:

```python
from app.core.wallet_profiles import rank_wallets

# Rank by win rate
top_by_win_rate = rank_wallets(
    by="win_rate",
    market_outcomes=market_outcomes,
    min_trades=5,  # Require at least 5 trades
    limit=10,
)

# Rank by total profit
top_by_profit = rank_wallets(
    by="profit",
    market_outcomes=market_outcomes,
    min_trades=5,
    limit=10,
)

# Rank by ROI
top_by_roi = rank_wallets(
    by="roi",
    market_outcomes=market_outcomes,
    min_trades=5,
    limit=10,
)

# Rank by trading volume
top_by_volume = rank_wallets(
    by="volume",
    min_trades=1,
    limit=10,
)
```

### Get All Wallet Profiles

Retrieve profiles for all wallets in the database:

```python
from app.core.wallet_profiles import get_all_wallet_profiles

# Get all profiles with at least 1 trade
all_profiles = get_all_wallet_profiles(
    market_outcomes=market_outcomes,
    min_trades=1,
)

# Filter for "smart wallets"
smart_wallets = [
    p for p in all_profiles
    if p.total_trades >= 5  # Sufficient history
    and p.win_rate > 60     # Above 60% win rate
    and p.avg_roi > 0       # Positive returns
]
```

## Market Outcomes

To calculate accurate win rates and ROI, you need to provide market outcome data. The format is:

```python
market_outcomes = {
    "market_id": {
        "outcome": "yes" or "no",  # Winning outcome
        "resolved": True,           # Whether market is resolved
    }
}
```

Without market outcomes, the system will still calculate other statistics (trades, volume, markets traded) but win rate and ROI will be 0.

## Example Script

A complete demonstration is available in `scripts/example_wallet_profiles.py`:

```bash
# Run from repository root
PYTHONPATH=/path/to/polymarket-arb-spotter python scripts/example_wallet_profiles.py
```

This script demonstrates:
1. Creating sample trade data
2. Getting individual wallet profiles
3. Ranking wallets by different metrics
4. Identifying "smart wallets"

## Integration with Wallet Feed

The wallet profiles module builds on the wallet feed infrastructure:

```python
from app.core.wallet_feed import WalletFeed, WalletTrade
from app.core.wallet_profiles import get_wallet_profile

# 1. First, ingest trades using wallet feed
feed = WalletFeed(db_path="data/wallet_trades.db")
feed.ingest_trades(wallet="0x1234567890abcdef", limit=100)

# 2. Then analyze the wallet's performance
profile = get_wallet_profile(
    wallet="0x1234567890abcdef",
    db_path="data/wallet_trades.db",
)
```

## API Reference

### WalletProfile

Dataclass containing wallet trading statistics:

```python
@dataclass
class WalletProfile:
    wallet: str                    # Wallet address
    total_trades: int              # Number of trades
    avg_entry_price: float         # Volume-weighted average price
    realized_outcomes: int         # Number of resolved markets
    win_rate: float                # Percentage of winning trades
    avg_roi: float                 # Average return on investment
    markets_traded: List[str]      # List of market IDs
    categories: Set[str]           # Market categories (if available)
    total_volume: float            # Total trading volume
    total_profit: float            # Total profit/loss
```

### get_wallet_profile()

```python
def get_wallet_profile(
    wallet: str,
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
    db_path: str = "data/wallet_trades.db",
) -> Optional[WalletProfile]:
```

Get trading profile for a specific wallet.

**Parameters:**
- `wallet`: Wallet address to get profile for
- `market_outcomes`: Optional dict mapping market_id to outcome info
- `db_path`: Path to wallet trades database

**Returns:**
- `WalletProfile` object or `None` if wallet not found

### rank_wallets()

```python
def rank_wallets(
    by: str = "win_rate",
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
    min_trades: int = 5,
    limit: int = 100,
    db_path: str = "data/wallet_trades.db",
) -> List[WalletProfile]:
```

Rank wallets by performance metrics.

**Parameters:**
- `by`: Ranking metric - "win_rate", "profit", "roi", or "volume"
- `market_outcomes`: Optional dict mapping market_id to outcome info
- `min_trades`: Minimum number of trades required for ranking
- `limit`: Maximum number of wallets to return
- `db_path`: Path to wallet trades database

**Returns:**
- List of `WalletProfile` objects sorted by the specified metric

### get_all_wallet_profiles()

```python
def get_all_wallet_profiles(
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
    min_trades: int = 1,
    db_path: str = "data/wallet_trades.db",
) -> List[WalletProfile]:
```

Get profiles for all wallets in the database.

**Parameters:**
- `market_outcomes`: Optional dict mapping market_id to outcome info
- `min_trades`: Minimum number of trades required
- `db_path`: Path to wallet trades database

**Returns:**
- List of `WalletProfile` objects for all wallets

## Best Practices

### Identifying Smart Wallets

Use a combination of criteria to identify high-performing traders:

```python
def is_smart_wallet(profile: WalletProfile) -> bool:
    """Determine if a wallet shows consistent smart trading patterns."""
    return (
        profile.total_trades >= 10       # Sufficient history
        and profile.realized_outcomes >= 5  # Multiple resolved positions
        and profile.win_rate >= 55       # Above average win rate
        and profile.avg_roi > 5          # Positive returns after costs
        and profile.total_profit > 0     # Actual profitability
    )

smart_wallets = [
    p for p in get_all_wallet_profiles(market_outcomes)
    if is_smart_wallet(p)
]
```

### Performance Monitoring

Set up periodic analysis to track emerging patterns:

```python
import time
from app.core.wallet_feed import WalletFeed
from app.core.wallet_profiles import rank_wallets

feed = WalletFeed()

while True:
    # Ingest recent trades
    feed.ingest_trades(limit=100)
    
    # Identify top performers
    top_traders = rank_wallets(
        by="roi",
        min_trades=10,
        limit=20,
    )
    
    # Alert on significant changes
    for profile in top_traders:
        if profile.avg_roi > 30:  # Exceptional performance
            print(f"🌟 Smart wallet detected: {profile.wallet}")
            print(f"   ROI: {profile.avg_roi:.1f}%")
            print(f"   Win Rate: {profile.win_rate:.1f}%")
    
    time.sleep(3600)  # Check every hour
```

## Testing

The module includes comprehensive test coverage in `tests/test_wallet_profiles.py`:

```bash
# Run wallet profiles tests
python -m pytest tests/test_wallet_profiles.py -v

# Run with coverage
python -m pytest tests/test_wallet_profiles.py --cov=app.core.wallet_profiles
```

## See Also

- [Wallet Feed Documentation](wallet_feed.md) - Trade ingestion and storage
- [Scripts Documentation](scripts.md) - Example scripts
- [Replay Engine](replay_engine.md) - Historical analysis
