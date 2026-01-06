"""
Depth scanner for analyzing orderbook depth metrics.

This module provides functionality to analyze orderbook depth for YES and NO
outcomes, calculating metrics such as total depth, top-of-book gaps, and
imbalances.
"""

from typing import Dict, Any, List, Union


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
                             (equals total_yes_depth for binary markets since buying YES = selling NO)
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

        # For binary markets, NO gap equals YES gap
        # (because no_gap = (1 - yes_best_bid) - (1 - yes_best_ask) = yes_best_ask - yes_best_bid)
        top_gap_no = top_gap_yes

        metrics["top_gap_yes"] = top_gap_yes
        metrics["top_gap_no"] = top_gap_no

    # Calculate imbalance (for binary markets, this is always 0 since depths are equal)
    metrics["imbalance"] = total_yes_depth - total_no_depth

    return metrics


def analyze_normalized_depth(
    yes_bids: List[List[float]],
    yes_asks: List[List[float]],
    no_bids: List[List[float]],
    no_asks: List[List[float]],
) -> Dict[str, float]:
    """
    Analyze orderbook depth from normalized price/size lists.

    This function works with normalized orderbook levels (as returned by
    NormalizedOrderBook) to compute depth metrics for both YES and NO outcomes.

    Args:
        yes_bids: List of [price, size] pairs for YES bids (descending price order)
        yes_asks: List of [price, size] pairs for YES asks (ascending price order)
        no_bids: List of [price, size] pairs for NO bids (descending price order)
        no_asks: List of [price, size] pairs for NO asks (ascending price order)

    Returns:
        Dictionary containing depth metrics:
            - total_yes_depth: Total volume available across all YES bids and asks
            - total_no_depth: Total volume available across all NO bids and asks
            - yes_bid_depth: Total volume in YES bids
            - yes_ask_depth: Total volume in YES asks
            - no_bid_depth: Total volume in NO bids
            - no_ask_depth: Total volume in NO asks
            - top_gap_yes: Spread between best YES bid and ask prices
            - top_gap_no: Spread between best NO bid and ask prices
            - imbalance: Difference between YES and NO depth

    Example:
        >>> yes_bids = [[0.45, 100.0], [0.44, 200.0]]
        >>> yes_asks = [[0.55, 150.0], [0.56, 250.0]]
        >>> no_bids = [[0.45, 150.0], [0.44, 250.0]]
        >>> no_asks = [[0.55, 100.0], [0.56, 200.0]]
        >>> metrics = analyze_normalized_depth(yes_bids, yes_asks, no_bids, no_asks)
        >>> metrics["total_yes_depth"]
        700.0
    """
    # Initialize metrics
    metrics = {
        "total_yes_depth": 0.0,
        "total_no_depth": 0.0,
        "yes_bid_depth": 0.0,
        "yes_ask_depth": 0.0,
        "no_bid_depth": 0.0,
        "no_ask_depth": 0.0,
        "top_gap_yes": 0.0,
        "top_gap_no": 0.0,
        "imbalance": 0.0,
    }

    # Calculate YES depths
    yes_bid_depth = sum(size for price, size in yes_bids) if yes_bids else 0.0
    yes_ask_depth = sum(size for price, size in yes_asks) if yes_asks else 0.0
    total_yes_depth = yes_bid_depth + yes_ask_depth

    # Calculate NO depths
    no_bid_depth = sum(size for price, size in no_bids) if no_bids else 0.0
    no_ask_depth = sum(size for price, size in no_asks) if no_asks else 0.0
    total_no_depth = no_bid_depth + no_ask_depth

    metrics["total_yes_depth"] = total_yes_depth
    metrics["total_no_depth"] = total_no_depth
    metrics["yes_bid_depth"] = yes_bid_depth
    metrics["yes_ask_depth"] = yes_ask_depth
    metrics["no_bid_depth"] = no_bid_depth
    metrics["no_ask_depth"] = no_ask_depth

    # Calculate top-of-book gaps
    if yes_bids and yes_asks:
        yes_best_bid = yes_bids[0][0]  # First bid (highest price)
        yes_best_ask = yes_asks[0][0]  # First ask (lowest price)
        metrics["top_gap_yes"] = yes_best_ask - yes_best_bid

    if no_bids and no_asks:
        no_best_bid = no_bids[0][0]  # First bid (highest price)
        no_best_ask = no_asks[0][0]  # First ask (lowest price)
        metrics["top_gap_no"] = no_best_ask - no_best_bid

    # Calculate imbalance
    metrics["imbalance"] = total_yes_depth - total_no_depth

    return metrics


def convert_normalized_to_raw(
    yes_bids: List[List[float]],
    yes_asks: List[List[float]],
) -> Dict[str, Any]:
    """
    Convert normalized orderbook levels to raw orderbook format.

    This utility function converts price/size lists back to the raw format
    expected by analyze_depth() for backward compatibility.

    Args:
        yes_bids: List of [price, size] pairs for YES bids
        yes_asks: List of [price, size] pairs for YES asks

    Returns:
        Dictionary with "bids" and "asks" keys containing raw orderbook data

    Example:
        >>> yes_bids = [[0.45, 100.0], [0.44, 200.0]]
        >>> yes_asks = [[0.55, 150.0], [0.56, 250.0]]
        >>> raw = convert_normalized_to_raw(yes_bids, yes_asks)
        >>> raw["bids"][0]
        {'price': '0.45', 'size': '100.0'}
    """
    bids = [{"price": str(price), "size": str(size)} for price, size in yes_bids]
    asks = [{"price": str(price), "size": str(size)} for price, size in yes_asks]

    return {"bids": bids, "asks": asks}
