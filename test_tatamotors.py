"""Test Tata Motors symbol variations"""
import asyncio
from brokers.groww import GrowwBroker
from config import settings

async def test_symbols():
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    broker = GrowwBroker(broker_config)
    
    symbols_to_test = [
        "TATAMOTORS",
        "TATAMOTORS-EQ", 
        "TATAMOTOR",
        "TATAMTR"
    ]
    
    print("Testing Tata Motors symbols:")
    for symbol in symbols_to_test:
        try:
            quote = await broker.get_quote(symbol)
            print(f"✓ {symbol} - WORKS (Price: ₹{quote.last_price})")
        except Exception as e:
            print(f"✗ {symbol} - FAILED: {str(e)[:80]}")

if __name__ == "__main__":
    asyncio.run(test_symbols())
