"""
Depth scanner for analyzing orderbook depth metrics.

This module provides functionality to analyze orderbook depth for YES and NO
outcomes, calculating metrics such as total depth, top-of-book gaps, and
imbalances.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Union, Optional


# Default configuration file path
DEFAULT_CONFIG_PATH = "data/depth_config.json"

# Default configuration values
DEFAULT_CONFIG = {
    "min_depth": 500.0,
    "max_gap": 0.10,
    "imbalance_ratio": 300.0,
    "markets_to_watch": [],
}


def load_depth_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load depth configuration from JSON file.

    Args:
        config_path: Path to the configuration file. If None, uses DEFAULT_CONFIG_PATH.

    Returns:
        Dictionary containing configuration values with keys:
            - min_depth: Minimum total depth threshold
            - max_gap: Maximum acceptable bid-ask spread
            - imbalance_ratio: Maximum acceptable depth imbalance
            - markets_to_watch: List of market IDs to monitor

    Raises:
        json.JSONDecodeError: If config file contains invalid JSON

    Example:
        >>> config = load_depth_config()
        >>> config["min_depth"]
        500.0
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    path = Path(config_path)

    # If file doesn't exist, create it with default values
    if not path.exists():
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        # Create default config file
        save_depth_config(DEFAULT_CONFIG, config_path)
        return DEFAULT_CONFIG.copy()

    # Load from file
    with open(path, "r") as f:
        config = json.load(f)

    # Merge with defaults to ensure all keys are present
    merged_config = DEFAULT_CONFIG.copy()
    merged_config.update(config)

    return merged_config


def save_depth_config(
    config: Dict[str, Any], config_path: Optional[str] = None
) -> None:
    """
    Save depth configuration to JSON file.

    Args:
        config: Configuration dictionary with keys:
            - min_depth: Minimum total depth threshold
            - max_gap: Maximum acceptable bid-ask spread
            - imbalance_ratio: Maximum acceptable depth imbalance
            - markets_to_watch: List of market IDs to monitor
        config_path: Path to save the configuration file. If None, uses DEFAULT_CONFIG_PATH.

    Raises:
        OSError: If file cannot be written

    Example:
        >>> config = {
        ...     "min_depth": 1000.0,
        ...     "max_gap": 0.05,
        ...     "imbalance_ratio": 500.0,
        ...     "markets_to_watch": ["market1", "market2"]
        ... }
        >>> save_depth_config(config)
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    path = Path(config_path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write config to file with pretty formatting
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


@dataclass
class DepthSignal:
    """
    Structured signal for orderbook depth analysis.

    Represents alerts triggered by orderbook depth conditions such as
    thin liquidity, large spreads, or strong imbalances.

    Attributes:
        signal_type: Type of depth signal ("thin_depth", "large_gap", "strong_imbalance")
        triggered: Whether the signal condition has been met
        reason: Human-readable explanation of the signal
        metrics: Dictionary containing relevant metrics that triggered the signal
    """

    signal_type: str
    triggered: bool
    reason: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        return {
            "signal_type": self.signal_type,
            "triggered": self.triggered,
            "reason": self.reason,
            "metrics": self.metrics,
        }


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


def detect_depth_signals(
    metrics: Dict[str, float], config: Optional[Dict[str, Any]] = None
) -> List[DepthSignal]:
    """
    Detect depth-related signals from orderbook metrics.

    Analyzes depth metrics and triggers signals based on conditions:
    - Thin depth: Total depth below threshold indicating low liquidity
    - Large gaps: Wide bid-ask spread indicating poor market efficiency
    - Strong imbalance: Significant difference between YES and NO depth

    Args:
        metrics: Dictionary containing depth metrics from analyze_depth() or
                analyze_normalized_depth() with keys:
                - total_yes_depth: Total YES side liquidity
                - total_no_depth: Total NO side liquidity
                - top_gap_yes: YES bid-ask spread
                - top_gap_no: NO bid-ask spread
                - imbalance: Difference between YES and NO depth
        config: Optional configuration dictionary. If None, loads from default config file.
                Expected keys:
                - min_depth: Minimum total depth threshold
                - max_gap: Maximum acceptable bid-ask spread
                - imbalance_ratio: Maximum acceptable depth imbalance

    Returns:
        List of DepthSignal objects for triggered conditions

    Example:
        >>> metrics = {
        ...     "total_yes_depth": 150.0,
        ...     "total_no_depth": 150.0,
        ...     "top_gap_yes": 0.15,
        ...     "top_gap_no": 0.15,
        ...     "imbalance": 0.0
        ... }
        >>> signals = detect_depth_signals(metrics)
        >>> len(signals)
        2
        >>> signals[0].signal_type
        'thin_depth'
    """
    signals = []

    # Load configuration if not provided
    if config is None:
        config = load_depth_config()

    # Thresholds for signal detection (from config)
    THIN_DEPTH_THRESHOLD = config.get("min_depth", 500.0)
    LARGE_GAP_THRESHOLD = config.get("max_gap", 0.10)
    STRONG_IMBALANCE_THRESHOLD = config.get("imbalance_ratio", 300.0)

    # Extract metrics
    total_yes_depth = metrics.get("total_yes_depth", 0.0)
    total_no_depth = metrics.get("total_no_depth", 0.0)
    top_gap_yes = metrics.get("top_gap_yes", 0.0)
    top_gap_no = metrics.get("top_gap_no", 0.0)
    imbalance = metrics.get("imbalance", 0.0)

    # Calculate total depth across both sides
    total_depth = total_yes_depth + total_no_depth

    # Check for thin depth
    if total_depth < THIN_DEPTH_THRESHOLD:
        signals.append(
            DepthSignal(
                signal_type="thin_depth",
                triggered=True,
                reason=f"Thin orderbook depth: {total_depth:.2f} < {THIN_DEPTH_THRESHOLD:.2f}",
                metrics={
                    "total_depth": total_depth,
                    "threshold": THIN_DEPTH_THRESHOLD,
                    "total_yes_depth": total_yes_depth,
                    "total_no_depth": total_no_depth,
                },
            )
        )

    # Check for large gaps
    max_gap = max(top_gap_yes, top_gap_no)
    if max_gap > LARGE_GAP_THRESHOLD:
        signals.append(
            DepthSignal(
                signal_type="large_gap",
                triggered=True,
                reason=f"Large bid-ask gap: {max_gap:.4f} > {LARGE_GAP_THRESHOLD:.4f}",
                metrics={
                    "max_gap": max_gap,
                    "threshold": LARGE_GAP_THRESHOLD,
                    "top_gap_yes": top_gap_yes,
                    "top_gap_no": top_gap_no,
                },
            )
        )

    # Check for strong imbalance
    abs_imbalance = abs(imbalance)
    if abs_imbalance > STRONG_IMBALANCE_THRESHOLD:
        # Determine which side has more depth
        deeper_side = "YES" if imbalance > 0 else "NO"
        signals.append(
            DepthSignal(
                signal_type="strong_imbalance",
                triggered=True,
                reason=f"Strong depth imbalance: {abs_imbalance:.2f} > {STRONG_IMBALANCE_THRESHOLD:.2f} (favors {deeper_side})",
                metrics={
                    "imbalance": imbalance,
                    "abs_imbalance": abs_imbalance,
                    "threshold": STRONG_IMBALANCE_THRESHOLD,
                    "deeper_side": deeper_side,
                    "total_yes_depth": total_yes_depth,
                    "total_no_depth": total_no_depth,
                },
            )
        )

    return signals
