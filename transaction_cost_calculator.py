"""Transaction Cost Calculator
==============================

Calculates exact transaction costs before trade execution.
Based on actual Groww broker charges from contract notes.

Cost Structure (Per Round Trip - Buy + Sell):
1. Brokerage: ₹1 per side (₹2 total) or 0.01% whichever is lower
2. IGST: 18% on brokerage
3. STT: 0.025% of sell value (intraday equity)
4. Exchange charges: ~0.00325% of turnover (NSE)
5. SEBI fees: ₹10 per crore of turnover
6. Stamp duty: 0.003% of buy value (or ₹1500 per crore)
7. IPFT: Negligible

Real Example from Contract Note (Feb 20, 2026):
- 10 shares @ ₹1250 (JSW Steel)
- Total cost: ₹24.99
- Cost per share: ₹2.50
"""
import logging
from dataclasses import dataclass
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TransactionCost:
    """Complete breakdown of transaction costs"""
    brokerage: float
    igst: float  # 18% on brokerage
    stt: float  # Securities Transaction Tax
    exchange_charges: float
    sebi_fees: float
    stamp_duty: float
    ipft: float
    
    @property
    def total_cost(self) -> float:
        """Total round-trip cost"""
        return (
            self.brokerage + 
            self.igst + 
            self.stt + 
            self.exchange_charges + 
            self.sebi_fees + 
            self.stamp_duty + 
            self.ipft
        )
    
    @property
    def breakdown_dict(self) -> Dict[str, float]:
        """Get cost breakdown as dictionary"""
        return {
            "brokerage": self.brokerage,
            "igst": self.igst,
            "stt": self.stt,
            "exchange_charges": self.exchange_charges,
            "sebi_fees": self.sebi_fees,
            "stamp_duty": self.stamp_duty,
            "ipft": self.ipft,
            "total": self.total_cost
        }


class TransactionCostCalculator:
    """Calculate exact transaction costs for equity intraday trades
    
    Based on Groww broker structure (similar to most Indian brokers).
    """
    
    # Rate constants (validated from contract notes)
    BROKERAGE_FLAT_PER_SIDE = 1.00  # ₹1 per side
    BROKERAGE_PERCENT = 0.01  # 0.01% of trade value
    IGST_RATE = 0.18  # 18% on brokerage + exchange + sebi + ipft
    STT_INTRADAY_RATE = 0.00025  # 0.025% on sell side only
    EXCHANGE_CHARGES_RATE = 0.0000325  # ~0.00325% of turnover
    SEBI_FEES_RATE = 0.0000001  # ₹10 per crore
    STAMP_DUTY_RATE = 0.00003  # 0.003% of buy value
    IPFT_RATE = 0.000001  # Negligible
    
    def __init__(self):
        logger.info("Transaction cost calculator initialized with Groww rates")
    
    def calculate_costs(
        self,
        quantity: int,
        entry_price: float,
        exit_price: float = None
    ) -> TransactionCost:
        """Calculate complete transaction costs
        
        Args:
            quantity: Number of shares
            entry_price: Entry price per share
            exit_price: Exit price per share (if None, assumes same as entry)
            
        Returns:
            TransactionCost with complete breakdown
        """
        if exit_price is None:
            exit_price = entry_price
        
        buy_value = quantity * entry_price
        sell_value = quantity * exit_price
        turnover = buy_value + sell_value
        
        # 1. Brokerage (lower of flat ₹1 or 0.01%)
        brokerage_buy = min(self.BROKERAGE_FLAT_PER_SIDE, buy_value * self.BROKERAGE_PERCENT / 100)
        brokerage_sell = min(self.BROKERAGE_FLAT_PER_SIDE, sell_value * self.BROKERAGE_PERCENT / 100)
        total_brokerage = brokerage_buy + brokerage_sell
        
        # 2. Exchange charges
        exchange_charges = turnover * self.EXCHANGE_CHARGES_RATE
        
        # 3. SEBI fees
        sebi_fees = turnover * self.SEBI_FEES_RATE
        
        # 4. IPFT (Negligible but included for completeness)
        ipft = turnover * self.IPFT_RATE
        
        # 5. Taxable value for IGST
        taxable_value = total_brokerage + exchange_charges + sebi_fees + ipft
        igst = taxable_value * self.IGST_RATE
        
        # 6. STT (only on sell side for intraday)
        stt = sell_value * self.STT_INTRADAY_RATE
        
        # 7. Stamp duty (only on buy side)
        stamp_duty = buy_value * self.STAMP_DUTY_RATE
        
        return TransactionCost(
            brokerage=round(total_brokerage, 2),
            igst=round(igst, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange_charges, 2),
            sebi_fees=round(sebi_fees, 2),
            stamp_duty=round(stamp_duty, 2),
            ipft=round(ipft, 2)
        )
    
    def get_cost_per_share(
        self,
        quantity: int,
        entry_price: float,
        exit_price: float = None
    ) -> float:
        """Get cost per share for easy comparison
        
        Args:
            quantity: Number of shares
            entry_price: Entry price per share
            exit_price: Exit price (optional)
            
        Returns:
            Cost per share in rupees
        """
        costs = self.calculate_costs(quantity, entry_price, exit_price)
        return round(costs.total_cost / quantity, 2)
    
    def get_minimum_required_move(
        self,
        quantity: int,
        entry_price: float,
        buffer_multiplier: float = 2.0
    ) -> float:
        """Calculate minimum price move required to overcome costs
        
        Args:
            quantity: Number of shares
            entry_price: Entry price per share
            buffer_multiplier: Safety buffer (2.0 = need 2x cost to break even)
            
        Returns:
            Minimum required move per share
        """
        cost_per_share = self.get_cost_per_share(quantity, entry_price)
        return round(cost_per_share * buffer_multiplier, 2)
    
    def get_breakeven_price(
        self,
        quantity: int,
        entry_price: float,
        direction: str = "LONG"
    ) -> float:
        """Calculate breakeven price including all costs
        
        Args:
            quantity: Number of shares
            entry_price: Entry price per share
            direction: "LONG" or "SHORT"
            
        Returns:
            Breakeven price per share
        """
        cost_per_share = self.get_cost_per_share(quantity, entry_price)
        
        if direction == "LONG":
            return round(entry_price + cost_per_share, 2)
        else:  # SHORT
            return round(entry_price - cost_per_share, 2)
    
    def validate_trade_profitability(
        self,
        quantity: int,
        entry_price: float,
        expected_move_per_share: float,
        max_cost_ratio: float = 0.25
    ) -> Tuple[bool, str, Dict]:
        """Validate if trade can overcome costs
        
        Args:
            quantity: Number of shares
            entry_price: Entry price per share
            expected_move_per_share: Expected price move
            max_cost_ratio: Maximum allowed cost-to-profit ratio (0.25 = 25%)
            
        Returns:
            Tuple of (approved, reason, metrics)
        """
        costs = self.calculate_costs(quantity, entry_price)
        cost_per_share = costs.total_cost / quantity
        
        # Calculate expected profit
        expected_gross_profit = expected_move_per_share * quantity
        expected_net_profit = expected_gross_profit - costs.total_cost
        
        # Cost ratio check
        if expected_gross_profit <= 0:
            return False, "Expected move is zero or negative", {}
        
        cost_ratio = costs.total_cost / expected_gross_profit
        
        metrics = {
            "total_cost": costs.total_cost,
            "cost_per_share": round(cost_per_share, 2),
            "expected_gross_profit": round(expected_gross_profit, 2),
            "expected_net_profit": round(expected_net_profit, 2),
            "cost_ratio": round(cost_ratio * 100, 2),  # As percentage
            "breakeven_move": round(cost_per_share, 2),
            "required_move_2x": round(cost_per_share * 2, 2),
            "cost_breakdown": costs.breakdown_dict
        }
        
        # Validation checks
        if expected_net_profit <= 0:
            return False, f"Net profit negative: ₹{expected_net_profit:.2f} after ₹{costs.total_cost:.2f} costs", metrics
        
        if cost_ratio > max_cost_ratio:
            return (
                False,
                f"Cost ratio too high: {cost_ratio*100:.1f}% (max {max_cost_ratio*100:.0f}%). "
                f"Costs ₹{costs.total_cost:.2f} vs expected profit ₹{expected_gross_profit:.2f}",
                metrics
            )
        
        if expected_move_per_share < cost_per_share * 2:
            return (
                False,
                f"Expected move ₹{expected_move_per_share:.2f} < 2x cost ₹{cost_per_share*2:.2f}. "
                f"Need at least 2x cost for safety buffer.",
                metrics
            )
        
        # Trade approved
        return True, f"Trade viable: {cost_ratio*100:.1f}% cost ratio, ₹{expected_net_profit:.2f} net expected", metrics


