"""
News Impact Scoring Model for Indian Equities (NSE CASH)
Based on: Fundamental Shock + Novelty + Market Reaction + Tradability

Key Principle: "News does not move price. Surprise + positioning + liquidity imbalance moves price."
Trade only when: News Impact + Market Reaction + Tradability ALL confirm.
"""
import logging
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NewsCategory(str, Enum):
    """News categories with different impact profiles"""
    EARNINGS = "earnings"
    GUIDANCE = "guidance_revision"
    REGULATORY = "regulatory"
    ORDER_WIN = "order_win"
    MANAGEMENT_CHANGE = "management_change"
    MERGER_ACQUISITION = "merger_acquisition"
    PROMOTER_ACTION = "promoter_action"
    RUMOR = "rumor"
    GENERIC_PR = "generic_pr"


class NewsAction(str, Enum):
    """Action to take based on news"""
    IGNORE = "ignore"
    WATCH = "watch"
    TRADE_MODE = "trade_mode"


class TradeMode(str, Enum):
    """Trading timeframe"""
    INTRADAY = "intraday"
    SWING = "swing"
    POSITIONAL = "positional"


class Direction(str, Enum):
    """Direction bias from news"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Confidence(str, Enum):
    """Confidence in news analysis"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class NewsImpactScore:
    """Complete news impact analysis"""
    # Headline
    headline: str
    source: str
    timestamp: datetime
    symbol: str
    
    # Score components (0-100 total)
    fundamental_shock: float  # A: 0-40
    novelty_credibility: float  # B: 0-25
    time_sensitivity: float  # C: 0-10
    stock_context: float  # D: 0-10
    market_reaction: float  # E: 0-15 (MANDATORY)
    
    total_score: float  # 0-100
    
    # Analysis results
    action: NewsAction
    mode: TradeMode
    direction: Direction
    confidence: Confidence
    
    # Gating checks
    blocked_by: List[str]  # Reasons if blocked
    
    # Context
    price_at_detection: float
    current_price: float
    price_move_pct: float
    
    def log_analysis(self):
        """Log detailed news analysis"""
        logger.info("=" * 100)
        logger.info("📰 NEWS IMPACT ANALYSIS")
        logger.info("=" * 100)
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Headline: {self.headline}")
        logger.info(f"Source: {self.source} | Time: {self.timestamp.strftime('%H:%M:%S')}")
        logger.info("")
        logger.info("📊 IMPACT SCORE BREAKDOWN:")
        logger.info(f"  A) Fundamental Shock:     {self.fundamental_shock:>5.1f} / 40")
        logger.info(f"  B) Novelty & Credibility: {self.novelty_credibility:>5.1f} / 25")
        logger.info(f"  C) Time Sensitivity:      {self.time_sensitivity:>5.1f} / 10")
        logger.info(f"  D) Stock Context:         {self.stock_context:>5.1f} / 10")
        logger.info(f"  E) Market Reaction:       {self.market_reaction:>5.1f} / 15 {'✅' if self.market_reaction >= 7 else '❌'}")
        logger.info(f"  ─────────────────────────────────")
        logger.info(f"  TOTAL IMPACT SCORE:       {self.total_score:>5.1f} / 100")
        logger.info("")
        logger.info(f"🎯 ACTION: {self.action.value.upper()}")
        logger.info(f"📈 DIRECTION: {self.direction.value.upper()}")
        logger.info(f"⏰ MODE: {self.mode.value.upper()}")
        logger.info(f"🎲 CONFIDENCE: {self.confidence.value.upper()}")
        logger.info("")
        logger.info(f"💰 PRICE MOVEMENT:")
        logger.info(f"  Detection: Rs{self.price_at_detection:.2f}")
        logger.info(f"  Current:   Rs{self.current_price:.2f} ({self.price_move_pct:+.2f}%)")
        
        if self.blocked_by:
            logger.warning(f"")
            logger.warning(f"🚫 TRADE BLOCKED BY:")
            for reason in self.blocked_by:
                logger.warning(f"   • {reason}")
        
        logger.info("=" * 100)


