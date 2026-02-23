"""Multi-Timeframe Performance Monitor
======================================

Monitor and visualize performance across all trading styles:
- Intraday (20%)
- Swing (30%)  
- Mid-term (30%)
- Long-term (20%)

Shows:
- P&L by style
- Win rates
- R-multiples
- Capital allocation
- Expected vs actual returns
- Projections
"""
import logging
from typing import Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Trade, TradeStatus
from trading_styles import TradingStyle, TradingStylesConfig
from capital_allocator import CapitalAllocator

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor multi-timeframe trading performance"""
    
    def __init__(self, db_session: Session, total_capital: float):
        self.db = db_session
        self.capital_allocator = CapitalAllocator(db_session, total_capital)
        
    def get_style_performance(self, style: TradingStyle, days: int = 30) -> Dict:
        """Get performance metrics for a trading style
        
        Args:
            style: Trading style
            days: Lookback period
            
        Returns:
            Dict with performance metrics
        """
        start_date = datetime.now() - timedelta(days=days)
        
        # Get closed trades for this style
        trades = self.db.query(Trade).filter(
            Trade.strategy_name == style.value,
            Trade.status == TradeStatus.CLOSED,
            Trade.exit_timestamp >= start_date
        ).all()
        
        if not trades:
            return {
                "style": style.value,
                "trades": 0,
                "total_pnl": 0,
                "win_rate": 0,
                "avg_r": 0,
                "best_trade": 0,
                "worst_trade": 0
            }
        
        # Calculate metrics
        total_pnl = sum(t.realized_pnl or 0 for t in trades)
        wins = [t for t in trades if (t.realized_pnl or 0) > 0]
        losses = [t for t in trades if (t.realized_pnl or 0) < 0]
        
        win_rate = len(wins) / len(trades) if trades else 0
        
        # Calculate R-multiples
        r_multiples = []
        for t in trades:
            if t.realized_pnl and t.entry_price and t.stop_loss:
                risk = abs((t.entry_price - t.stop_loss) * t.quantity)
                if risk > 0:
                    r = t.realized_pnl / risk
                    r_multiples.append(r)
        
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
        
        best_trade = max((t.realized_pnl or 0 for t in trades)) if trades else 0
        worst_trade = min((t.realized_pnl or 0 for t in trades)) if trades else 0
        
        return {
            "style": style.value,
            "trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "total_pnl": total_pnl,
            "win_rate": win_rate * 100,
            "avg_r": avg_r,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "period_days": days
        }
    
    def get_portfolio_performance(self, days: int = 30) -> Dict:
        """Get overall portfolio performance"""
        performance = {}
        
        for style in TradingStyle:
            performance[style.value] = self.get_style_performance(style, days)
        
        # Calculate totals
        total_trades = sum(p["trades"] for p in performance.values())
        total_pnl = sum(p["total_pnl"] for p in performance.values())
        total_wins = sum(p["wins"] for p in performance.values())
        
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        # Get capital stats
        portfolio_stats = self.capital_allocator.get_portfolio_stats()
        
        return {
            "by_style": performance,
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "overall_win_rate": overall_win_rate,
            "total_capital": portfolio_stats["total_capital"],
            "expected_annual_return": portfolio_stats["expected_annual_return"],
            "3_year_projection": portfolio_stats["3_year_projection"],
            "period_days": days
        }
    
    def print_performance_report(self, days: int = 30):
        """Print formatted performance report"""
        perf = self.get_portfolio_performance(days)
        
        print("\n" + "="*100)
        print(f"MULTI-TIMEFRAME PERFORMANCE REPORT (Last {days} Days)")
        print("="*100)
        
        print(f"\nTotal Capital: Rs{perf['total_capital']:,.2f}")
        print(f"Expected Annual Return: {perf['expected_annual_return']:.1f}%")
        print(f"3-Year Projection: Rs{perf['3_year_projection']:,.2f}")
        
        print(f"\n{'='*100}")
        print(f"OVERALL PERFORMANCE")
        print(f"{'='*100}")
        print(f"Total Trades: {perf['total_trades']}")
        print(f"Total P&L: Rs{perf['total_pnl']:,.2f}")
        print(f"Overall Win Rate: {perf['overall_win_rate']:.1f}%")
        
        print(f"\n{'='*100}")
        print(f"PERFORMANCE BY STYLE")
        print(f"{'='*100}")
        
        for style_name, style_perf in perf['by_style'].items():
            config = TradingStylesConfig.ALLOCATIONS[TradingStyle[style_name.upper()]]
            
            print(f"\n[{style_name.upper()}] (Allocation: {config.allocation_percent:.0f}%, "
                  f"Expected Return: {config.expected_annual_return:.0f}%)")
            print(f"  Trades: {style_perf['trades']} | Wins: {style_perf['wins']} | Losses: {style_perf['losses']}")
            print(f"  Win Rate: {style_perf['win_rate']:.1f}%")
            print(f"  Total P&L: Rs{style_perf['total_pnl']:,.2f}")
            print(f"  Avg R-Multiple: {style_perf['avg_r']:.2f}R")
            print(f"  Best Trade: Rs{style_perf['best_trade']:,.2f}")
            print(f"  Worst Trade: Rs{style_perf['worst_trade']:,.2f}")
        
        print(f"\n{'='*100}")
        
        # Print allocation table
        print(f"\nCAPITAL ALLOCATION:")
        print(f"{'-'*100}")
        print(f"{'Style':<15} {'Allocation':<12} {'Expected Return':<18} {'Max Drawdown':<15} {'Volatility':<12}")
        print(f"{'-'*100}")
        
        for style in TradingStyle:
            config = TradingStylesConfig.ALLOCATIONS[style]
            print(f"{style.value.upper():<15} "
                  f"{config.allocation_percent:>6.1f}%     "
                  f"{config.expected_annual_return:>6.1f}%          "
                  f"{config.max_drawdown_percent:>6.1f}%        "
                  f"{config.volatility:<12}")
        
        print(f"{'-'*100}")
        print()
    
    def get_expected_vs_actual(self, days: int = 30) -> Dict:
        """Compare expected vs actual returns for each style"""
        comparison = {}
        
        for style in TradingStyle:
            perf = self.get_style_performance(style, days)
            config = TradingStylesConfig.ALLOCATIONS[style]
            style_capital = self.capital_allocator.get_style_capital(style)
            
            # Annualize actual return
            actual_pnl = perf['total_pnl']
            actual_return_period = (actual_pnl / style_capital.allocated_capital) * 100 if style_capital.allocated_capital > 0 else 0
            actual_return_annual = actual_return_period * (365 / days)
            
            comparison[style.value] = {
                "expected_annual": config.expected_annual_return,
                "actual_annual": actual_return_annual,
                "difference": actual_return_annual - config.expected_annual_return,
                "actual_pnl": actual_pnl,
                "trades": perf['trades']
            }
        
        return comparison
    
    def print_expected_vs_actual(self, days: int = 30):
        """Print expected vs actual returns"""
        comparison = self.get_expected_vs_actual(days)
        
        print("\n" + "="*100)
        print(f"EXPECTED VS ACTUAL RETURNS (Annualized from last {days} days)")
        print("="*100)
        print(f"{'Style':<15} {'Expected':<12} {'Actual':<12} {'Difference':<15} {'P&L':<15} {'Trades':<10}")
        print("-"*100)
        
        for style_name, comp in comparison.items():
            diff_color = "+" if comp['difference'] >= 0 else ""
            print(f"{style_name.upper():<15} "
                  f"{comp['expected_annual']:>6.1f}%     "
                  f"{comp['actual_annual']:>6.1f}%     "
                  f"{diff_color}{comp['difference']:>6.1f}%        "
                  f"Rs{comp['actual_pnl']:>8,.2f}    "
                  f"{comp['trades']:>3}")
        
        print("-"*100)
        print()


def run_performance_report(days: int = 30):
    """Run and display performance report"""
    from config import settings
    
    db = SessionLocal()
    monitor = PerformanceMonitor(db, settings.initial_capital)
    
    try:
        monitor.print_performance_report(days)
        monitor.print_expected_vs_actual(days)
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    
    print(f"\nGenerating performance report for last {days} days...")
    run_performance_report(days)
