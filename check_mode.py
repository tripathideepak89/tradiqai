"""Quick script to check current trading mode"""
from config import settings

print("=== CONFIGURATION CHECK ===")
print(f"PAPER_TRADING = {settings.paper_trading}")
print(f"Mode: {'PAPER' if settings.paper_trading else 'LIVE'}")
print(f"Broker: {settings.broker}")
print(f"Initial Capital: ₹{settings.initial_capital:,.2f}")
print("=" * 30)
