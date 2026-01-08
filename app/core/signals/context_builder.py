"""
Signal Context Builder for Polymarket Arbitrage Spotter.

Generates structured metadata for detected arbitrage signals to provide
human-readable context and auditability.
"""

from typing import Dict, Any, Optional

def build_signal_metadata(market: Dict[str, Any], opportunity_type: str) -> Dict[str, Any]:
    """
    Build structured metadata for a detected signal.
    
    Args:
        market: Normalized market data dictionary.
        opportunity_type: Type of opportunity (e.g., "two-way").
        
    Returns:
        Dictionary of metadata.
    """
    outcomes = market.get("outcomes", [])
    price_sum = sum(o.get("price", 0.0) for o in outcomes)
    
    # 1. Reason Detected
    reason = f"{opportunity_type.capitalize()} arbitrage detected. "
    if price_sum < 1.0:
        reason += f"Outcome prices sum to {price_sum:.4f}, which is below 1.0."
    else:
        reason += f"Prices sum to {price_sum:.4f}."

    # 2. Market Type
    market_type = "binary" if len(outcomes) == 2 else "multi-outcome"
    
    # 3. Liquidity Notes
    liquidity = market.get("liquidity", 0.0)
    if liquidity == 0:
        liquidity_notes = "Liquidity data N/A"
    elif liquidity < 300:
        liquidity_notes = f"Low liquidity: < $300 (${liquidity:.2f})"
    else:
        liquidity_notes = f"Sufficient liquidity for standard stake (${liquidity:,.2f})"

    # 4. Spread Structure
    if opportunity_type == "two-way":
        spread_structure = "Simple opposing-outcome arbitrage (YES/NO imbalance)"
    else:
        spread_structure = f"Structure: {opportunity_type}"

    return {
        "reason_detected": reason,
        "market_type": market_type,
        "liquidity_notes": liquidity_notes,
        "spread_structure": spread_structure,
        "price_sum": round(price_sum, 4)
    }
