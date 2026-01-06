"""
Depth scanner for analyzing orderbook depth metrics.

This module provides functionality to analyze orderbook depth for YES and NO
outcomes, calculating metrics such as total depth, top-of-book gaps, and
imbalances.
"""

from typing import Dict, Any


def analyze_depth(orderbook: Dict[str, Any]) -> Dict[str, float]:
    """
    Analyze orderbook depth and return key metrics.

    This function processes an orderbook dictionary containing bids and asks,
    and computes depth metrics for both YES and NO outcomes. For binary markets,
    YES and NO depths are complementary since buying YES is equivalent to
    selling NO.

    Args:
        orderbook: Dictionary containing orderbook data with structure:
            {
                "bids": [{"price": str, "size": str}, ...],
                "asks": [{"price": str, "size": str}, ...]
            }

    Returns:
        Dictionary containing depth metrics:
            - total_yes_depth: Total volume available across all YES bids and asks
            - total_no_depth: Total volume available across all NO bids and asks
                             (derived from YES order book for binary markets)
            - top_gap_yes: Spread between best YES bid and ask prices
            - top_gap_no: Spread between best NO bid and ask prices
            - imbalance: Difference between YES and NO depth (total_yes_depth - total_no_depth)

    Example:
        >>> orderbook = {
        ...     "bids": [{"price": "0.45", "size": "100"}, {"price": "0.44", "size": "200"}],
        ...     "asks": [{"price": "0.55", "size": "150"}, {"price": "0.56", "size": "250"}]
        ... }
        >>> metrics = analyze_depth(orderbook)
        >>> metrics["total_yes_depth"]  # 100 + 200 + 150 + 250 = 700
        700.0
    """
    # Initialize metrics
    metrics = {
        "total_yes_depth": 0.0,
        "total_no_depth": 0.0,
        "top_gap_yes": 0.0,
        "top_gap_no": 0.0,
        "imbalance": 0.0,
    }

    # Extract bids and asks
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])

    # Calculate total YES depth (sum of all bid and ask sizes)
    yes_bid_depth = sum(float(bid.get("size", 0)) for bid in bids)
    yes_ask_depth = sum(float(ask.get("size", 0)) for ask in asks)
    total_yes_depth = yes_bid_depth + yes_ask_depth

    # For binary markets, NO depth equals YES depth
    # (buying YES = selling NO, and vice versa)
    total_no_depth = total_yes_depth

    metrics["total_yes_depth"] = total_yes_depth
    metrics["total_no_depth"] = total_no_depth

    # Calculate top-of-book gaps (spread between best bid and ask)
    if bids and asks:
        # Find best bid (highest price) and best ask (lowest price)
        sorted_bids = sorted(bids, key=lambda x: float(x.get("price", 0)), reverse=True)
        sorted_asks = sorted(asks, key=lambda x: float(x.get("price", 0)))

        yes_best_bid = float(sorted_bids[0].get("price", 0))
        yes_best_ask = float(sorted_asks[0].get("price", 0))

        # YES gap = ask - bid
        top_gap_yes = yes_best_ask - yes_best_bid

        # NO prices are derived: no_price = 1 - yes_price
        # no_best_bid = 1 - yes_best_ask
        # no_best_ask = 1 - yes_best_bid
        no_best_bid = 1.0 - yes_best_ask
        no_best_ask = 1.0 - yes_best_bid

        # NO gap = no_ask - no_bid = (1 - yes_best_bid) - (1 - yes_best_ask)
        #        = yes_best_ask - yes_best_bid = same as YES gap
        top_gap_no = no_best_ask - no_best_bid

        metrics["top_gap_yes"] = top_gap_yes
        metrics["top_gap_no"] = top_gap_no

    # Calculate imbalance (for binary markets, this is always 0 since depths are equal)
    metrics["imbalance"] = total_yes_depth - total_no_depth

    return metrics
