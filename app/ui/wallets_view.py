"""
Wallet intelligence dashboard view.

Provides a Bloomberg-style overview of wallet behavior:
- Top wallet leaderboard
- Recent wallet alerts
- Drill-down into trades, ROI history, and markets traded
- Filters for whales, fresh wallets, and suspected insiders
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from app.core.config import config
from app.core.privacy import format_wallet_address

def _format_currency(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.2f}K"
    return f"${value:,.2f}"


def _format_flags(row: pd.Series) -> str:
    flags = []
    if row.get("whale"):
        flags.append("🐋 Whale")
    if row.get("fresh"):
        flags.append("🧪 Fresh")
    if row.get("insider"):
        flags.append("🕵️ Insider?")
    return ", ".join(flags) if flags else "—"


def _wallet_leaderboard() -> pd.DataFrame:
    data = [
        {
            "wallet": "0x9a3f…b21e",
            "alias": "Atlas Fund",
            "volume_24h": 12_800_000,
            "pnl_24h": 1_350_000,
            "roi_30d": 10.8,
            "win_rate": 62,
            "trades_24h": 312,
            "last_active": "2m",
            "whale": True,
            "fresh": False,
            "insider": True,
        },
        {
            "wallet": "0x1f2c…aa91",
            "alias": "Quanta Capital",
            "volume_24h": 9_420_000,
            "pnl_24h": 890_000,
            "roi_30d": 7.4,
            "win_rate": 58,
            "trades_24h": 276,
            "last_active": "5m",
            "whale": True,
            "fresh": False,
            "insider": False,
        },
        {
            "wallet": "0xb7d0…c4de",
            "alias": "FreshMint 03",
            "volume_24h": 1_250_000,
            "pnl_24h": 210_000,
            "roi_30d": 16.1,
            "win_rate": 71,
            "trades_24h": 54,
            "last_active": "1m",
            "whale": False,
            "fresh": True,
            "insider": False,
        },
        {
            "wallet": "0xa88e…1c02",
            "alias": "Oracle Ridge",
            "volume_24h": 5_670_000,
            "pnl_24h": 420_000,
            "roi_30d": 9.2,
            "win_rate": 64,
            "trades_24h": 191,
            "last_active": "12m",
            "whale": True,
            "fresh": False,
            "insider": True,
        },
        {
            "wallet": "0x3c51…02bf",
            "alias": "Signal Drift",
            "volume_24h": 2_980_000,
            "pnl_24h": 135_000,
            "roi_30d": 4.8,
            "win_rate": 55,
            "trades_24h": 88,
            "last_active": "18m",
            "whale": False,
            "fresh": False,
            "insider": False,
        },
        {
            "wallet": "0x54b3…9f91",
            "alias": "New Dawn",
            "volume_24h": 980_000,
            "pnl_24h": 75_000,
            "roi_30d": 12.6,
            "win_rate": 68,
            "trades_24h": 32,
            "last_active": "33m",
            "whale": False,
            "fresh": True,
            "insider": True,
        },
    ]
    return pd.DataFrame(data)


def _recent_alerts() -> pd.DataFrame:
    data = [
        {
            "time": "09:44",
            "wallet": "Atlas Fund",
            "alert": "Aggressive YES sweep in BTC CPI",
            "confidence": "High",
            "action": "Front-run momentum",
        },
        {
            "time": "09:39",
            "wallet": "Oracle Ridge",
            "alert": "Insider cluster on Fed Pause",
            "confidence": "Medium",
            "action": "Watch liquidity",
        },
        {
            "time": "09:32",
            "wallet": "FreshMint 03",
            "alert": "Fresh wallet sniping low-liquidity",
            "confidence": "High",
            "action": "Mirror small clips",
        },
        {
            "time": "09:25",
            "wallet": "Quanta Capital",
            "alert": "Cross-market hedge detected",
            "confidence": "Medium",
            "action": "Check paired markets",
        },
        {
            "time": "09:12",
            "wallet": "New Dawn",
            "alert": "Whale follow-on buys",
            "confidence": "Low",
            "action": "Monitor depth",
        },
    ]
    return pd.DataFrame(data)


def _wallet_trades(wallet_alias: str) -> pd.DataFrame:
    data = {
        "Atlas Fund": [
            ("09:42", "BTC CPI > 3.0%", "YES", 0.62, 420_000, "Aggressive"),
            ("09:31", "ETH ETF Approval", "NO", 0.44, 180_000, "Hedge"),
            ("09:22", "US Recession 2024", "NO", 0.37, 260_000, "Liquidity"),
            ("09:15", "Fed Cuts by Sep", "YES", 0.58, 330_000, "Momentum"),
        ],
        "Quanta Capital": [
            ("09:41", "ECB Hike", "NO", 0.53, 210_000, "Swing"),
            ("09:29", "Oil > $100", "YES", 0.47, 350_000, "Hedge"),
            ("09:18", "AI Regulation Passed", "NO", 0.39, 190_000, "Range"),
        ],
        "FreshMint 03": [
            ("09:43", "GME Squeeze 2.0", "YES", 0.21, 45_000, "Snipe"),
            ("09:34", "US Govt Shutdown", "NO", 0.33, 62_000, "Arb"),
        ],
        "Oracle Ridge": [
            ("09:40", "Fed Pause", "YES", 0.59, 280_000, "Signal"),
            ("09:26", "GDP > 2.5%", "YES", 0.48, 190_000, "Macro"),
            ("09:11", "Inflation < 2%", "NO", 0.36, 210_000, "Hedge"),
        ],
        "Signal Drift": [
            ("09:36", "NBA Finals Game 7", "YES", 0.55, 95_000, "Sports"),
            ("09:20", "SpaceX Launch", "YES", 0.62, 80_000, "Event"),
        ],
        "New Dawn": [
            ("09:30", "Bitcoin > 80K", "YES", 0.29, 70_000, "Fresh"),
            ("09:17", "Apple AR Glasses", "NO", 0.41, 52_000, "Trend"),
        ],
    }
    rows = data.get(wallet_alias, [])
    return pd.DataFrame(
        rows,
        columns=["Time", "Market", "Side", "Price", "Notional", "Strategy Tag"],
    )


def _wallet_roi_history(wallet_alias: str) -> pd.DataFrame:
    base_date = datetime.utcnow().date()
    dates = [base_date - timedelta(days=day) for day in range(6, -1, -1)]
    patterns = {
        "Atlas Fund": [4.2, 5.1, 6.8, 7.9, 8.7, 9.4, 10.8],
        "Quanta Capital": [2.1, 3.4, 4.2, 5.3, 6.1, 6.8, 7.4],
        "FreshMint 03": [1.8, 3.6, 5.2, 8.0, 10.9, 13.6, 16.1],
        "Oracle Ridge": [3.3, 4.4, 5.6, 6.9, 7.8, 8.6, 9.2],
        "Signal Drift": [0.9, 1.6, 2.3, 3.1, 3.7, 4.2, 4.8],
        "New Dawn": [1.4, 2.8, 4.1, 6.0, 8.3, 10.4, 12.6],
    }
    roi = patterns.get(wallet_alias, [0.0] * 7)
    return pd.DataFrame({"Date": dates, "ROI (%)": roi})


def _wallet_markets(wallet_alias: str) -> pd.DataFrame:
    markets = {
        "Atlas Fund": [
            ("BTC CPI > 3.0%", 3_200_000, 420_000, 66),
            ("Fed Cuts by Sep", 2_100_000, 270_000, 61),
            ("US Recession 2024", 1_800_000, 190_000, 58),
        ],
        "Quanta Capital": [
            ("Oil > $100", 2_600_000, 210_000, 57),
            ("ECB Hike", 1_900_000, 180_000, 60),
            ("AI Regulation Passed", 1_200_000, 140_000, 54),
        ],
        "FreshMint 03": [
            ("GME Squeeze 2.0", 540_000, 110_000, 74),
            ("US Govt Shutdown", 420_000, 70_000, 69),
        ],
        "Oracle Ridge": [
            ("Fed Pause", 1_980_000, 210_000, 63),
            ("GDP > 2.5%", 1_340_000, 140_000, 61),
            ("Inflation < 2%", 980_000, 70_000, 55),
        ],
        "Signal Drift": [
            ("NBA Finals Game 7", 760_000, 65_000, 56),
            ("SpaceX Launch", 640_000, 52_000, 53),
        ],
        "New Dawn": [
            ("Bitcoin > 80K", 520_000, 80_000, 67),
            ("Apple AR Glasses", 460_000, 55_000, 62),
        ],
    }
    rows = markets.get(wallet_alias, [])
    return pd.DataFrame(
        rows, columns=["Market", "Volume", "PnL", "Win Rate (%)"]
    )


def render_wallets_view() -> None:
    """
    Render the wallet intelligence dashboard page.
    """
    st.title("🧠 Wallet Intelligence")
    st.caption(
        "Bloomberg-style situational awareness for high-signal wallets and flow."
    )
    st.caption("We analyze behavior — we don’t dox people.")
    if not config.wallet_features_enabled:
        st.warning(
            "Wallet intelligence is disabled. Set WALLET_FEATURES_ENABLED=true to enable."
        )
        return
    st.markdown("---")

    wallets = _wallet_leaderboard()

    st.subheader("🔎 Filters")
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        whales_only = st.checkbox("🐋 Whales only", value=False)
    with filter_col2:
        fresh_only = st.checkbox("🧪 Fresh only", value=False)
    with filter_col3:
        insiders_only = st.checkbox("🕵️ Insiders suspected", value=False)

    filtered = wallets.copy()
    if whales_only:
        filtered = filtered[filtered["whale"]]
    if fresh_only:
        filtered = filtered[filtered["fresh"]]
    if insiders_only:
        filtered = filtered[filtered["insider"]]

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.metric("Wallets Tracked", len(wallets))
    with metric_col2:
        st.metric(
            "24h Volume",
            _format_currency(wallets["volume_24h"].sum()),
        )
    with metric_col3:
        st.metric(
            "24h PnL",
            _format_currency(wallets["pnl_24h"].sum()),
        )
    with metric_col4:
        st.metric(
            "Fresh Wallets",
            int(wallets["fresh"].sum()),
        )

    st.markdown("---")

    st.subheader("🏆 Top Wallet Leaderboard")
    if filtered.empty:
        st.info("No wallets match the current filters.")
    else:
        leaderboard = filtered.copy()
        leaderboard["Rank"] = (
            leaderboard["pnl_24h"].rank(ascending=False).astype(int)
        )
        leaderboard["Flags"] = leaderboard.apply(_format_flags, axis=1)
        leaderboard = leaderboard.sort_values("Rank")

        display = leaderboard[
            [
                "Rank",
                "alias",
                "wallet",
                "volume_24h",
                "pnl_24h",
                "roi_30d",
                "win_rate",
                "trades_24h",
                "last_active",
                "Flags",
            ]
        ].copy()
        display.columns = [
            "#",
            "Alias",
            "Wallet",
            "24h Volume",
            "24h PnL",
            "30d ROI (%)",
            "Win Rate (%)",
            "Trades",
            "Last Active",
            "Signals",
        ]
        display["24h Volume"] = display["24h Volume"].apply(_format_currency)
        display["24h PnL"] = display["24h PnL"].apply(_format_currency)
        display["30d ROI (%)"] = display["30d ROI (%)"].apply(lambda x: f"{x:.1f}")
        display["Win Rate (%)"] = display["Win Rate (%)"].apply(lambda x: f"{x:.0f}")
        display["Wallet"] = display["Wallet"].apply(format_wallet_address)
        st.dataframe(display, use_container_width=True)

    st.markdown("---")

    st.subheader("🚨 Recent Wallet Alerts")
    alerts = _recent_alerts()
    st.dataframe(alerts, use_container_width=True, hide_index=True)

    st.markdown("---")

    st.subheader("🧩 Wallet Drill-Down")
    if filtered.empty:
        st.info("Select a wallet once filters return results.")
        return

    wallet_options = filtered["alias"].tolist()
    selected_alias = st.selectbox(
        "Select wallet",
        wallet_options,
        index=0,
        help="Choose a wallet to inspect trades and ROI history.",
    )

    trades_tab, roi_tab, markets_tab = st.tabs(
        ["📈 Trades", "📊 ROI History", "🧭 Markets Traded"]
    )

    with trades_tab:
        trades = _wallet_trades(selected_alias)
        trades_display = trades.copy()
        if not trades_display.empty:
            trades_display["Price"] = trades_display["Price"].apply(lambda x: f"{x:.2f}")
            trades_display["Notional"] = trades_display["Notional"].apply(
                _format_currency
            )
        st.dataframe(trades_display, use_container_width=True, hide_index=True)

    with roi_tab:
        roi_history = _wallet_roi_history(selected_alias)
        st.line_chart(roi_history, x="Date", y="ROI (%)")

    with markets_tab:
        markets = _wallet_markets(selected_alias)
        markets_display = markets.copy()
        if not markets_display.empty:
            markets_display["Volume"] = markets_display["Volume"].apply(_format_currency)
            markets_display["PnL"] = markets_display["PnL"].apply(_format_currency)
        st.dataframe(markets_display, use_container_width=True, hide_index=True)
