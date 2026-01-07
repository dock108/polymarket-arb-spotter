"""Privacy utilities for masking sensitive identifiers."""

from app.core.config import config


def format_wallet_address(wallet: str) -> str:
    """Return a shortened wallet address for display."""
    if not wallet:
        return "N/A"
    if not config.do_not_expose_full_addresses:
        return wallet
    if "…" in wallet:
        return wallet
    if len(wallet) <= 8:
        return f"{wallet[:2]}…{wallet[-2:]}" if len(wallet) > 4 else "…"
    return f"{wallet[:6]}…{wallet[-4:]}"


def format_wallet_profile_url(wallet: str) -> str:
    """Return a profile URL when allowed; otherwise redact it."""
    if not wallet:
        return "N/A"
    if config.do_not_expose_full_addresses:
        return "Redacted"
    return f"https://polymarket.com/profile/{wallet}"
