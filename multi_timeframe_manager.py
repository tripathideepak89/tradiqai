"""Multi-Timeframe Trading Manager
===================================

Orchestrates all 4 trading styles with proper capital allocation:
- Intraday (20%)
- Swing (30%)
- Mid-term (30%)
- Long-term (20%)

Manages:
- Capital allocation across styles
- Market regime detection
- Signal generation for all styles
- Position management
- Performance tracking
- Monthly rebalancing
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from trading_styles import TradingStyle, TradingStylesConfig, StylePerformanceTracker
from capital_allocator import CapitalAllocator
from regime_detector import RegimeDetector, RegimeBasedRiskAdjuster
from strategies.strategy_intraday import IntradayStrategy
from strategies.strategy_swing import SwingStrategy
from strategies.strategy_midterm import MidTermStrategy
from strategies.strategy_longterm import LongTermStrategy
from strategies.base import Signal
from brokers.base import BaseBroker
from models import Trade, TradeStatus

logger = logging.getLogger(__name__)


class MultiTimeframeManager:
    """Manager for multi-timeframe trading system"""
    
    def __init__(
        self, 
        db_session: Session, 
        broker: BaseBroker, 
        total_capital: float
    ):
        self.db = db_session
        self.broker = broker
        
        # Initialize components
        self.capital_allocator = CapitalAllocator(db_session, total_capital)
        self.regime_detector = RegimeDetector(broker)
        self.risk_adjuster = RegimeBasedRiskAdjuster()
        
        # Initialize strategies
        self.strategies = {
            TradingStyle.INTRADAY: IntradayStrategy(broker, self.regime_detector),
            TradingStyle.SWING: SwingStrategy(broker, self.regime_detector),
            TradingStyle.MIDTERM: MidTermStrategy(broker, self.regime_detector),
            TradingStyle.LONGTERM: LongTermStrategy(broker, self.regime_detector)
        }
        
        # Tracking
        self.active_styles = {style: True for style in TradingStyle}
        self.last_regime_check = None
        self.current_regimes: Dict[str, object] = {}
        
        logger.info("Multi-timeframe manager initialized")
        logger.info(self.capital_allocator.get_allocation_summary())
    
    async def update_regimes(self):
        """Update market regimes for all timeframes"""
        try:
            regimes = await self.regime_detector.get_multi_timeframe_regime("NIFTY50")
            self.current_regimes = regimes
            self.regime_detector.print_regime_summary(regimes)
            self.last_regime_check = datetime.now()
        except Exception as e:
            logger.error(f"Failed to update regimes: {e}")
    
    async def scan_for_signals(self, watchlist: List[str]) -> Dict[TradingStyle, List[Signal]]:
        """Scan watchlist for signals across all active styles
        
        Args:
            watchlist: List of symbols to scan
            
        Returns:
            Dict mapping style to list of signals
        """
        signals_by_style: Dict[TradingStyle, List[Signal]] = {
            style: [] for style in TradingStyle
        }
        
        # Update regimes if needed
        if not self.current_regimes:
            await self.update_regimes()
        
        # Monthly rebalancing check
        self.capital_allocator.check_and_rebalance()
        
        for symbol in watchlist:
            try:
                # Get market data for all timeframes
                market_data = await self._fetch_market_data(symbol)
                
                # Generate signals for each active style
                for style, strategy in self.strategies.items():
                    # Check if style is active
                    if not self.active_styles[style]:
                        continue
                    
                    # Check if style is blocked
                    is_blocked, block_reason = self.capital_allocator.is_style_blocked(style)
                    if is_blocked:
                        logger.warning(f"[{style.value.upper()}] Blocked: {block_reason}")
                        continue
                    
                    # Check regime compatibility
                    regime_timeframe = self._get_regime_timeframe_for_style(style)
                    regime = self.current_regimes.get(regime_timeframe)
                    
                    if regime:
                        # Check if new trades allowed
                        if not self.risk_adjuster.should_enter_new_trades(regime, style.value):
                            logger.debug(f"[{style.value.upper()}] Regime prevents new trades")
                            continue
                    
                    # Generate signal
                    try:
                        signal = await strategy.generate_signal(symbol, market_data)
                        if signal:
                            # Apply regime-based position sizing
                            if regime:
                                size_multiplier = self.risk_adjuster.get_position_size_multiplier(regime)
                                signal.metadata['regime_size_multiplier'] = size_multiplier
                            
                            signals_by_style[style].append(signal)
                            logger.info(f"[{style.value.upper()}] Signal generated for {symbol}")
                    except Exception as e:
                        logger.error(f"[{style.value.upper()}] Error generating signal for {symbol}: {e}")
                
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        # Log summary
        total_signals = sum(len(signals) for signals in signals_by_style.values())
        if total_signals > 0:
            logger.info(f"\n{'='*80}")
            logger.info(f"SCAN SUMMARY: {total_signals} signals found")
            for style, signals in signals_by_style.items():
                if signals:
                    logger.info(f"  [{style.value.upper()}]: {len(signals)} signals")
            logger.info("="*80)
        
        return signals_by_style
    
    def validate_and_size_signal(self, signal: Signal, style: TradingStyle) -> Optional[Signal]:
        """Validate signal and calculate position size
        
        Returns:
            Signal with quantity set, or None if validation fails
        """
        # Get available capital for this style
        available_capital = self.capital_allocator.get_available_capital(style)
        
        # Calculate position size based on risk rules
        quantity = TradingStylesConfig.calculate_position_size(
            style=style,
            allocated_capital=available_capital,
            entry_price=signal.entry_price,
            stop_loss_price=signal.stop_loss
        )
        
        if quantity == 0:
            logger.warning(f"[{style.value.upper()}] Position size calculated as 0 for {signal.symbol}")
            return None
        
        # Apply regime-based scaling
        regime_multiplier = signal.metadata.get('regime_size_multiplier', 1.0)
        quantity = int(quantity * regime_multiplier)
        
        if quantity == 0:
            logger.warning(f"[{style.value.upper()}] Position size reduced to 0 after regime scaling")
            return None
        
        # Calculate required capital
        required_capital = signal.entry_price * quantity
        
        # Reserve capital
        if not self.capital_allocator.reserve_capital(style, required_capital):
            logger.warning(f"[{style.value.upper()}] Failed to reserve capital for {signal.symbol}")
            return None
        
        # Set quantity in signal
        signal.quantity = quantity
        signal.metadata['style'] = style.value
        signal.metadata['allocated_capital'] = required_capital
        
        logger.info(f"[{style.value.upper()}] {signal.symbol}: {quantity} shares @ Rs{signal.entry_price:.2f} "
                   f"= Rs{required_capital:.2f} (Risk: Rs{abs(signal.entry_price - signal.stop_loss) * quantity:.2f})")
        
        return signal
    
    async def check_exits(self) -> List[Trade]:
        """Check all open positions for exit signals
        
        Returns:
            List of trades that should be exited
        """
        exits = []
        
        # Get all open trades grouped by style
        open_trades = self.db.query(Trade).filter(
            Trade.status == TradeStatus.OPEN
        ).all()
        
        for trade in open_trades:
            try:
                # Determine style
                style = self._get_style_from_trade(trade)
                if not style:
                    continue
                
                # Get strategy
                strategy = self.strategies.get(style)
                if not strategy:
                    continue
                
                # Get current quote
                quote = await self.broker.get_quote(trade.symbol)
                current_price = quote.get('ltp', 0)
                
                if current_price == 0:
                    continue
                
                # Get market data
                market_data = await self._fetch_market_data(trade.symbol)
                
                # Check if should exit
                position_dict = self._trade_to_position_dict(trade)
                should_exit, reason = await strategy.should_exit(
                    position_dict,
                    current_price,
                    datetime.now(),
                    market_data
                )
                
                if should_exit:
                    logger.info(f"[{style.value.upper()}] Exit signal for {trade.symbol}: {reason}")
                    trade.exit_reason = reason
                    exits.append(trade)
                
            except Exception as e:
                logger.error(f"Error checking exit for {trade.symbol}: {e}")
        
        return exits
    
    def record_trade_closed(self, trade: Trade):
        """Record that a trade has closed"""
        style = self._get_style_from_trade(trade)
        if style:
            self.capital_allocator.record_trade_result(style, trade)
    
    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary"""
        summary = {
            "capital_allocation": self.capital_allocator.get_allocation_summary(),
            "portfolio_stats": self.capital_allocator.get_portfolio_stats(),
            "active_styles": {
                style.value: active for style, active in self.active_styles.items()
            },
            "current_regimes": {
                tf: {
                    "type": regime.regime_type,
                    "confidence": regime.confidence
                }
                for tf, regime in self.current_regimes.items()
            }
        }
        
        return summary
    
    def print_portfolio_summary(self):
        """Print portfolio summary"""
        summary = self.get_portfolio_summary()
        
        logger.info("\n" + "="*80)
        logger.info("MULTI-TIMEFRAME PORTFOLIO SUMMARY")
        logger.info("="*80)
        
        stats = summary['portfolio_stats']
        logger.info(f"\nTotal Capital: Rs{stats['total_capital']:,.2f}")
        logger.info(f"Total P&L: Rs{stats['total_pnl']:,.2f}")
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Expected Annual Return: {stats['expected_annual_return']:.1f}%")
        logger.info(f"3-Year Projection: Rs{stats['3_year_projection']:,.2f}")
        
        logger.info(f"\n{summary['capital_allocation']}")
        
        logger.info("\nACTIVE STYLES:")
        for style_name, active in summary['active_styles'].items():
            status = "ACTIVE" if active else "DISABLED"
            logger.info(f"  {style_name.upper()}: {status}")
        
        logger.info("="*80)
    
    async def _fetch_market_data(self, symbol: str) -> Dict:
        """Fetch market data for all timeframes needed
        
        Returns:
            Dict with candles, quotes, fundamentals (if available)
        """
        market_data = {}
        
        try:
            # Get quote
            market_data['quote'] = await self.broker.get_quote(symbol)
            
            # Get intraday candles (for intraday strategy)
            try:
                candles_5min = await self.broker.get_historical_data(
                    symbol, 
                    datetime.now() - timedelta(days=5),
                    datetime.now(),
                    "5minute"
                )
                market_data['candles'] = candles_5min
            except:
                pass
            
            # Get daily candles (for swing, mid-term, long-term)
            try:
                daily_candles = await self.broker.get_historical_data(
                    symbol,
                    datetime.now() - timedelta(days=250),
                    datetime.now(),
                    "day"
                )
                market_data['daily_candles'] = daily_candles
            except:
                pass
            
            # Get weekly candles (for mid-term, long-term)
            try:
                weekly_candles = await self.broker.get_historical_data(
                    symbol,
                    datetime.now() - timedelta(days=730),
                    datetime.now(),
                    "week"
                )
                market_data['weekly_candles'] = weekly_candles
            except:
                pass
            
            # Get monthly candles (for long-term)
            try:
                monthly_candles = await self.broker.get_historical_data(
                    symbol,
                    datetime.now() - timedelta(days=1095),
                    datetime.now(),
                    "month"
                )
                market_data['monthly_candles'] = monthly_candles
            except:
                pass
            
            # Get fundamentals (for mid-term, long-term)
            # Note: Would need broker API support
            # For now, placeholder
            market_data['fundamentals'] = {}
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
        
        return market_data
    
    def _get_regime_timeframe_for_style(self, style: TradingStyle) -> str:
        """Get appropriate regime timeframe for style"""
        mapping = {
            TradingStyle.INTRADAY: "15min",
            TradingStyle.SWING: "daily",
            TradingStyle.MIDTERM: "weekly",
            TradingStyle.LONGTERM: "weekly"
        }
        return mapping.get(style, "daily")
    
    def _get_style_from_trade(self, trade: Trade) -> Optional[TradingStyle]:
        """Determine trading style from trade"""
        strategy_name = trade.strategy_name
        
        if 'intraday' in strategy_name.lower():
            return TradingStyle.INTRADAY
        elif 'swing' in strategy_name.lower():
            return TradingStyle.SWING
        elif 'midterm' in strategy_name.lower():
            return TradingStyle.MIDTERM
        elif 'longterm' in strategy_name.lower():
            return TradingStyle.LONGTERM
        
        # Default to intraday if can't determine
        return TradingStyle.INTRADAY
    
    def _trade_to_position_dict(self, trade: Trade) -> Dict:
        """Convert Trade model to position dict for strategy"""
        return {
            'symbol': trade.symbol,
            'direction': trade.direction.value if hasattr(trade.direction, 'value') else trade.direction,
            'entry_price': trade.entry_price,
            'stop_loss': trade.stop_loss,
            'target': trade.target,
            'quantity': trade.quantity,
            'metadata': trade.metadata or {}
        }


logger.info("Multi-timeframe manager module loaded")