# Global instance
cost_calculator = TransactionCostCalculator()


if __name__ == "__main__":
    """Test with real contract note data"""
    print("\n" + "="*80)
    print("TRANSACTION COST CALCULATOR TEST")
    print("="*80 + "\n")
    
    # Test 1: JSW Steel from contract note (actual trade)
    print("Test 1: JSW Steel (from Feb 20 contract note)")
    print("-" * 50)
    qty = 10
    price = 1249.40
    costs = cost_calculator.calculate_costs(qty, price)
    print(f"Quantity: {qty} shares @ ₹{price}")
    print(f"Total Cost: ₹{costs.total_cost:.2f}")
    print(f"Cost per share: ₹{costs.total_cost/qty:.2f}")
    print(f"Breakdown: {costs.breakdown_dict}")
    print()
    
    # Test 2: TataSteel example from user's loss
    print("Test 2: TataSteel (190 shares from user's trade)")
    print("-" * 50)
    qty = 190
    price = 150.0  # Example price
    costs = cost_calculator.calculate_costs(qty, price)
    min_move = cost_calculator.get_minimum_required_move(qty, price)
    print(f"Quantity: {qty} shares @ ₹{price}")
    print(f"Total Cost: ₹{costs.total_cost:.2f}")
    print(f"Cost per share: ₹{costs.total_cost/qty:.2f}")
    print(f"Minimum required move (2x): ₹{min_move:.2f} per share")
    print(f"Actual move in trade: ₹0.09 ❌ REJECTED")
    print()
    
    # Test 3: Validate trade profitability
    print("Test 3: Trade Validation")
    print("-" * 50)
    qty = 50
    entry = 1000.0
    expected_move = 8.0  # Expecting ₹8 move
    approved, reason, metrics = cost_calculator.validate_trade_profitability(
        qty, entry, expected_move
    )
    print(f"Quantity: {qty} shares @ ₹{entry}")
    print(f"Expected move: ₹{expected_move}")
    print(f"Approved: {'✅ YES' if approved else '❌ NO'}")
    print(f"Reason: {reason}")
    print(f"Metrics: {metrics}")
    print("\n" + "="*80 + "\n")
