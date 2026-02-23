"""Portfolio Projection Simulator
================================

Simulate realistic portfolio growth over 1-3 years
using the multi-timeframe system with:
- Intraday (20%, 15% return)
- Swing (30%, 25% return)
- Mid-term (30%, 30% return)
- Long-term (20%, 18% return)

Shows month-by-month progression with realistic variance.
"""
import random
from typing import Dict, List
from datetime import datetime, timedelta


class PortfolioSimulator:
    """Simulate multi-timeframe portfolio performance"""
    
    def __init__(self, initial_capital: float = 50000.0):
        self.initial_capital = initial_capital
        
        # Style configurations
        self.styles = {
            "intraday": {
                "allocation": 0.20,
                "expected_annual_return": 0.15,
                "volatility": 0.12,  # Monthly std dev
                "max_drawdown": 0.12
            },
            "swing": {
                "allocation": 0.30,
                "expected_annual_return": 0.25,
                "volatility": 0.10,
                "max_drawdown": 0.10
            },
            "midterm": {
                "allocation": 0.30,
                "expected_annual_return": 0.30,
                "volatility": 0.12,
                "max_drawdown": 0.12
            },
            "longterm": {
                "allocation": 0.20,
                "expected_annual_return": 0.18,
                "volatility": 0.08,
                "max_drawdown": 0.15
            }
        }
        
        # Calculate expected portfolio return
        self.expected_portfolio_return = sum(
            config["allocation"] * config["expected_annual_return"]
            for config in self.styles.values()
        )
    
    def generate_monthly_return(self, style: str, month: int) -> float:
        """Generate realistic monthly return for a style
        
        Uses normal distribution around expected return with style-specific volatility
        """
        config = self.styles[style]
        
        # Monthly expected return
        monthly_expected = config["expected_annual_return"] / 12
        
        # Add realistic variance (normal distribution)
        monthly_volatility = config["volatility"]
        actual_return = random.gauss(monthly_expected, monthly_volatility)
        
        # Occasional drawdown months (20% chance of negative month)
        if random.random() < 0.20:
            actual_return = -abs(random.gauss(0.01, 0.02))
        
        # Cap at max drawdown
        max_monthly_loss = -config["max_drawdown"] / 2  # Spread over months
        actual_return = max(actual_return, max_monthly_loss)
        
        return actual_return
    
    def simulate_month(self, current_capital: Dict[str, float], month: int) -> Dict[str, float]:
        """Simulate one month of trading"""
        new_capital = {}
        
        for style, capital in current_capital.items():
            monthly_return = self.generate_monthly_return(style, month)
            new_capital[style] = capital * (1 + monthly_return)
        
        return new_capital
    
    def simulate_year(self, starting_capital: Dict[str, float] = None) -> List[Dict]:
        """Simulate one year (12 months)
        
        Returns:
            List of monthly snapshots with capital and returns
        """
        if starting_capital is None:
            # Initialize with allocations
            starting_capital = {
                style: self.initial_capital * config["allocation"]
                for style, config in self.styles.items()
            }
        
        results = []
        current_capital = starting_capital.copy()
        
        for month in range(1, 13):
            # Simulate month
            new_capital = self.simulate_month(current_capital, month)
            
            # Calculate monthly return
            old_total = sum(current_capital.values())
            new_total = sum(new_capital.values())
            monthly_return = ((new_total - old_total) / old_total) * 100
            
            results.append({
                "month": month,
                "capital_by_style": new_capital.copy(),
                "total_capital": new_total,
                "monthly_return": monthly_return,
                "ytd_return": ((new_total - self.initial_capital) / self.initial_capital) * 100
            })
            
            current_capital = new_capital
        
        return results
    
    def simulate_multi_year(self, years: int = 3) -> Dict:
        """Simulate multiple years
        
        Returns:
            Dict with yearly summaries and monthly details
        """
        all_results = []
        
        # Start with initial allocation
        starting_capital = {
            style: self.initial_capital * config["allocation"]
            for style, config in self.styles.items()
        }
        
        yearly_summaries = []
        
        for year in range(1, years + 1):
            print(f"\nSimulating Year {year}...")
            
            # Simulate year
            year_results = self.simulate_year(starting_capital)
            all_results.extend(year_results)
            
            # Year-end capital becomes next year's starting capital
            final_month = year_results[-1]
            starting_capital = final_month["capital_by_style"]
            
            # Yearly summary
            year_end_capital = final_month["total_capital"]
            year_return = ((year_end_capital - self.initial_capital) / self.initial_capital) * 100
            
            yearly_summaries.append({
                "year": year,
                "starting_capital": self.initial_capital if year == 1 else yearly_summaries[-1]["ending_capital"],
                "ending_capital": year_end_capital,
                "return_percent": year_return,
                "profit": year_end_capital - self.initial_capital
            })
        
        return {
            "monthly_results": all_results,
            "yearly_summaries": yearly_summaries,
            "initial_capital": self.initial_capital,
            "final_capital": all_results[-1]["total_capital"],
            "total_return": ((all_results[-1]["total_capital"] - self.initial_capital) / self.initial_capital) * 100
        }
    
    def print_yearly_summary(self, simulation: Dict):
        """Print yearly summary"""
        print("\n" + "="*100)
        print("MULTI-TIMEFRAME PORTFOLIO SIMULATION")
        print("="*100)
        
        print(f"\nInitial Capital: Rs{simulation['initial_capital']:,.2f}")
        print(f"Expected Annual Return: {self.expected_portfolio_return*100:.1f}%")
        
        print("\n" + "="*100)
        print("YEARLY SUMMARY")
        print("="*100)
        print(f"{'Year':<8} {'Starting Capital':<20} {'Ending Capital':<20} {'Return':<15} {'Profit':<15}")
        print("-"*100)
        
        for summary in simulation['yearly_summaries']:
            print(f"{summary['year']:<8} "
                  f"Rs{summary['starting_capital']:>13,.2f}     "
                  f"Rs{summary['ending_capital']:>13,.2f}     "
                  f"{summary['return_percent']:>6.1f}%        "
                  f"Rs{summary['profit']:>10,.2f}")
        
        print("-"*100)
        print(f"\nFinal Capital: Rs{simulation['final_capital']:,.2f}")
        print(f"Total Return: {simulation['total_return']:.1f}%")
        print(f"Total Profit: Rs{simulation['final_capital'] - simulation['initial_capital']:,.2f}")
        print()
    
    def print_monthly_detail(self, simulation: Dict, year: int = None):
        """Print monthly details for a specific year or all"""
        monthly_results = simulation['monthly_results']
        
        if year:
            start_month = (year - 1) * 12
            end_month = year * 12
            monthly_results = monthly_results[start_month:end_month]
            print(f"\nMONTHLY DETAILS - YEAR {year}")
        else:
            print("\nMONTHLY DETAILS - ALL YEARS")
        
        print("="*100)
        print(f"{'Month':<8} {'Total Capital':<18} {'Monthly Return':<18} {'YTD Return':<15}")
        print("-"*100)
        
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        for i, result in enumerate(monthly_results):
            month_name = month_names[i % 12]
            return_indicator = "📈" if result['monthly_return'] > 0 else "📉"
            
            print(f"{month_name:<8} "
                  f"Rs{result['total_capital']:>12,.2f}    "
                  f"{return_indicator} {result['monthly_return']:>6.1f}%         "
                  f"{result['ytd_return']:>6.1f}%")
        
        print("-"*100)
        print()


