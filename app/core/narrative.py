"""
Centralized narrative hints and guidance copy.
"""

NARRATIVE_HINTS = {
    "volatility_low": "Low volatility — fewer opportunities, but more stable entries.",
    "volatility_med": "Moderate volatility — decent signal flow with manageable swings.",
    "volatility_high": "High volatility — more arbitrage appears, but timing risk increases.",
    "volatility_extreme": "Extreme volatility — many false signals and rapid reversals possible.",
    
    "volume_spike": "When volume spikes, arbitrage signals often follow shortly after.",
    "liquidity_thin": "Markets with thin liquidity may appear profitable but be hard to execute.",
    "liquidity_deep": "Deep liquidity reduces slippage risk for larger entries.",
    
    "empty_history": "Not enough historical data yet to determine reliability trends.",
    "top_signal_intro": "The reliability score below includes both mathematical outcomes and user feedback labels.",
    
    "untradeable_warning": "High ROI in low-liquidity markets is often a 'liquidity trap' where exit is impossible."
}

def get_hint(key: str) -> str:
    """Safely retrieve a narrative hint."""
    return NARRATIVE_HINTS.get(key, "")
