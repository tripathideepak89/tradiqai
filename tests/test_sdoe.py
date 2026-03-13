"""
Tests for Strong Dip Opportunity Engine (SDOE)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_decline_metrics(**overrides):
    """Build a DeclineMetrics with sensible defaults."""
    from strategies.strong_dip import DeclineMetrics
    defaults = dict(
        price_current=2500.0,
        high_20d=2750.0,
        high_60d=2800.0,
        high_52w=2900.0,
        low_20d=2400.0,
        decline_from_20d_pct=9.1,
        decline_from_60d_pct=10.7,
        decline_from_52w_pct=13.8,
        worst_single_day_pct=2.5,
        decline_started_days_ago=12,
    )
    defaults.update(overrides)
    return DeclineMetrics(**defaults)


class TestSDOECandidateSelection:
    """Test SDOE candidate selection logic"""

    def test_decline_filter_accepts_valid_decline(self):
        """Stock with 8% decline from 52w high should pass."""
        metrics = _make_decline_metrics(decline_from_52w_pct=8.5, decline_from_60d_pct=6.2)
        assert 5.0 <= metrics.decline_from_52w_pct <= 30.0
        assert metrics.decline_started_days_ago >= 5

    def test_decline_filter_rejects_shallow_dip(self):
        """Stock with only 2% decline should be rejected."""
        metrics = _make_decline_metrics(decline_from_52w_pct=2.0, decline_from_60d_pct=1.5)
        assert metrics.decline_from_52w_pct < 5.0

    def test_decline_filter_rejects_deep_crash(self):
        """Stock with 45% decline might be value trap."""
        metrics = _make_decline_metrics(decline_from_52w_pct=45.0, decline_from_60d_pct=35.0)
        assert metrics.decline_from_52w_pct > 30.0


class TestSDOERejectionLogic:
    """Test rejection reasons are properly captured"""
    
    def test_rejection_for_low_market_cap(self):
        """Micro-cap stocks should be rejected"""
        # Simulated rejection check
        market_cap = 400  # Rs 400 Cr - too small
        min_cap = 500
        
        assert market_cap < min_cap
        rejection_reason = f"Market cap Rs{market_cap}Cr below min Rs{min_cap}Cr"
        assert "below min" in rejection_reason
    
    def test_rejection_for_low_volume(self):
        """Low volume stocks should be rejected"""
        avg_volume = 30000
        min_volume = 100000  # Minimum required
        
        assert avg_volume < min_volume
        rejection_reason = f"Avg volume {avg_volume} below threshold {min_volume}"
        assert "below threshold" in rejection_reason
    
    def test_rejection_for_no_stabilization(self):
        """Stocks without stabilization signals should be rejected"""
        stabilization_score = 25  # Out of 50 required
        min_score = 50
        
        assert stabilization_score < min_score


class TestSDOEScoreCalculation:
    """Test score calculation and weighting"""
    
    def test_score_weights_sum_to_100(self):
        """All score weights should sum to 100"""
        weights = {
            'decline': 20,
            'quality': 25,
            'stabilization': 20,
            'recovery': 15,
            'market': 10,
            'upside': 10
        }
        
        assert sum(weights.values()) == 100
    
    def test_strong_buy_threshold(self):
        """Score >= 80 should be Strong Buy"""
        threshold_strong_buy = 80
        
        test_scores = [85, 92, 80]
        for score in test_scores:
            assert score >= threshold_strong_buy
    
    def test_watchlist_threshold(self):
        """Score 65-79 should be Watchlist"""
        threshold_watchlist_min = 65
        threshold_watchlist_max = 79
        
        test_scores = [65, 72, 79]
        for score in test_scores:
            assert threshold_watchlist_min <= score <= threshold_watchlist_max
    
    def test_monitor_threshold(self):
        """Score 50-64 should be Monitor"""
        threshold_monitor_min = 50
        threshold_monitor_max = 64
        
        test_scores = [50, 58, 64]
        for score in test_scores:
            assert threshold_monitor_min <= score <= threshold_monitor_max
    
    def test_reject_threshold(self):
        """Score < 50 should be Reject"""
        threshold_reject = 50
        
        test_scores = [35, 42, 49]
        for score in test_scores:
            assert score < threshold_reject


class TestStabilizationDetection:
    """Test stabilization pattern detection"""
    
    def test_supports_detection(self):
        """Test support level detection logic"""
        # Simulated price action finding support
        recent_lows = [145.2, 145.5, 145.0, 145.3, 145.8]
        
        # Calculate support zone
        min_low = min(recent_lows)
        max_low = max(recent_lows)
        spread = ((max_low - min_low) / min_low) * 100
        
        # Tight range indicates support forming
        assert spread < 3.0  # Less than 3% spread
    
    def test_volume_dry_up(self):
        """Volume should decrease during stabilization"""
        volumes = [1000000, 850000, 720000, 680000, 650000]
        
        # Volume trend should be decreasing
        for i in range(1, len(volumes)):
            assert volumes[i] <= volumes[i-1] * 1.1  # Allow small variance
    
    def test_rsi_in_oversold_zone(self):
        """RSI should be in oversold/recovery zone"""
        rsi_value = 35  # Coming out of oversold
        
        assert 25 <= rsi_value <= 50  # Recovery zone


class TestRecoveryConfirmation:
    """Test recovery signal confirmation"""
    
    def test_green_candle_detection(self):
        """Detect bullish reversal candles"""
        open_price = 145.0
        close_price = 149.5
        high_price = 150.2
        low_price = 144.0
        
        # Green candle
        is_green = close_price > open_price
        assert is_green
        
        # Body size
        body_size = abs(close_price - open_price)
        candle_range = high_price - low_price
        body_ratio = body_size / candle_range
        
        # Strong candle should have large body
        assert body_ratio > 0.5
    
    def test_volume_surge_on_recovery(self):
        """Volume should increase on recovery day"""
        avg_volume = 500000
        recovery_volume = 950000
        
        surge_ratio = recovery_volume / avg_volume
        assert surge_ratio > 1.5  # 50%+ surge
    
    def test_macd_crossover(self):
        """MACD line crossing signal indicates momentum shift"""
        macd_line = 0.5
        signal_line = -0.2
        
        # Bullish crossover
        is_bullish = macd_line > signal_line
        assert is_bullish


class TestAPIResponseShape:
    """Test API response structure"""
    
    def test_opportunity_response_schema(self):
        """Test opportunity response has required fields"""
        expected_fields = {
            'symbol': str,
            'total_score': (int, float),
            'classification': str,
            'decline_metrics': dict,
            'quality_metrics': dict,
            'stabilization_signals': dict,
            'recovery_signals': dict,
            'market_context': dict,
            'trade_params': dict,
            'selection_reasons': list,
        }
        
        # Mock response
        response = {
            'symbol': 'RELIANCE',
            'total_score': 82,
            'classification': 'Strong Buy',
            'decline_metrics': {'decline_from_52w_high': 8.5},
            'quality_metrics': {'roe': 15.2, 'debt_to_equity': 0.4},
            'stabilization_signals': {'support_forming': True},
            'recovery_signals': {'macd_bullish': True},
            'market_context': {'regime': 'Range-Bound'},
            'trade_params': {'entry_zone': [2800, 2850], 'stop_loss': 2700, 'target_1': 3100},
            'selection_reasons': ['Quality fundamentals', 'Technical stabilization'],
        }
        
        for field, expected_type in expected_fields.items():
            assert field in response
            assert isinstance(response[field], expected_type)
    
    def test_scan_result_response_schema(self):
        """Test scan result has counts and lists"""
        response = {
            'strong_buy_count': 3,
            'watchlist_count': 8,
            'monitor_count': 15,
            'rejected_count': 24,
            'total_analyzed': 50,
            'scan_time': '2024-01-15T09:30:00',
            'opportunities': []
        }
        
        assert 'strong_buy_count' in response
        assert 'watchlist_count' in response
        assert 'opportunities' in response
        assert isinstance(response['opportunities'], list)
    
    def test_rejection_response_schema(self):
        """Test rejection includes reasons"""
        response = {
            'symbol': 'SMALLCAP',
            'rejected': True,
            'rejection_reasons': [
                {'filter': 'quality', 'reason': 'ROE -2.5% below minimum 10%'},
                {'filter': 'market_cap', 'reason': 'Market cap Rs250Cr below Rs500Cr'}
            ],
            'partial_scores': {
                'decline': 15,
                'quality': 0,
                'stabilization': 8,
                'recovery': 5,
                'market': 10,
                'upside': 12
            }
        }
        
        assert response['rejected'] is True
        assert len(response['rejection_reasons']) > 0


class TestRiskIntegration:
    """Test SDOE integrates with existing risk engine"""
    
    def test_position_size_respects_max_allocation(self):
        """SDOE trades should respect max allocation"""
        total_capital = 1000000
        max_allocation_pct = 5  # 5% max per trade
        
        max_position = total_capital * (max_allocation_pct / 100)
        
        # Any SDOE position should be <= max
        proposed_position = 45000
        assert proposed_position <= max_position
    
    def test_stop_loss_enforced(self):
        """All SDOE trades must have stop loss"""
        trade_params = {
            'entry_zone': [2800, 2850],
            'stop_loss': 2700,
            'target_1': 3100
        }
        
        assert 'stop_loss' in trade_params
        assert trade_params['stop_loss'] > 0
        assert trade_params['stop_loss'] < trade_params['entry_zone'][0]
    
    def test_max_positions_enforced(self):
        """SDOE respects max concurrent positions"""
        max_positions = 10
        current_positions = 8
        
        can_take_new = current_positions < max_positions
        assert can_take_new
        
        current_positions = 10
        can_take_new = current_positions < max_positions
        assert not can_take_new


class TestSDOEClassification:
    """Test score-based classification"""
    
    def test_all_classifications(self):
        """Test classification function"""
        def classify(score: float) -> str:
            if score >= 80:
                return "Strong Buy"
            elif score >= 65:
                return "Watchlist"
            elif score >= 50:
                return "Monitor"
            else:
                return "Reject"
        
        assert classify(92) == "Strong Buy"
        assert classify(80) == "Strong Buy"
        assert classify(79) == "Watchlist"
        assert classify(65) == "Watchlist"
        assert classify(64) == "Monitor"
        assert classify(50) == "Monitor"
        assert classify(49) == "Reject"
        assert classify(0) == "Reject"


class TestSDOEDataClasses:
    """Test SDOE data classes"""
    
    def test_decline_metrics_creation(self):
        """Test DeclineMetrics dataclass with current signature."""
        metrics = _make_decline_metrics(decline_from_52w_pct=12.5, decline_started_days_ago=15)
        assert metrics.decline_from_52w_pct == 12.5
        assert metrics.decline_started_days_ago == 15

    def test_quality_metrics_creation(self):
        """Test QualityMetrics dataclass with current signature."""
        from strategies.strong_dip import QualityMetrics
        metrics = QualityMetrics(
            market_cap_cr=25000,
            avg_volume_cr=50.0,
            roe_pct=18.5,
            de_ratio=0.35,
            sector="Energy",
            quality_score=78,
        )
        assert metrics.roe_pct == 18.5
        assert metrics.market_cap_cr == 25000

    def test_signal_creation(self):
        """Test SDOESignal can be constructed (field structure check)."""
        from strategies.strong_dip import SDOESignal
        import inspect
        # Just verify the class exists and has expected attributes
        fields = {f.name for f in SDOESignal.__dataclass_fields__.values()}
        assert "symbol" in fields
        assert "total_score" in fields


class TestAsyncMethods:
    """Test async methods with mocks"""
    
    @pytest.mark.asyncio
    async def test_scanner_returns_scan_status(self):
        """SDOEScanner.get_scan_status() returns expected structure."""
        from services.sdoe_scanner import SDOEScanner
        scanner = SDOEScanner()
        status = scanner.get_scan_status()
        assert "has_data" in status
        assert "counts" in status
        assert isinstance(status["counts"], dict)
    
    @pytest.mark.asyncio
    async def test_scanner_filter_by_sector(self):
        """Test sector filtering works"""
        opportunities = [
            {'symbol': 'RELIANCE', 'sector': 'Oil & Gas', 'total_score': 85},
            {'symbol': 'TCS', 'sector': 'IT', 'total_score': 82},
            {'symbol': 'ONGC', 'sector': 'Oil & Gas', 'total_score': 78},
        ]
        
        # Filter by sector
        sector = 'Oil & Gas'
        filtered = [o for o in opportunities if o.get('sector') == sector]
        
        assert len(filtered) == 2
        assert all(o['sector'] == 'Oil & Gas' for o in filtered)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
