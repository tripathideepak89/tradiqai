"""Test margins API"""
import asyncio
import logging
from brokers.groww import GrowwBroker
from config import settings

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def test():
    broker = GrowwBroker({
        'api_key': settings.groww_api_key,
        'api_secret': settings.groww_api_secret,
        'api_url': settings.groww_api_url
    })
    
    print("Connecting...")
    connected = await broker.connect()
    print(f"Connected: {connected}")
    
    print("\nGetting margins...")
    margins = await broker.get_margins()
    
    print("\n=== Margins Result ===")
    for key, value in margins.items():
        print(f"{key}: {value}")
    
    await broker.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
