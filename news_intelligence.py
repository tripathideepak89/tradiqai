"""
Enhanced News Intelligence Layer
Adds sentiment analysis, clustering, and learning capabilities to news processing
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


@dataclass
class NewsCluster:
    """Related news items for same stock/event"""
    symbol: str
    primary_news: str  # Main headline
    related_news: List[str]  # Similar headlines
    first_seen: datetime
    last_updated: datetime
    impact_scores: List[float]
    max_impact: float
    trade_triggered: bool = False


class SentimentAnalyzer:
    """
    Intelligent sentiment analysis for news headlines
    Uses keyword-based approach optimized for Indian market
    """
    
    def __init__(self):
        # Positive keywords with intensity scores
        self.positive_keywords = {
            # Strong positive (1.0)
            "record": 1.0, "surge": 1.0, "soars": 1.0, "stellar": 1.0,
            "breakthrough": 1.0, "exceptional": 1.0, "beats": 1.0,
            "doubles": 1.0, "triples": 1.0, "blockbuster": 1.0,
            
            # Moderate positive (0.7)
            "strong": 0.7, "growth": 0.7, "rises": 0.7, "gains": 0.7,
            "improves": 0.7, "expands": 0.7, "upgrade": 0.7,
            "positive": 0.7, "wins": 0.7, "success": 0.7,
            
            # Mild positive (0.4)
            "announces": 0.4, "plans": 0.4, "eyes": 0.4,
            "considers": 0.4, "expects": 0.4
        }
        
        # Negative keywords with intensity scores
        self.negative_keywords = {
            # Strong negative (-1.0)
            "crash": -1.0, "plunges": -1.0, "collapse": -1.0,
            "scandal": -1.0, "fraud": -1.0, "investigation": -1.0,
            "penalty": -1.0, "ban": -1.0, "defaults": -1.0,
            
            # Moderate negative (-0.7)
            "misses": -0.7, "falls": -0.7, "declines": -0.7,
            "weak": -0.7, "downgrade": -0.7, "concern": -0.7,
            "disappoints": -0.7, "cuts": -0.7, "losses": -0.7,
            
            # Mild negative (-0.4)
            "delays": -0.4, "slows": -0.4, "uncertain": -0.4,
            "challenges": -0.4, "risks": -0.4
        }
        
        # Magnitude multipliers
        self.magnitude_multipliers = {
            "significantly": 1.3,
            "substantially": 1.3,
            "sharply": 1.2,
            "dramatically": 1.2,
            "slightly": 0.6,
            "marginally": 0.5,
            "modestly": 0.7
        }
    
    def analyze_sentiment(self, headline: str) -> Tuple[float, str]:
        """
        Analyze sentiment of news headline
        
        Returns: (sentiment_score, sentiment_label)
        - sentiment_score: -1.0 to +1.0
        - sentiment_label: "VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"
        """
        headline_lower = headline.lower()
        
        # Find positive matches
        positive_score = 0.0
        positive_matches = []
        for keyword, intensity in self.positive_keywords.items():
            if keyword in headline_lower:
                positive_matches.append((keyword, intensity))
                positive_score += intensity
        
        # Find negative matches
        negative_score = 0.0
        negative_matches = []
        for keyword, intensity in self.negative_keywords.items():
            if keyword in headline_lower:
                negative_matches.append((keyword, intensity))
                negative_score += intensity
        
        # Apply magnitude multipliers
        multiplier = 1.0
        for modifier, mult in self.magnitude_multipliers.items():
            if modifier in headline_lower:
                multiplier = max(multiplier, mult)
        
        # Calculate final sentiment
        raw_sentiment = (positive_score + negative_score) * multiplier
        
        # Normalize to -1.0 to +1.0
        sentiment_score = max(-1.0, min(1.0, raw_sentiment))
        
        # Determine label
        if sentiment_score >= 0.7:
            label = "VERY_POSITIVE"
        elif sentiment_score >= 0.3:
            label = "POSITIVE"
        elif sentiment_score <= -0.7:
            label = "VERY_NEGATIVE"
        elif sentiment_score <= -0.3:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"
        
        logger.debug(f"[SENTIMENT] '{headline}' -> {sentiment_score:.2f} ({label})")
        
        return sentiment_score, label
    
    def extract_key_entities(self, headline: str) -> Dict[str, List[str]]:
        """
        Extract key entities from headline (numbers, percentages, companies)
        """
        entities = {
            'numbers': [],
            'percentages': [],
            'amounts': []
        }
        
        # Extract percentages
        pct_pattern = r'(\d+\.?\d*)\s*%'
        percentages = re.findall(pct_pattern, headline)
        entities['percentages'] = percentages
        
        # Extract amounts (Rs/crore/lakh)
        amount_pattern = r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(crore|lakh|billion|million)?'
        amounts = re.findall(amount_pattern, headline, re.IGNORECASE)
        entities['amounts'] = amounts
        
        # Extract standalone numbers
        number_pattern = r'\b(\d+(?:,\d+)*(?:\.\d+)?)\b'
        numbers = re.findall(number_pattern, headline)
        entities['numbers'] = [n for n in numbers if n not in percentages]
        
        return entities


class NewsClusterManager:
    """
    Manages news clustering to avoid duplicate trades on same event
    """
    
    def __init__(self, similarity_window_minutes: int = 30):
        self.clusters: Dict[str, List[NewsCluster]] = defaultdict(list)
        self.similarity_window = timedelta(minutes=similarity_window_minutes)
        self.min_similarity_score = 0.6
    
    def add_news(
        self,
        symbol: str,
        headline: str,
        timestamp: datetime,
        impact_score: float
    ) -> Tuple[bool, Optional[NewsCluster]]:
        """
        Add news to clusters
        
        Returns: (is_duplicate, cluster)
        - is_duplicate: True if similar news already exists
        - cluster: The cluster this news belongs to
        """
        # Find existing cluster for this symbol within time window
        for cluster in self.clusters[symbol]:
            time_diff = timestamp - cluster.first_seen
            
            # Check if within time window
            if abs(time_diff.total_seconds()) > self.similarity_window.total_seconds():
                continue
            
            # Check similarity
            similarity = self._calculate_similarity(headline, cluster.primary_news)
            
            if similarity >= self.min_similarity_score:
                # Add to existing cluster
                cluster.related_news.append(headline)
                cluster.last_updated = timestamp
                cluster.impact_scores.append(impact_score)
                cluster.max_impact = max(cluster.max_impact, impact_score)
                
                logger.info(f"[CLUSTER] Added to existing cluster: {symbol}")
                logger.info(f"  Primary: {cluster.primary_news[:80]}...")
                logger.info(f"  New: {headline[:80]}...")
                logger.info(f"  Similarity: {similarity:.2f}")
                
                return True, cluster
        
        # Create new cluster
        new_cluster = NewsCluster(
            symbol=symbol,
            primary_news=headline,
            related_news=[],
            first_seen=timestamp,
            last_updated=timestamp,
            impact_scores=[impact_score],
            max_impact=impact_score,
            trade_triggered=False
        )
        
        self.clusters[symbol].append(new_cluster)
        
        logger.info(f"[CLUSTER] Created new cluster for {symbol}")
        
        return False, new_cluster
    
    def _calculate_similarity(self, headline1: str, headline2: str) -> float:
        """
        Calculate similarity between two headlines
        Uses simple word overlap method
        """
        # Normalize
        h1_lower = headline1.lower()
        h2_lower = headline2.lower()
        
        # Extract words (remove common stopwords)
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
        
        words1 = set([w for w in re.findall(r'\b\w+\b', h1_lower) if w not in stopwords])
        words2 = set([w for w in re.findall(r'\b\w+\b', h2_lower) if w not in stopwords])
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0.0
        
        return similarity
    
    def mark_trade_triggered(self, cluster: NewsCluster) -> None:
        """Mark that a trade was triggered for this cluster"""
        cluster.trade_triggered = True
        logger.info(f"[CLUSTER] Trade triggered for cluster: {cluster.symbol}")
    
    def cleanup_old_clusters(self, max_age_hours: int = 4) -> None:
        """Remove clusters older than max_age_hours"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for symbol in list(self.clusters.keys()):
            self.clusters[symbol] = [
                c for c in self.clusters[symbol]
                if c.last_updated >= cutoff
            ]
            
            if not self.clusters[symbol]:
                del self.clusters[symbol]


