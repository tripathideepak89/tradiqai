"""Check broker positions for specific stocks"""
import asyncio
from brokers.groww import GrowwBroker
from config import settings

async def check_broker():
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    
    broker = GrowwBroker(broker_config)
    await broker.connect()
    
    positions = await broker.get_positions()
    
    print("\n" + "="*60)
    print("📈 POSITIONS IN BROKER ACCOUNT")
    print("="*60)
    
    symbols = ['HINDALCO', 'NTPC', 'COALINDIA']
    
    found = False
    if positions:
        for pos in positions:
            if pos.get('symbol') in symbols:
                found = True
                print(f"\n{pos.get('symbol')}:")
                print(f"  Quantity: {pos.get('quantity', 0)}")
                print(f"  Side: {pos.get('side', 'N/A')}")
                print(f"  Avg Price: Rs{pos.get('average_price', 0)}")
                print(f"  Current Price: Rs{pos.get('ltp', 0)}")
                pnl = pos.get('pnl', 0)
                print(f"  P&L: Rs{pnl:.2f}")
    
    if not found:
        print("\n❌ No positions found for these stocks in broker account")
    
    print("\n" + "="*60)

asyncio.run(check_broker())