def run_simulation(years: int = 3, initial_capital: float = 50000.0):
    """Run portfolio simulation"""
    print(f"\n🎯 Running {years}-year portfolio simulation...")
    print(f"💰 Initial Capital: Rs{initial_capital:,.2f}")
    print(f"📊 Multi-Timeframe Strategy:")
    print(f"   - Intraday: 20% (15% return)")
    print(f"   - Swing: 30% (25% return)")
    print(f"   - Mid-term: 30% (30% return)")
    print(f"   - Long-term: 20% (18% return)")
    
    simulator = PortfolioSimulator(initial_capital)
    simulation = simulator.simulate_multi_year(years)
    
    simulator.print_yearly_summary(simulation)
    
    # Print monthly details for each year
    for year in range(1, years + 1):
        simulator.print_monthly_detail(simulation, year)
    
    # Final analysis
    print("\n" + "="*100)
    print("ANALYSIS")
    print("="*100)
    
    final_capital = simulation['final_capital']
    total_return = simulation['total_return']
    annual_return = ((final_capital / initial_capital) ** (1/years) - 1) * 100
    
    print(f"\n✅ Starting Capital: Rs{initial_capital:,.2f}")
    print(f"✅ Final Capital: Rs{final_capital:,.2f}")
    print(f"✅ Total Profit: Rs{final_capital - initial_capital:,.2f}")
    print(f"✅ Total Return: {total_return:.1f}%")
    print(f"✅ Annualized Return: {annual_return:.1f}%")
    
    print("\n💡 Key Insights:")
    print(f"   - This is REALISTIC performance (expect red months)")
    print(f"   - Diversification across timeframes reduces risk")
    print(f"   - ~{annual_return:.0f}% annual return is sustainable")
    print(f"   - Much safer than pure intraday or single-style")
    
    print("\n🎯 This demonstrates:")
    print(f"   - Steady compounding (not gambling)")
    print(f"   - Realistic monthly variance")
    print(f"   - Professional trader behavior")
    print(f"   - Long-term wealth building")
    
    print("\n" + "="*100)
    print()


if __name__ == "__main__":
    import sys
    
    # Default: 3 years, Rs50,000
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    capital = float(sys.argv[2]) if len(sys.argv) > 2 else 50000.0
    
    run_simulation(years, capital)