class NewsPriorityQueue:
    """
    Intelligent priority queue for news processing
    Prioritizes high-impact, actionable news
    """
    
    def __init__(self):
        self.queue: List[Tuple[float, datetime, dict]] = []
    
    def add_news(
        self,
        news_item: dict,
        impact_score: float,
        timestamp: datetime
    ) -> None:
        """
        Add news to priority queue
        Priority = impact_score + time_decay_factor
        """
        # Calculate time decay (newer = higher priority)
        age_minutes = (datetime.now() - timestamp).total_seconds() / 60
        time_decay = max(0, 100 - age_minutes)  # Decays over 100 minutes
        
        priority = impact_score + (time_decay * 0.1)  # Time adds up to 10 points
        
        self.queue.append((priority, timestamp, news_item))
        
        # Sort by priority (descending)
        self.queue.sort(key=lambda x: x[0], reverse=True)
        
        logger.debug(f"[QUEUE] Added news: {news_item.get('symbol')} | Priority: {priority:.1f}")
    
    def get_top_news(self, count: int = 5) -> List[dict]:
        """Get top N news items by priority"""
        return [item[2] for item in self.queue[:count]]
    
    def remove_processed(self, news_item: dict) -> None:
        """Remove processed news from queue"""
        self.queue = [
            (p, t, n) for p, t, n in self.queue
            if n.get('symbol') != news_item.get('symbol') or
               n.get('headline') != news_item.get('headline')
        ]


