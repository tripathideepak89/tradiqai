"""Test IST logging"""
import logging
import sys
from datetime import datetime
from utils import now_ist

# Custom formatter with IST timezone
class ISTFormatter(logging.Formatter):
    """Logging formatter that displays timestamps in IST"""
    def formatTime(self, record, datefmt=None):
        dt = now_ist()
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S IST')

# Setup logging
ist_formatter = ISTFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ist_formatter)

logging.basicConfig(level=logging.INFO, handlers=[console_handler])
logger = logging.getLogger(__name__)

# Test logs
print("\n=== TIMESTAMP COMPARISON ===")
print(f"System Local Time (CET): {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Indian Standard Time: {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}")
print(f"Time difference: IST = CET + 5:30 hours")
print("\n=== SAMPLE LOGS WITH IST TIMESTAMPS ===")

logger.info("Trading bot initialized")
logger.info("Broker connected successfully")
logger.info("Market status: OPEN (9:15 AM - 3:30 PM IST)")
logger.info("Scanning stocks for trading signals...")
logger.warning("All logs now display IST timestamps for consistency")