class NewsImpactDetector:
    """
    News Impact Detection System
    
    Analyzes news and market reaction to determine tradability.
    Based on institutional approach: News + Order Flow Confluence.
    """
    
    def __init__(self, broker=None):
        self.broker = broker
        self.news_cache = {}  # Track seen news to avoid reprocessing
        
        # Thresholds
        self.intraday_thresholds = {
            'ignore': 39,
            'watch': 59,
            'trade_reduced': 74,
            'trade_normal': 75
        }
        
        self.swing_min_fundamental = 55  # A+B threshold for swing
        
    async def analyze_news_impact(
        self,
        headline: str,
        source: str,
        symbol: str,
        category: NewsCategory,
        timestamp: datetime = None,
        quote: Dict = None
    ) -> NewsImpactScore:
        """
        Analyze news impact using 5-component model
        
        Returns complete NewsImpactScore with tradability assessment
        """
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Check if already seen
        cache_key = f"{symbol}_{headline[:50]}_{timestamp.strftime('%Y%m%d%H%M')}"
        if cache_key in self.news_cache:
            logger.debug(f"News already processed: {headline[:50]}...")
            return self.news_cache[cache_key]
        
        # A) Fundamental Shock Score (0-40)
        fundamental_shock = self._score_fundamental_shock(category, headline)
        
        # B) Novelty & Credibility Score (0-25)
        novelty_credibility = self._score_novelty_credibility(source, headline, symbol, timestamp)
        
        # C) Time Sensitivity Score (0-10)
        time_sensitivity = self._score_time_sensitivity(category, timestamp)
        
        # D) Stock Context Score (0-10)
        stock_context = self._score_stock_context(symbol, quote)
        
        # E) Market Reaction Score (0-15) - MANDATORY
        # Wait 1 candle if just released
        market_reaction = 0
        price_at_detection = quote.get('ltp', 0) if quote else 0
        current_price = price_at_detection
        
        if quote:
            market_reaction = await self._score_market_reaction(symbol, quote, timestamp)
            current_price = quote.get('ltp', price_at_detection)
        
        # Calculate total
        total_score = (
            fundamental_shock +
            novelty_credibility +
            time_sensitivity +
            stock_context +
            market_reaction
        )
        
        # Determine direction
        direction = self._infer_direction(category, headline, quote)
        
        # Determine mode (intraday vs swing vs positional)
        mode = self._determine_mode(
            fundamental_shock,
            novelty_credibility,
            time_sensitivity,
            market_reaction
        )
        
        # Determine confidence
        confidence = self._calculate_confidence(
            total_score,
            market_reaction,
            fundamental_shock + novelty_credibility
        )
        
        # Apply trade gating rules
        action, blocked_by = self._apply_gating_rules(
            total_score=total_score,
            market_reaction=market_reaction,
            price_at_detection=price_at_detection,
            current_price=current_price,
            mode=mode,
            quote=quote
        )
        
        price_move_pct = ((current_price - price_at_detection) / price_at_detection * 100
                          if price_at_detection > 0 else 0)
        
        # Create result
        result = NewsImpactScore(
            headline=headline,
            source=source,
            timestamp=timestamp,
            symbol=symbol,
            fundamental_shock=fundamental_shock,
            novelty_credibility=novelty_credibility,
            time_sensitivity=time_sensitivity,
            stock_context=stock_context,
            market_reaction=market_reaction,
            total_score=total_score,
            action=action,
            mode=mode,
            direction=direction,
            confidence=confidence,
            blocked_by=blocked_by,
            price_at_detection=price_at_detection,
            current_price=current_price,
            price_move_pct=price_move_pct
        )
        
        # Cache it
        self.news_cache[cache_key] = result
        
        # Log analysis
        result.log_analysis()
        
        return result
    
    def _score_fundamental_shock(self, category: NewsCategory, headline: str) -> float:
        """
        A) Fundamental Shock Score (0-40)
        
        How much does this change long-term value?
        """
        
        # Base scores by category
        base_scores = {
            NewsCategory.EARNINGS: 32,  # 25-40 range, use 32 as base
            NewsCategory.GUIDANCE: 35,
            NewsCategory.ORDER_WIN: 22,  # 15-30 range
            NewsCategory.REGULATORY: 30,  # 20-40 range
            NewsCategory.PROMOTER_ACTION: 27,  # 20-35 range
            NewsCategory.MANAGEMENT_CHANGE: 20,  # 15-25 range
            NewsCategory.MERGER_ACQUISITION: 27,  # 20-35 range
            NewsCategory.RUMOR: 5,  # 0-10 range
            NewsCategory.GENERIC_PR: 2  # 0-5 range
        }
        
        base_score = base_scores.get(category, 10)
        
        # Materiality factor from headline keywords
        materiality = self._assess_materiality(headline)
        
        final_score = base_score * materiality
        
        return min(40, max(0, final_score))
    
    def _assess_materiality(self, headline: str) -> float:
        """
        Assess materiality from headline keywords
        
        Returns: 0.3 (minor), 0.6 (moderate), 1.0 (material)
        """
        headline_lower = headline.lower()
        
        # High materiality keywords
        high_impact = [
            'beat', 'miss', 'surprise', 'surge', 'plunge',
            'major', 'significant', 'substantial', 'record',
            'ban', 'penalty', 'investigation', 'fraud',
            'acquisition', 'merger', 'takeover',
            'raises guidance', 'cuts guidance', 'restructuring'
        ]
        
        # Moderate materiality
        moderate_impact = [
            'rises', 'falls', 'increases', 'decreases',
            'order', 'contract', 'deal', 'partnership',
            'appoints', 'resigns', 'announces'
        ]
        
        # Check matches
        if any(word in headline_lower for word in high_impact):
            return 1.0
        elif any(word in headline_lower for word in moderate_impact):
            return 0.6
        else:
            return 0.3
    
    def _score_novelty_credibility(
        self,
        source: str,
        headline: str,
        symbol: str,
        timestamp: datetime
    ) -> float:
        """
        B) Novelty & Credibility Score (0-25)
        
        Is it new and trustworthy?
        """
        
        # Credibility (0-15)
        source_lower = source.lower()
        
        if any(x in source_lower for x in ['nse', 'bse', 'sebi', 'company filing', 'exchange']):
            credibility = 15  # Official exchange filing
        elif any(x in source_lower for x in ['reuters', 'bloomberg', 'moneycontrol', 'et']):
            credibility = 11  # Major financial wire
        elif any(x in source_lower for x in ['broker', 'analyst', 'research']):
            credibility = 8  # Broker note
        elif any(x in source_lower for x in ['twitter', 'social', 'rumor']):
            credibility = 1  # Social media
        else:
            credibility = 6  # Generic news
        
        # Novelty (0-10)
        # Check if we've seen similar news recently
        similar_seen = self._check_novelty(symbol, headline, timestamp)
        
        if not similar_seen:
            novelty = 10  # First time reported
        elif similar_seen == 'recent':
            novelty = 3  # Rehash of recent news
        else:
            novelty = 1  # Old news resurfacing
        
        return credibility + novelty
    
    def _check_novelty(self, symbol: str, headline: str, timestamp: datetime) -> Optional[str]:
        """Check if similar news seen recently"""
        
        # Check cache for similar headlines in last 24 hours
        cutoff = timestamp - timedelta(hours=24)
        
        for cache_key, cached_score in self.news_cache.items():
            if (cached_score.symbol == symbol and
                cached_score.timestamp > cutoff):
                
                # Simple similarity check (can be improved with fuzzy matching)
                if len(set(headline.lower().split()) & set(cached_score.headline.lower().split())) > 3:
                    if cached_score.timestamp > (timestamp - timedelta(hours=4)):
                        return 'recent'
                    else:
                        return 'old'
        
        return None
    
    def _score_time_sensitivity(self, category: NewsCategory, timestamp: datetime) -> float:
        """
        C) Time Sensitivity Score (0-10)
        
        How quickly does it matter?
        """
        
        # Immediate catalysts
        immediate_categories = [
            NewsCategory.EARNINGS,
            NewsCategory.GUIDANCE,
            NewsCategory.REGULATORY
        ]
        
        if category in immediate_categories:
            return 9  # 8-10 range
        
        # Medium-term
        medium_categories = [
            NewsCategory.ORDER_WIN,
            NewsCategory.MANAGEMENT_CHANGE
        ]
        
        if category in medium_categories:
            return 5  # 4-6 range
        
        # Long-term
        return 2  # 1-3 range
    
    def _score_stock_context(self, symbol: str, quote: Dict = None) -> float:
        """
        D) Stock Context Score (0-10)
        
        How "primed" is the stock to react?
        """
        
        if not quote:
            return 5  # Neutral if no data
        
        # Check volume (proxy for attention)
        volume = quote.get('volume', 0)
        avg_volume = quote.get('avg_volume', volume)
        
        if avg_volume > 0:
            volume_ratio = volume / avg_volume
            
            if volume_ratio > 1.5:
                volume_score = 4
            elif volume_ratio > 1.0:
                volume_score = 2
            else:
                volume_score = 1
        else:
            volume_score = 1
        
        # Check volatility (range as proxy)
        high = quote.get('high', 0)
        low = quote.get('low', 0)
        open_price = quote.get('open', 0)
        
        if open_price > 0:
            intraday_range_pct = ((high - low) / open_price) * 100
            
            if intraday_range_pct > 3.0:
                volatility_score = 4
            elif intraday_range_pct > 1.5:
                volatility_score = 2
            else:
                volatility_score = 1
        else:
            volatility_score = 1
        
        # Check liquidity (spread as proxy)
        ltp = quote.get('ltp', 0)
        if ltp > 100:
            liquidity_score = 2  # Decent liquidity for Rs100+ stocks
        else:
            liquidity_score = 1
        
        total = volume_score + volatility_score + liquidity_score
        
        return min(10, total)
    
    async def _score_market_reaction(
        self,
        symbol: str,
        quote: Dict,
        news_timestamp: datetime
    ) -> float:
        """
        E) Market Reaction Score (0-15) - MANDATORY
        
        This prevents trading headlines that don't move price.
        """
        
        # Volume Spike (0-6)
        volume = quote.get('volume', 0)
        avg_volume = quote.get('avg_volume', volume)
        
        if avg_volume > 0:
            volume_ratio = volume / avg_volume
            
            if volume_ratio >= 3.0:
                volume_score = 6
            elif volume_ratio >= 2.0:
                volume_score = 4
            elif volume_ratio >= 1.2:
                volume_score = 2
            else:
                volume_score = 0
        else:
            volume_score = 0
        
        # Range Expansion / ATR (0-4)
        high = quote.get('high', 0)
        low = quote.get('low', 0)
        open_price = quote.get('open', 0)
        
        if open_price > 0:
            current_range_pct = ((high - low) / open_price) * 100
            
            # Assume normal ATR is ~1.5% (can be calculated properly)
            normal_atr_pct = 1.5
            
            if current_range_pct > (normal_atr_pct * 2):
                range_score = 4
            elif current_range_pct > (normal_atr_pct * 1.3):
                range_score = 2
            else:
                range_score = 0
        else:
            range_score = 0
        
        # Structure Break (0-5)
        ltp = quote.get('ltp', 0)
        
        if ltp >= high * 0.98:  # Near/at high
            structure_score = 5
        elif ltp <= low * 1.02:  # Near/at low
            structure_score = 5
        elif ltp > open_price * 1.01:  # Above open
            structure_score = 2
        else:
            structure_score = 0
        
        total = volume_score + range_score + structure_score
        
        return min(15, total)
    
    def _infer_direction(
        self,
        category: NewsCategory,
        headline: str,
        quote: Dict = None
    ) -> Direction:
        """
        Infer direction from news + price action
        """
        
        headline_lower = headline.lower()
        
        # Bullish keywords
        bullish_keywords = [
            'beat', 'exceeds', 'raises', 'upgrade', 'win', 'wins',
            'positive', 'strong', 'growth', 'expansion', 'buyback',
            'dividend increase', 'profit surge'
        ]
        
        # Bearish keywords
        bearish_keywords = [
            'miss', 'cuts', 'downgrade', 'loss', 'penalty', 'ban',
            'investigation', 'fraud', 'resign', 'weak', 'decline',
            'stake sale', 'pledge increase'
        ]
        
        # Check keywords
        is_bullish = any(word in headline_lower for word in bullish_keywords)
        is_bearish = any(word in headline_lower for word in bearish_keywords)
        
        if is_bullish and not is_bearish:
            base_direction = Direction.BULLISH
        elif is_bearish and not is_bullish:
            base_direction = Direction.BEARISH
        else:
            base_direction = Direction.NEUTRAL
        
        # Validate with VWAP if available
        if quote:
            ltp = quote.get('ltp', 0)
            vwap = quote.get('vwap', 0)
            
            if vwap > 0:
                if base_direction == Direction.BULLISH and ltp < vwap:
                    logger.warning(f"Direction conflict: Bullish news but price below VWAP")
                elif base_direction == Direction.BEARISH and ltp > vwap:
                    logger.warning(f"Direction conflict: Bearish news but price above VWAP")
        
        return base_direction
    
    def _determine_mode(
        self,
        fundamental_shock: float,
        novelty_credibility: float,
        time_sensitivity: float,
        market_reaction: float
    ) -> TradeMode:
        """Determine appropriate trading timeframe"""
        
        # High time sensitivity + market reaction = intraday
        if time_sensitivity >= 8 and market_reaction >= 7:
            return TradeMode.INTRADAY
        
        # High fundamental but lower immediacy = swing
        if fundamental_shock >= 25:
            return TradeMode.SWING
        
        # Default intraday for now
        return TradeMode.INTRADAY
    
    def _calculate_confidence(
        self,
        total_score: float,
        market_reaction: float,
        fundamental_credibility: float
    ) -> Confidence:
        """Calculate overall confidence"""
        
        # High confidence requires both score and confirmation
        if total_score >= 75 and market_reaction >= 10:
            return Confidence.HIGH
        
        # Medium confidence
        if total_score >= 60 and market_reaction >= 7:
            return Confidence.MEDIUM
        
        # Low confidence
        return Confidence.LOW
    
    def _apply_gating_rules(
        self,
        total_score: float,
        market_reaction: float,
        price_at_detection: float,
        current_price: float,
        mode: TradeMode,
        quote: Dict = None
    ) -> Tuple[NewsAction, List[str]]:
        """
        Apply trade gating rules (G1-G4)
        
        Returns: (action, blocked_by_reasons)
        """
        
        blocked_by = []
        
        # G1) No-confirmation block
        if market_reaction < 7:
            blocked_by.append("G1: Market reaction insufficient (< 7/15)")
            return NewsAction.WATCH, blocked_by
        
        # G2) Chasing block
        if price_at_detection > 0:
            move_pct = abs((current_price - price_at_detection) / price_at_detection * 100)
            
            if mode == TradeMode.INTRADAY and move_pct > 1.5:
                blocked_by.append(f"G2: Chasing block - already moved {move_pct:.2f}% (> 1.5%)")
                return NewsAction.WATCH, blocked_by
            
            if mode == TradeMode.SWING and move_pct > 4.0:
                blocked_by.append(f"G2: Chasing block - already moved {move_pct:.2f}% (> 4.0%)")
                return NewsAction.WATCH, blocked_by
        
        # G3) Liquidity block
        # (Would need bid-ask spread data - skip for now)
        
        # G4) Event risk block
        # (Would check calendar - skip for now)
        
        # Determine action from score
        if mode == TradeMode.INTRADAY:
            if total_score >= self.intraday_thresholds['trade_normal']:
                return NewsAction.TRADE_MODE, blocked_by
            elif total_score >= self.intraday_thresholds['trade_reduced']:
                return NewsAction.TRADE_MODE, blocked_by  # Will reduce size elsewhere
            elif total_score >= self.intraday_thresholds['watch']:
                return NewsAction.WATCH, blocked_by
            else:
                return NewsAction.IGNORE, blocked_by
        
        else:  # SWING/POSITIONAL
            # More lenient for swing - focus on fundamental
            if total_score >= 55:
                return NewsAction.TRADE_MODE, blocked_by
            elif total_score >= 40:
                return NewsAction.WATCH, blocked_by
            else:
                return NewsAction.IGNORE, blocked_by
