"""Simple live-quote based strategy - No historical data required"""
import logging
from typing import Optional, Dict
from datetime import datetime

from strategies.base import BaseStrategy, Signal
from pre_entry_checks import PreEntryChecker
from adaptive_targets import AdaptiveTargetSystem, TimeBasedExit, VWAPBias
from utils.timezone import now_ist

logger = logging.getLogger(__name__)


class LiveSimpleStrategy(BaseStrategy):
    """Simple momentum strategy using only live quotes
    
    Rules:
    - Uses only current live quote data (no historical data required)
    - Entry: Price up X% from day's open with strong momentum
    - Stop loss: Fixed percentage below entry (e.g., 2%)
    - Target: Fixed risk-reward ratio (e.g., 1:2)
    - Exit: Stop loss or target hit, or end of day
    
    This strategy is designed to work without historical data access,
    relying only on real-time quote information.
    """
    
    def __init__(self, parameters: Dict = None, broker=None):
        default_params = {
            "min_price_change_pct": 1.0,  # Min % gain from open to trigger entry (lowered for more opportunities)
            "max_price_change_pct": 5.0,  # Max % gain (avoid chasing)
            "stop_loss_pct": 2.0,  # Stop loss % below entry
            "min_risk_reward": 1.5,  # CRITICAL: Minimum R:R ratio (Professional rule)
            "min_price": 50,  # Don't trade stocks below Rs50
            "max_price": 10000,  # Don't trade stocks above Rs10000 (raised for midcaps)
            "min_confidence": 0.6,  # Minimum confidence score to trade
            "use_adaptive_targets": True,  # Use structure/day-type based targets
            "enforce_pre_entry_checklist": True,  # Enforce professional checklist
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("LiveSimple", default_params)
        
        # Professional systems
        self.broker = broker
        if broker:
            self.pre_entry_checker = PreEntryChecker(broker)
            self.adaptive_targets = AdaptiveTargetSystem(broker)
        else:
            self.pre_entry_checker = None
            self.adaptive_targets = None
            logger.warning("⚠️ No broker provided - running without pre-entry checks")
    
    async def analyze(
        self,
        quote: Dict,
        symbol: str
    ) -> Optional[Signal]:
        """Analyze live quote and generate signal
        
        Args:
            quote: Live quote data with keys:
                   - ltp: Last traded price
                   - open: Day's open price
                   - high: Day's high price
                   - low: Day's low price
                   - close: Previous close (if available)
                   - change_pct: % change from open
            symbol: Stock symbol
            
        Returns:
            Signal if conditions met, None otherwise
        """
        try:
            # Extract quote data
            ltp = quote.get('ltp', 0)
            open_price = quote.get('open', ltp)
            high = quote.get('high', ltp)
            low = quote.get('low', ltp)
            prev_close = quote.get('close', open_price)
            
            if ltp == 0 or open_price == 0:
                logger.debug(f"{symbol}: Invalid quote data")
                return None
            
            # 1. Price range filter - avoid penny stocks and very expensive stocks
            if ltp < self.parameters['min_price'] or ltp > self.parameters['max_price']:
                logger.debug(f"{symbol}: Price Rs{ltp:.2f} outside range")
                return None
            
            # 2. Calculate intraday price change
            if open_price > 0:
                price_change_pct = ((ltp - open_price) / open_price) * 100
            else:
                price_change_pct = 0
            
            # 3. Momentum filter - price should be up but not too much
            min_change = self.parameters['min_price_change_pct']
            max_change = self.parameters['max_price_change_pct']
            
            if price_change_pct < min_change:
                logger.debug(f"{symbol}: Insufficient momentum ({price_change_pct:.2f}%)")
                return None
            
            if price_change_pct > max_change:
                logger.debug(f"{symbol}: Too much gain, avoid chasing ({price_change_pct:.2f}%)")
                return None
            
            # 4. Price position - should be near day's high (strong momentum)
            if high > 0:
                position_in_range = ((ltp - low) / (high - low)) * 100 if high > low else 50
                if position_in_range < 70:  # Should be in upper 30% of day's range
                    logger.debug(f"{symbol}: Price not near high ({position_in_range:.1f}%)")
                    return None
            
            # 5. Calculate entry and stop loss
            entry_price = ltp
            stop_loss_pct = self.parameters['stop_loss_pct']
            stop_loss = entry_price * (1 - stop_loss_pct / 100)
            
            # 6. PROFESSIONAL PRE-ENTRY CHECKLIST
            if self.parameters['enforce_pre_entry_checklist'] and self.pre_entry_checker:
                # Calculate initial target for R:R check
                initial_target = entry_price + ((entry_price - stop_loss) * self.parameters['min_risk_reward'])
                
                # Run complete checklist
                pre_entry_analysis = await self.pre_entry_checker.check_entry_conditions(
                    symbol=symbol,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target=initial_target,
                    quote=quote
                )
                
                # REJECT if checklist fails
                if not pre_entry_analysis.should_enter:
                    logger.info(f"❌ {symbol} REJECTED: {pre_entry_analysis.rejection_reason}")
                    return None
                
                # Use adaptive targets if enabled
                if self.parameters['use_adaptive_targets'] and self.adaptive_targets:
                    target, target_type = self.adaptive_targets.calculate_adaptive_target(
                        symbol=symbol,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        quote=quote,
                        day_type=pre_entry_analysis.day_type,
                        resistance=pre_entry_analysis.nearest_resistance
                    )
                else:
                    # Fallback to minimum R:R
                    risk = entry_price - stop_loss
                    target = entry_price + (risk * self.parameters['min_risk_reward'])
                    target_type = f"fixed_{self.parameters['min_risk_reward']}R"
            
            else:
                # Legacy mode (no checklist)
                logger.warning(f"⚠️ {symbol}: Trading WITHOUT pre-entry checklist - not recommended")
                risk = entry_price - stop_loss
                
                # Enforce minimum R:R
                min_target = entry_price + (risk * self.parameters['min_risk_reward'])
                target = min_target
                target_type = "legacy_minimum"
            
            
            # 7. Calculate confidence score
            confidence = self._calculate_confidence(
                price_change_pct,
                position_in_range,
                ltp,
                high,
                low
            )
            
            # 8. Check minimum confidence
            if confidence < self.parameters['min_confidence']:
                logger.debug(f"{symbol}: Low confidence ({confidence:.2f})")
                return None
            
            # 9. Calculate final R:R ratio
            risk = entry_price - stop_loss
            reward = target - entry_price
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # 10. Final R:R validation
            if risk_reward_ratio < self.parameters['min_risk_reward']:
                logger.warning(
                    f"❌ {symbol} REJECTED: R:R {risk_reward_ratio:.2f}:1 "
                    f"< minimum {self.parameters['min_risk_reward']}:1"
                )
                return None
            
            # Create signal
            signal = Signal(
                symbol=symbol,
                action="BUY",
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                quantity=1,  # Placeholder - risk engine will calculate
                confidence=confidence,
                reason=f"Momentum: +{price_change_pct:.1f}%, R:R={risk_reward_ratio:.2f}:1, Target={target_type}",
                timestamp=datetime.now()
            )
            
            logger.info("=" * 80)
            logger.info(f"✅ SIGNAL APPROVED: {symbol}")
            logger.info(f"   Entry: Rs{entry_price:.2f}")
            logger.info(f"   Stop:  Rs{stop_loss:.2f} (-{stop_loss_pct:.1f}%, Risk=Rs{risk:.2f})")
            logger.info(f"   Target: Rs{target:.2f} (+{((target-entry_price)/entry_price*100):.1f}%, Reward=Rs{reward:.2f})")
            logger.info(f"   R:R Ratio: {risk_reward_ratio:.2f}:1 {'✅' if risk_reward_ratio >= 1.5 else '⚠️'}")
            logger.info(f"   Target Type: {target_type}")
            logger.info(f"   Confidence: {confidence:.2f}")
            logger.info("=" * 80)
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    async def should_exit(self, position: Dict, current_quote: Dict) -> bool:
        """Check if position should be exited
        
        Exit conditions:
        - Stop loss hit
        - Target reached
        - Time-based exit (dead trade - no movement in 45 min)
        - End of day
        - Professional trailing stop
        
        Args:
            position: Position data with entry_price, stop_loss, target, entry_timestamp
            current_quote: Current live quote with ltp
            
        Returns:
            True if should exit, False otherwise
        """
        try:
            current_price = current_quote.get('ltp', 0)
            if current_price == 0:
                return False
            
            entry_price = position.get('entry_price', 0)
            stop_loss = position.get('stop_loss', 0)
            target = position.get('target', 0)
            entry_time = position.get('entry_timestamp')
            
            if entry_price == 0:
                return False
            
            # 1. Stop loss hit
            if current_price <= stop_loss:
                logger.info(f"{position['symbol']}: Stop loss hit at Rs{current_price:.2f}")
                return True
            
            # 2. Target reached
            if current_price >= target:
                logger.info(f"{position['symbol']}: Target reached at Rs{current_price:.2f}")
                return True
            
            # 3. TIME-BASED EXIT - Dead trade check
            if entry_time:
                should_exit_time, reason = TimeBasedExit.should_exit_on_time(
                    entry_time=entry_time,
                    current_price=current_price,
                    entry_price=entry_price,
                    candles_since_entry=0  # Would need to track this
                )
                
                if should_exit_time:
                    logger.info(f"{position['symbol']}: {reason} at Rs{current_price:.2f}")
                    return True
            
            # 4. PROFESSIONAL TRAILING STOP
            # Once price moves 0.5R → move stop to breakeven
            # Once price moves 1R → trail at 0.5R profit
            if self.adaptive_targets:
                should_trail, new_stop = self.adaptive_targets.should_trail_stop(
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    current_price=current_price,
                    target=target
                )
                
                if should_trail:
                    # Note: In production, you'd update the position's stop_loss
                    # For now, just check if it would trigger
                    if current_price < new_stop:
                        logger.info(f"{position['symbol']}: Trailing stop triggered at Rs{current_price:.2f}")
                        return True
            else:
                # Fallback: Simple trailing at breakeven after 0.5R
                risk = entry_price - stop_loss
                gain = current_price - entry_price
                
                if gain >= (risk * 0.5):
                    if current_price < entry_price:
                        logger.info(f"{position['symbol']}: Trailing stop at breakeven")
                        return True
            
            # 5. End of day exit (3:20 PM)
            now = now_ist().time()
            market_close_time = datetime.strptime("15:20", "%H:%M").time()
            
            if now >= market_close_time:
                logger.info(f"{position['symbol']}: End of day exit at Rs{current_price:.2f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking exit for {position.get('symbol')}: {e}")
            return False
    
    def _calculate_confidence(
        self,
        price_change_pct: float,
        position_in_range: float,
        ltp: float,
        high: float,
        low: float
    ) -> float:
        """Calculate signal confidence score (0-1)
        
        Higher confidence when:
        - Stronger momentum (higher price change %)
        - Price closer to day's high
        - Wider intraday range (more volatility/opportunity)
        """
        score = 0.5  # Base score
        
        # Momentum component (0-0.3)
        # Higher % gain = higher confidence
        if price_change_pct >= 3.0:
            score += 0.3
        elif price_change_pct >= 2.0:
            score += 0.2
        elif price_change_pct >= 1.5:
            score += 0.15
        elif price_change_pct >= 1.0:
            score += 0.1
        
        # Position in range component (0-0.2)
        # Closer to high = higher confidence
        if position_in_range >= 90:
            score += 0.2
        elif position_in_range >= 80:
            score += 0.15
        elif position_in_range >= 70:
            score += 0.1
        
        # Volatility component (0-0.1)
        # Wider range = more opportunity
        if high > 0 and ltp > 0:
            range_pct = ((high - low) / ltp) * 100
            if range_pct >= 3.0:
                score += 0.1
            elif range_pct >= 2.0:
                score += 0.05
        
        return min(score, 1.0)
