"""Simple backtesting framework"""
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta
import logging

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class Backtester:
    """Simple backtesting engine
    
    Simulates trading with historical data including:
    - Brokerage charges
    - Slippage
    - Position sizing
    - Risk management
    """
    
    def __init__(
        self,
        initial_capital: float,
        max_risk_per_trade: float,
        brokerage_per_order: float = 20.0,
        slippage_percent: float = 0.1
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.brokerage_per_order = brokerage_per_order
        self.slippage_percent = slippage_percent
        
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = [initial_capital]
        self.dates: List[datetime] = []
    
    def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        symbol: str
    ) -> Dict:
        """Run backtest on historical data
        
        Args:
            strategy: Trading strategy
            data: Historical OHLCV data
            symbol: Symbol being tested
            
        Returns:
            Performance metrics dictionary
        """
        logger.info(f"Starting backtest for {symbol} with {len(data)} bars")
        
        position = None
        
        for i in range(100, len(data)):  # Start after enough data for indicators
            current_data = data.iloc[:i+1]
            current_bar = data.iloc[i]
            
            # Check for exit if in position
            if position:
                # Check stop loss
                if current_bar['low'] <= position['stop_loss']:
                    exit_price = position['stop_loss']
                    exit_price = self._apply_slippage(exit_price, 'sell')
                    
                    self._close_trade(
                        position,
                        exit_price,
                        current_bar['date'],
                        'STOP_LOSS'
                    )
                    position = None
                    continue
                
                # Check target
                if current_bar['high'] >= position['target']:
                    exit_price = position['target']
                    exit_price = self._apply_slippage(exit_price, 'sell')
                    
                    self._close_trade(
                        position,
                        exit_price,
                        current_bar['date'],
                        'TARGET'
                    )
                    position = None
                    continue
                
                # Check strategy exit
                should_exit = strategy.should_exit(position, current_bar['close'])
                if should_exit:
                    exit_price = self._apply_slippage(current_bar['close'], 'sell')
                    
                    self._close_trade(
                        position,
                        exit_price,
                        current_bar['date'],
                        'STRATEGY_EXIT'
                    )
                    position = None
                    continue
            
            # Look for entry if no position
            if not position:
                signal = strategy.analyze(current_data, symbol)
                
                if signal:
                    # Apply slippage to entry
                    entry_price = self._apply_slippage(signal.entry_price, 'buy')
                    
                    # Calculate position size
                    quantity = strategy.calculate_position_size(
                        entry_price,
                        signal.stop_loss,
                        self.max_risk_per_trade
                    )
                    
                    # Check if we have enough capital
                    required_capital = entry_price * quantity
                    if required_capital <= self.capital:
                        position = {
                            'symbol': symbol,
                            'entry_price': entry_price,
                            'stop_loss': signal.stop_loss,
                            'target': signal.target,
                            'quantity': quantity,
                            'entry_date': current_bar['date']
                        }
                        
                        logger.debug(
                            f"Trade opened: {symbol} @ ₹{entry_price:.2f}, "
                            f"Qty: {quantity}"
                        )
            
            # Record equity
            self.equity_curve.append(self.capital)
            self.dates.append(current_bar['date'])
        
        # Close any open position at end
        if position:
            self._close_trade(
                position,
                data.iloc[-1]['close'],
                data.iloc[-1]['date'],
                'END_OF_DATA'
            )
        
        # Calculate metrics
        metrics = self._calculate_metrics()
        
        logger.info(f"Backtest complete: {len(self.trades)} trades")
        
        return metrics
    
    def _close_trade(
        self,
        position: Dict,
        exit_price: float,
        exit_date: datetime,
        reason: str
    ) -> None:
        """Close a trade and record results"""
        entry_price = position['entry_price']
        quantity = position['quantity']
        
        # Calculate P&L
        gross_pnl = (exit_price - entry_price) * quantity
        
        # Calculate charges
        charges = (self.brokerage_per_order * 2) + \
                 (exit_price * quantity * 0.00025) + \
                 (0.18 * self.brokerage_per_order * 2)
        
        net_pnl = gross_pnl - charges
        
        # Update capital
        self.capital += net_pnl
        
        # Record trade
        trade = {
            'symbol': position['symbol'],
            'entry_date': position['entry_date'],
            'exit_date': exit_date,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'gross_pnl': gross_pnl,
            'charges': charges,
            'net_pnl': net_pnl,
            'reason': reason,
            'winner': net_pnl > 0
        }
        
        self.trades.append(trade)
    
    def _apply_slippage(self, price: float, direction: str) -> float:
        """Apply slippage to price"""
        slippage = price * (self.slippage_percent / 100)
        
        if direction == 'buy':
            return price + slippage
        else:
            return price - slippage
    
    def _calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {}
        
        trades_df = pd.DataFrame(self.trades)
        
        total_trades = len(self.trades)
        winners = trades_df[trades_df['winner'] == True]
        losers = trades_df[trades_df['winner'] == False]
        
        num_winners = len(winners)
        num_losers = len(losers)
        
        win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = winners['net_pnl'].sum() if num_winners > 0 else 0
        total_loss = abs(losers['net_pnl'].sum()) if num_losers > 0 else 0
        
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        avg_win = winners['net_pnl'].mean() if num_winners > 0 else 0
        avg_loss = losers['net_pnl'].mean() if num_losers > 0 else 0
        
        # Calculate drawdown
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # Calculate returns
        total_return = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        # Sharpe ratio (simplified)
        returns = trades_df['net_pnl'] / self.initial_capital
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if len(returns) > 1 else 0
        
        metrics = {
            'total_trades': total_trades,
            'winners': num_winners,
            'losers': num_losers,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': winners['net_pnl'].max() if num_winners > 0 else 0,
            'largest_loss': losers['net_pnl'].min() if num_losers > 0 else 0,
            'max_drawdown': max_drawdown,
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'final_capital': self.capital
        }
        
        return metrics
    
    def print_summary(self) -> None:
        """Print backtest summary"""
        metrics = self._calculate_metrics()
        
        print("\n" + "="*60)
        print("BACKTEST SUMMARY")
        print("="*60)
        print(f"Initial Capital: ₹{self.initial_capital:,.0f}")
        print(f"Final Capital:   ₹{metrics['final_capital']:,.0f}")
        print(f"Total Return:    {metrics['total_return']:.2f}%")
        print(f"\nTotal Trades:    {metrics['total_trades']}")
        print(f"Winners:         {metrics['winners']} ({metrics['win_rate']:.1f}%)")
        print(f"Losers:          {metrics['losers']}")
        print(f"\nProfit Factor:   {metrics['profit_factor']:.2f}")
        print(f"Sharpe Ratio:    {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown:    {metrics['max_drawdown']:.2f}%")
        print(f"\nTotal Profit:    ₹{metrics['total_profit']:,.2f}")
        print(f"Total Loss:      ₹{metrics['total_loss']:,.2f}")
        print(f"Avg Win:         ₹{metrics['avg_win']:,.2f}")
        print(f"Avg Loss:        ₹{metrics['avg_loss']:,.2f}")
        print(f"Largest Win:     ₹{metrics['largest_win']:,.2f}")
        print(f"Largest Loss:    ₹{metrics['largest_loss']:,.2f}")
        print("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    from strategies.intraday import IntradayStrategy
    
    # Load your historical data here
    # data = pd.read_csv('historical_data.csv')
    
    # Run backtest
    # backtester = Backtester(
    #     initial_capital=50000,
    #     max_risk_per_trade=400
    # )
    # 
    # strategy = IntradayStrategy()
    # metrics = backtester.run(strategy, data, "RELIANCE")
    # backtester.print_summary()
    
    pass
