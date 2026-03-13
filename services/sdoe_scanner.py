"""
SDOE Scanner Service
====================

Scheduled scanner that runs the Strong Dip Opportunity Engine
against the stock universe and manages results.

Responsibilities:
- Scan stock universe daily for SDOE opportunities
- Cache results for API access
- Integrate with rejection logging
- Support backtest/research queries
"""
import logging
import asyncio
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class SDOEScanResult:
    """Result of a single SDOE scan run"""
    scan_id: str
    scan_date: date
    scan_time: datetime
    total_scanned: int
    strong_buy_count: int
    watchlist_count: int
    monitor_count: int
    rejected_count: int
    duration_seconds: float
    
    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "scan_date": self.scan_date.isoformat(),
            "scan_time": self.scan_time.isoformat(),
            "total_scanned": self.total_scanned,
            "strong_buy_count": self.strong_buy_count,
            "watchlist_count": self.watchlist_count,
            "monitor_count": self.monitor_count,
            "rejected_count": self.rejected_count,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class SDOEScanner:
    """
    SDOE Scanner Service
    
    Manages scanning, caching, and retrieval of SDOE opportunities.
    """
    
    def __init__(self, broker=None, db_session=None):
        """
        Initialize SDOE Scanner
        
        Args:
            broker: Broker instance for data fetching
            db_session: SQLAlchemy session for persistence (optional)
        """
        self.broker = broker
        self.db = db_session
        
        # Import scoring engine
        from strategies.strong_dip import SDOEScoringEngine
        self.scoring_engine = SDOEScoringEngine(broker=broker)
        
        # In-memory cache for current results
        self._cache: Dict[str, Any] = {
            "last_scan": None,
            "strong_buy": [],
            "watchlist": [],
            "monitor": [],
            "rejected": [],
            "by_symbol": {},
        }
        
        self._cache_ttl_minutes = 60
        
        logger.info("[SDOE Scanner] Initialized")
    
    # ══════════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════
    
    async def scan_universe(
        self,
        symbols: List[str] = None,
        force_refresh: bool = False,
    ) -> SDOEScanResult:
        """
        Scan stock universe for SDOE opportunities.
        
        Args:
            symbols: Optional list of symbols to scan (defaults to NIFTY 200)
            force_refresh: Force scan even if cache is fresh
            
        Returns:
            SDOEScanResult with scan statistics
        """
        start_time = datetime.now()
        
        # Check cache
        if not force_refresh and self._is_cache_fresh():
            logger.info("[SDOE Scanner] Using cached results")
            return self._cache.get("last_scan")
        
        # Get symbols to scan
        if symbols is None:
            symbols = await self._get_scan_universe()
        
        logger.info(f"[SDOE Scanner] Starting scan of {len(symbols)} symbols...")
        
        # Run scan
        results = await self.scoring_engine.scan_universe(symbols)
        
        # Update cache
        self._cache["strong_buy"] = [s.to_dict() for s in results["strong_buy"]]
        self._cache["watchlist"] = [s.to_dict() for s in results["watchlist"]]
        self._cache["monitor"] = [s.to_dict() for s in results["monitor"]]
        self._cache["rejected"] = [s.to_dict() for s in results["rejected"]]
        
        # Index by symbol
        self._cache["by_symbol"] = {}
        for category in ["strong_buy", "watchlist", "monitor", "rejected"]:
            for signal in results[category]:
                self._cache["by_symbol"][signal.symbol] = signal.to_dict()
        
        # Create scan result
        duration = (datetime.now() - start_time).total_seconds()
        scan_result = SDOEScanResult(
            scan_id=f"sdoe_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scan_date=date.today(),
            scan_time=datetime.now(timezone.utc),
            total_scanned=len(symbols),
            strong_buy_count=len(results["strong_buy"]),
            watchlist_count=len(results["watchlist"]),
            monitor_count=len(results["monitor"]),
            rejected_count=len(results["rejected"]),
            duration_seconds=duration,
        )
        
        self._cache["last_scan"] = scan_result
        self._cache["cache_time"] = datetime.now()
        
        # Log rejections for audit
        await self._log_rejections(results["rejected"])
        
        logger.info(
            f"[SDOE Scanner] Scan complete in {duration:.1f}s: "
            f"{scan_result.strong_buy_count} strong buy, "
            f"{scan_result.watchlist_count} watchlist, "
            f"{scan_result.monitor_count} monitor, "
            f"{scan_result.rejected_count} rejected"
        )
        
        return scan_result
    
    def get_today_opportunities(self) -> Dict[str, List[dict]]:
        """
        Get today's SDOE opportunities from cache.
        
        Returns:
            Dict with "strong_buy", "watchlist", "monitor" lists
        """
        return {
            "strong_buy": self._cache.get("strong_buy", []),
            "watchlist": self._cache.get("watchlist", []),
            "monitor": self._cache.get("monitor", []),
        }
    
    def get_strong_buy(self) -> List[dict]:
        """Get strong buy candidates"""
        return self._cache.get("strong_buy", [])
    
    def get_watchlist(self) -> List[dict]:
        """Get watchlist candidates"""
        return self._cache.get("watchlist", [])
    
    def get_rejected(self) -> List[dict]:
        """Get rejected candidates with reasons"""
        return self._cache.get("rejected", [])
    
    def get_by_symbol(self, symbol: str) -> Optional[dict]:
        """
        Get detailed analysis for a specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            SDOE signal dict or None
        """
        return self._cache.get("by_symbol", {}).get(symbol)
    
    async def explain_symbol(self, symbol: str) -> dict:
        """
        Get detailed explanation for why a symbol was selected/rejected.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Detailed explanation dict
        """
        # Check cache first
        cached = self.get_by_symbol(symbol)
        if cached:
            return self._build_explanation(cached)
        
        # Run fresh analysis
        signal = await self.scoring_engine.analyze_stock(symbol)
        return self._build_explanation(signal.to_dict())
    
    def get_scan_status(self) -> Dict[str, Any]:
        """Get current scan status and stats"""
        last_scan = self._cache.get("last_scan")
        cache_time = self._cache.get("cache_time")
        
        return {
            "has_data": last_scan is not None,
            "last_scan": last_scan.to_dict() if last_scan else None,
            "cache_age_minutes": (
                (datetime.now() - cache_time).seconds / 60 
                if cache_time else None
            ),
            "is_cache_fresh": self._is_cache_fresh(),
            "counts": {
                "strong_buy": len(self._cache.get("strong_buy", [])),
                "watchlist": len(self._cache.get("watchlist", [])),
                "monitor": len(self._cache.get("monitor", [])),
                "rejected": len(self._cache.get("rejected", [])),
            }
        }
    
    # ══════════════════════════════════════════════════════════════════════════
    #  FILTERING
    # ══════════════════════════════════════════════════════════════════════════
    
    def filter_opportunities(
        self,
        min_score: int = None,
        max_score: int = None,
        sector: str = None,
        holding_horizon: str = None,
        min_decline_pct: float = None,
        max_decline_pct: float = None,
    ) -> List[dict]:
        """
        Filter opportunities with various criteria.
        
        Args:
            min_score: Minimum total score
            max_score: Maximum total score
            sector: Filter by sector
            holding_horizon: Filter by horizon ("5-20 days", "20-45 days", "45-90 days")
            min_decline_pct: Minimum decline percentage
            max_decline_pct: Maximum decline percentage
            
        Returns:
            List of filtered signals
        """
        # Combine all non-rejected signals
        all_signals = (
            self._cache.get("strong_buy", []) +
            self._cache.get("watchlist", []) +
            self._cache.get("monitor", [])
        )
        
        filtered = []
        for signal in all_signals:
            # Score filter
            if min_score and signal.get("total_score", 0) < min_score:
                continue
            if max_score and signal.get("total_score", 0) > max_score:
                continue
            
            # Sector filter
            if sector:
                quality = signal.get("quality_metrics", {})
                if quality.get("sector", "").lower() != sector.lower():
                    continue
            
            # Holding horizon filter
            if holding_horizon:
                if signal.get("holding_horizon") != holding_horizon:
                    continue
            
            # Decline filter
            decline = signal.get("decline_metrics", {})
            decline_pct = decline.get("decline_from_60d_pct", 0)
            
            if min_decline_pct and decline_pct < min_decline_pct:
                continue
            if max_decline_pct and decline_pct > max_decline_pct:
                continue
            
            filtered.append(signal)
        
        # Sort by score descending
        filtered.sort(key=lambda x: x.get("total_score", 0), reverse=True)
        
        return filtered
    
    # ══════════════════════════════════════════════════════════════════════════
    #  INTERNAL METHODS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _is_cache_fresh(self) -> bool:
        """Check if cache is still fresh"""
        cache_time = self._cache.get("cache_time")
        if not cache_time:
            return False
        
        age_minutes = (datetime.now() - cache_time).seconds / 60
        return age_minutes < self._cache_ttl_minutes
    
    async def _get_scan_universe(self) -> List[str]:
        """Get list of symbols to scan (NIFTY 200 + liquid stocks)"""
        
        # Core liquid universe
        universe = [
            # NIFTY 50 Blue Chips
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
            "LT", "AXISBANK", "MARUTI", "TITAN", "ASIANPAINT",
            "SUNPHARMA", "WIPRO", "ULTRACEMCO", "TECHM", "HCLTECH",
            "NESTLEIND", "BAJFINANCE", "M&M", "NTPC", "POWERGRID",
            "TATASTEEL", "TATAMOTORS", "ONGC", "COALINDIA", "GRASIM",
            "ADANIENT", "ADANIPORTS", "JSWSTEEL", "CIPLA", "DRREDDY",
            "DIVISLAB", "BRITANNIA", "BPCL", "BAJAJFINSV", "EICHERMOT",
            "HINDALCO", "INDUSINDBK", "HEROMOTOCO", "APOLLOHOSP", "DMART",
            
            # NIFTY Next 50
            "SIEMENS", "HAVELLS", "GODREJCP", "DABUR", "PIDILITIND",
            "AMBUJACEM", "TATACONSUM", "BERGEPAINT", "DLF", "BAJAJ-AUTO",
            "BANKBARODA", "SBILIFE", "HDFCLIFE", "ICICIPRULI", "VEDL",
            "TRENT", "ZOMATO", "INDIGO", "PFC", "RECLTD",
            "GAIL", "IOC", "JINDALSTEL", "NAUKRI", "PERSISTENT",
            "PIIND", "MUTHOOTFIN", "CHOLAFIN", "IDFCFIRSTB", "MARICO",
            
            # Quality Mid Caps
            "COFORGE", "LTIM", "VOLTAS", "CUMMINSIND", "AUROPHARMA",
            "TORNTPHARM", "PAGEIND", "FLUOROCHEM", "ASTRAL", "POLYCAB",
            "AADHAARRES", "ABCAPITAL", "ALKEM", "APOLLOTYRE", "ASHOKLEY",
            "ASTRAZEN", "AUBANK", "BANDHANBNK", "BEL", "CANFINHOME",
        ]
        
        # Try to get more via broker if available
        if self.broker:
            try:
                # Get top movers as additional candidates
                movers = await self.broker.get_top_movers(limit=50)
                if movers:
                    for m in movers:
                        symbol = m.get('symbol', '')
                        if symbol and symbol not in universe:
                            universe.append(symbol)
            except Exception as e:
                logger.debug(f"[SDOE Scanner] Could not fetch movers: {e}")
        
        return universe
    
    async def _log_rejections(self, rejected_signals: List) -> None:
        """Log rejected signals to audit system"""
        
        if not self.db:
            return
        
        if not getattr(settings, "rejected_trades_audit_enabled", True):
            return
        
        try:
            from rejected_trades import RejectedTradesService, RejectionReason
            
            svc = RejectedTradesService(self.db)
            user_id = getattr(settings, "trading_account_user_id", None) or "system"
            
            for signal in rejected_signals:
                signal_dict = signal.to_dict() if hasattr(signal, 'to_dict') else signal
                
                # Convert SDOE rejection reasons to standard format
                reasons = []
                for r in signal_dict.get("rejection_reasons", []):
                    reasons.append(RejectionReason(
                        code=r.get("code", "SDOE_REJECT"),
                        message=r.get("message", "SDOE rejection"),
                        rule_name=r.get("rule_name", "sdoe"),
                        rule_value=r.get("rule_value", ""),
                    ))
                
                if not reasons:
                    reasons.append(RejectionReason(
                        code="SDOE_LOW_SCORE",
                        message=f"Score {signal_dict.get('total_score', 0)} below threshold",
                        rule_name="sdoe_scanner",
                        rule_value=f"score={signal_dict.get('total_score', 0)}",
                    ))
                
                svc.log_rejection(
                    user_id=user_id,
                    symbol=signal_dict.get("symbol", ""),
                    strategy_name="SDOE",
                    side="BUY",
                    order_type="CNC",
                    reasons=reasons,
                    entry_price=signal_dict.get("trade_params", {}).get("entry_zone", [0, 0])[1],
                    stop_loss=signal_dict.get("trade_params", {}).get("stop_loss", 0),
                    target=signal_dict.get("trade_params", {}).get("target_1", 0),
                    quantity=0,
                )
                
        except Exception as e:
            logger.warning(f"[SDOE Scanner] Failed to log rejections: {e}")
    
    def _build_explanation(self, signal_dict: dict) -> dict:
        """Build detailed explanation from signal dict"""
        
        explanation = {
            "symbol": signal_dict.get("symbol"),
            "category": signal_dict.get("category"),
            "total_score": signal_dict.get("total_score"),
            "verdict": "",
            "score_explanation": {},
            "key_factors": [],
            "risks": signal_dict.get("risk_factors", []),
        }
        
        # Build verdict
        category = signal_dict.get("category")
        score = signal_dict.get("total_score", 0)
        
        if category == "Strong Buy":
            explanation["verdict"] = (
                f"Strong buy candidate with score {score}/100. "
                "Stock shows good decline attractiveness, quality metrics, "
                "stabilization evidence, and recovery potential."
            )
        elif category == "Watchlist":
            explanation["verdict"] = (
                f"Watchlist candidate with score {score}/100. "
                "Stock has potential but needs more confirmation before entry."
            )
        elif category == "Monitor":
            explanation["verdict"] = (
                f"Monitor only with score {score}/100. "
                "Stock shows some potential but insufficient signals for action."
            )
        else:
            explanation["verdict"] = (
                f"Not recommended with score {score}/100. "
                "Stock fails one or more key criteria."
            )
        
        # Score breakdown explanation
        breakdown = signal_dict.get("score_breakdown", {})
        explanation["score_explanation"] = {
            "decline": {
                "score": breakdown.get("decline", 0),
                "max": 20,
                "description": "How attractive is the decline? (Sweet spot: 8-15% from 60d high)"
            },
            "quality": {
                "score": breakdown.get("quality", 0),
                "max": 25,
                "description": "Stock quality: market cap, liquidity, ROE, debt levels"
            },
            "stabilization": {
                "score": breakdown.get("stabilization", 0),
                "max": 20,
                "description": "Is the stock stabilizing? (RSI recovery, base forming, no new lows)"
            },
            "recovery": {
                "score": breakdown.get("recovery", 0),
                "max": 15,
                "description": "Early recovery signals (above prev high, volume, SMA reclaim)"
            },
            "market": {
                "score": breakdown.get("market", 0),
                "max": 10,
                "description": "Market and sector context alignment"
            },
            "upside_bonus": {
                "score": breakdown.get("upside_bonus", 0),
                "max": 10,
                "description": "Upside potential, dividend, sector leadership bonus"
            },
        }
        
        # Key factors
        explanation["key_factors"] = signal_dict.get("selection_reasons", [])
        if not explanation["key_factors"]:
            explanation["key_factors"] = [
                r.get("message", "") for r in signal_dict.get("rejection_reasons", [])
            ]
        
        return explanation


# ══════════════════════════════════════════════════════════════════════════════
#  SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_scanner_instance: Optional[SDOEScanner] = None


def get_sdoe_scanner(broker=None, db_session=None) -> SDOEScanner:
    """Get or create SDOE Scanner singleton"""
    global _scanner_instance
    
    if _scanner_instance is None:
        _scanner_instance = SDOEScanner(broker=broker, db_session=db_session)
    
    return _scanner_instance
