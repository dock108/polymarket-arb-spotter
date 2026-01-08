"""
Backtest engine for testing strategies against historical data.
Pipes replay events through various detection strategies.
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from app.core.logger import logger, init_db, log_wallet_alert
from app.core.history_store import append_backtest_result
from app.core.wallet_feed import get_wallet_trades_in_range
from app.core.wallet_signals import WalletSignalConfig, detect_wallet_signals
from app.core.wallet_performance import evaluate_resolved_market, load_market_outcomes
from app.core.privacy import format_wallet_profile_url

try:
    from app.core.depth_scanner import analyze_depth, detect_depth_signals
except ImportError:
    analyze_depth = None
    detect_depth_signals = None

class BacktestEngine:
    """
    Backtest engine that pipes replay events through various detection strategies.
    """

    def __init__(
        self,
        replay_engine: Any,
        alerts_db_path: str = "data/backtest_alerts.sqlite",
        wallet_db_path: str = "data/polymarket_wallets.db",
    ):
        """
        Initialize the backtest engine.

        Args:
            replay_engine: HistoricalReplayEngine instance
            alerts_db_path: Path to store generated backtest alerts
            wallet_db_path: Path to the wallet trades database
        """
        self.replay_engine = replay_engine
        self.alerts_db_path = alerts_db_path
        self.wallet_db_path = wallet_db_path

        # Strategies
        self.arb_detector = None
        self.price_alerts = []
        self.depth_config = None
        self.wallet_replay_enabled = False
        self.wallet_signal_config = None
        self.wallet_market_metadata = {}

        # Stats tracking
        self.stats = {
            "ticks_processed": 0,
            "opportunities_detected": 0,
            "alerts_triggered": 0,
            "depth_signals_detected": 0,
            "wallet_trades_processed": 0,
            "wallet_signals_detected": 0,
            "wallet_alerts_logged": 0,
            "wallet_evaluations": 0,
            "successful_wallet_signals": 0,
        }

    def set_arb_detector(self, detector: Any) -> None:
        """Set arbitrage detector for backtesting."""
        self.arb_detector = detector
        logger.info("Arbitrage detector configured for backtest")

    def add_price_alert(self, market_id: str, direction: str, target_price: float) -> None:
        """Add a price alert to backtest."""
        self.price_alerts.append({
            "market_id": market_id,
            "direction": direction,
            "target_price": target_price,
            "triggered": False,
        })
        logger.info(f"Added price alert: {market_id} {direction} {target_price}")

    def set_depth_config(self, config: Dict[str, Any]) -> None:
        """Set depth scanner configuration for backtesting."""
        self.depth_config = config
        logger.info("Depth scanner configured for backtest")

    def enable_wallet_replay(self, config: Optional[WalletSignalConfig] = None, 
                             market_metadata_by_id: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """Enable wallet activity replay during backtests."""
        self.wallet_signal_config = config or WalletSignalConfig()
        self.wallet_market_metadata = market_metadata_by_id or {}
        self.wallet_replay_enabled = True
        logger.info("Wallet replay enabled for backtest")

    def disable_wallet_replay(self) -> None:
        """Disable wallet activity replay."""
        self.wallet_replay_enabled = False
        logger.info("Wallet replay disabled for backtest")

    def run(self, market_id: Optional[str] = None, start: Optional[Union[datetime, str]] = None, 
            end: Optional[Union[datetime, str]] = None) -> Dict[str, Any]:
        """Run the backtest."""
        logger.info(f"Starting backtest for market={market_id}")
        self.replay_engine.register_callback(self._process_tick)
        self.replay_engine.run(market_id=market_id, start=start, end=end)
        
        if self.wallet_replay_enabled and market_id:
            self._simulate_wallet_activity(market_id, start, end)
            
        return self.stats

    def _process_tick(self, tick: Dict[str, Any]) -> None:
        """Process a single tick during backtest."""
        self.stats["ticks_processed"] += 1
        m_id = tick["market_id"]
        
        # Arb detection
        if self.arb_detector:
            opps = self.arb_detector.detect_opportunities([tick])
            for opp in opps:
                self.stats["opportunities_detected"] += 1
                append_backtest_result("arb_detector", m_id, tick["timestamp"], opp.to_dict(), "would_trigger")

        # Price alerts
        for alert in self.price_alerts:
            if alert["market_id"] == m_id and not alert["triggered"]:
                triggered = False
                if alert["direction"] == "above" and tick["yes_price"] >= alert["target_price"]:
                    triggered = True
                elif alert["direction"] == "below" and tick["yes_price"] <= alert["target_price"]:
                    triggered = True
                
                if triggered:
                    alert["triggered"] = True
                    self.stats["alerts_triggered"] += 1
                    append_backtest_result("price_alert", m_id, tick["timestamp"], alert, "triggered")

        # Depth scanner
        if self.depth_config and analyze_depth and tick.get("depth_summary"):
            signals = detect_depth_signals(tick["depth_summary"], self.depth_config)
            for sig in signals:
                self.stats["depth_signals_detected"] += 1
                append_backtest_result("depth_scanner", m_id, tick["timestamp"], sig.to_dict(), "triggered")

    def _simulate_wallet_activity(self, market_id: str, start: Optional[Union[datetime, str]] = None, 
                                  end: Optional[Union[datetime, str]] = None) -> None:
        """Simulate wallet activity and generate wallet alerts."""
        trades = get_wallet_trades_in_range(market_id=market_id, start=start, end=end, db_path=self.wallet_db_path)
        if not trades: return

        self.stats["wallet_trades_processed"] += len(trades)
        signals = detect_wallet_signals(trades, db_path=self.wallet_db_path, config=self.wallet_signal_config, 
                                        market_metadata_by_id=self.wallet_market_metadata)
        if not signals: return

        init_db(self.alerts_db_path)
        for signal in signals:
            self.stats["wallet_signals_detected"] += 1
            log_wallet_alert(self._build_wallet_alert_payload(signal), db_path=self.alerts_db_path)
            self.stats["wallet_alerts_logged"] += 1

        self._evaluate_wallet_signals(market_id)

    def _evaluate_wallet_signals(self, market_id: str) -> None:
        """Evaluate accuracy of replayed wallet signals."""
        outcomes = load_market_outcomes(db_path=self.wallet_db_path)
        if market_id not in outcomes: return
        
        from app.core.event_log import _get_db
        db = _get_db(self.alerts_db_path)
        alerts = db["wallet_alerts"].rows_where("market_id = ?", [market_id])
        
        for alert in alerts:
            self.stats["wallet_evaluations"] += 1
            success = evaluate_resolved_market(alert["wallet"], market_id, outcomes[market_id], db_path=self.wallet_db_path)
            if success: self.stats["successful_wallet_signals"] += 1

    def _build_wallet_alert_payload(self, signal: Any) -> Dict[str, Any]:
        """Build payload for wallet alert logging."""
        return {
            "timestamp": signal.timestamp.isoformat(),
            "wallet": signal.wallet,
            "market_id": signal.market_id,
            "bet_size": signal.bet_size,
            "classification": signal.classification,
            "signal_type": signal.signal_type,
            "profile_url": format_wallet_profile_url(signal.wallet),
            "evidence": signal.evidence
        }