class NewsIntelligenceEngine:
    """
    Main intelligence engine combining all enhanced features
    """
    
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.cluster_manager = NewsClusterManager(similarity_window_minutes=30)
        self.priority_queue = NewsPriorityQueue()
        
        # Performance tracking
        self.news_performance: Dict[str, Dict] = {}  # Track news -> price outcome
        
        logger.info("[OK] News Intelligence Engine initialized")
        logger.info("   → Sentiment analysis active")
        logger.info("   → News clustering enabled")
        logger.info("   → Priority queue ready")
    
    def process_news(
        self,
        symbol: str,
        headline: str,
        timestamp: datetime,
        impact_score: float
    ) -> Dict:
        """
        Intelligent news processing pipeline
        
        Returns: Enhanced news insights
        """
        # 1. Sentiment analysis
        sentiment_score, sentiment_label = self.sentiment_analyzer.analyze_sentiment(headline)
        
        # 2. Entity extraction
        entities = self.sentiment_analyzer.extract_key_entities(headline)
        
        # 3. Check for duplicates/clusters
        is_duplicate, cluster = self.cluster_manager.add_news(
            symbol, headline, timestamp, impact_score
        )
        
        # 4. Calculate conviction score (impact + sentiment alignment)
        conviction = self._calculate_conviction(impact_score, sentiment_score)
        
        # 5. Determine if tradeable
        is_tradeable = self._determine_tradeability(
            impact_score, is_duplicate, cluster, sentiment_label
        )
        
        insights = {
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'entities': entities,
            'is_duplicate': is_duplicate,
            'cluster_size': len(cluster.related_news) + 1 if cluster else 1,
            'conviction': conviction,
            'is_tradeable': is_tradeable,
            'cluster': cluster
        }
        
        logger.info(f"[INTELLIGENCE] {symbol} | Sentiment: {sentiment_label} ({sentiment_score:+.2f})")
        logger.info(f"  Conviction: {conviction:.1f}/100 | Tradeable: {is_tradeable}")
        if is_duplicate:
            logger.info(f"  ⚠️ Duplicate news (cluster size: {insights['cluster_size']})")
        
        return insights
    
    def _calculate_conviction(self, impact_score: float, sentiment_score: float) -> float:
        """
        Calculate conviction score (0-100)
        
        Conviction = impact_score + sentiment_alignment_bonus
        """
        # Sentiment alignment bonus (0-20 points)
        # Strong sentiment (positive or negative) adds conviction
        sentiment_bonus = abs(sentiment_score) * 20
        
        conviction = min(100, impact_score + sentiment_bonus)
        
        return conviction
    
    def _determine_tradeability(
        self,
        impact_score: float,
        is_duplicate: bool,
        cluster: Optional[NewsCluster],
        sentiment_label: str
    ) -> bool:
        """
        Determine if news is tradeable based on intelligent rules
        """
        # Rule 1: Don't trade duplicates unless impact significantly higher
        if is_duplicate and cluster:
            if cluster.trade_triggered:
                logger.info("  ❌ Trade already triggered for this cluster")
                return False
            
            # Allow if this news has significantly higher impact
            if impact_score <= cluster.max_impact * 1.2:
                logger.info("  ❌ Similar news already processed")
                return False
        
        # Rule 2: Must have clear sentiment (not neutral)
        if sentiment_label == "NEUTRAL":
            logger.info("  ❌ Neutral sentiment - no clear direction")
            return False
        
        # Rule 3: Minimum impact threshold
        if impact_score < 60:
            logger.info("  ❌ Impact score too low")
            return False
        
        return True
    
    def adjust_position_size(
        self,
        base_position_size: float,
        conviction: float,
        sentiment_score: float
    ) -> float:
        """
        Intelligently adjust position size based on conviction
        
        High conviction = larger position
        Low conviction = smaller position
        """
        # Conviction factor (0.5x to 1.5x)
        if conviction >= 85:
            size_multiplier = 1.3  # Very high conviction
        elif conviction >= 75:
            size_multiplier = 1.15  # High conviction
        elif conviction >= 65:
            size_multiplier = 1.0  # Normal
        else:
            size_multiplier = 0.7  # Low conviction
        
        adjusted_size = base_position_size * size_multiplier
        
        logger.info(f"[POSITION SIZING] Base: {base_position_size:.2f} → Adjusted: {adjusted_size:.2f}")
        logger.info(f"  Conviction: {conviction:.1f} | Multiplier: {size_multiplier}x")
        
        return adjusted_size
    
    def cleanup(self) -> None:
        """Periodic cleanup of old data"""
        self.cluster_manager.cleanup_old_clusters(max_age_hours=4)
        logger.debug("[CLEANUP] Old news clusters removed")
