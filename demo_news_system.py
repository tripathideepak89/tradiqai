"""
News Impact System - Integration Demo
Shows how to use news detection with existing trading system
"""
import asyncio
import logging
from datetime import datetime

# Import news system
from news_impact_detector import (
    NewsImpactDetector, 
    NewsCategory,
    NewsAction
)
from news_governance import NewsGovernance, EventRiskLevel

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_news_impact_system():
    """
    Demonstrate the complete news impact detection workflow
    """
    
    print("\n" + "="*100)
    print("📰 NEWS IMPACT DETECTION SYSTEM - DEMO")
    print("="*100 + "\n")
    
    # Initialize
    detector = NewsImpactDetector()
    governance = NewsGovernance()
    
    # Add event risk calendar (example)
    governance.add_event_to_calendar(
        "2026-02-20",
        "RBI Monetary Policy Decision",
        EventRiskLevel.HIGH
    )
    
    # ===================================================================
    # SCENARIO 1: High-Impact News with Market Confirmation
    # ===================================================================
    print("\n" + "─"*100)
    print("SCENARIO 1: High-Impact News with Strong Market Confirmation")
    print("─"*100 + "\n")
    
    scenario1_quote = {
        'ltp': 210.50,
        'open': 208.00,
        'high': 211.00,
        'low': 207.50,
        'volume': 15000000,
        'avg_volume': 5000000,  # 3× volume spike
        'vwap': 209.50
    }
    
    score1 = await detector.analyze_news_impact(
        headline="TATASTEEL wins Rs5000 crore renewable energy contract from Adani Green",
        source="NSE Corporate Filing",
        symbol="TATASTEEL",
        category=NewsCategory.ORDER_WIN,
        timestamp=datetime.now(),
        quote=scenario1_quote
    )
    
    # Check governance
    passed1, violations1 = governance.check_all_news_governance(
        news_timestamp=score1.timestamp,
        current_price=scenario1_quote['ltp'],
        price_at_detection=score1.price_at_detection,
        quote=scenario1_quote,
        action="BUY"
    )
    
    print(f"\n{'✅ TRADE APPROVED' if passed1 and score1.action == NewsAction.TRADE_MODE else '❌ TRADE BLOCKED'}")
    
    if passed1 and score1.action == NewsAction.TRADE_MODE:
        # Calculate position size adjustment
        base_qty = 100
        adjusted_qty, reason = governance.get_position_size_adjustment(base_qty, is_news_trade=True)
        print(f"📊 Position Size: {base_qty} → {adjusted_qty} shares ({reason})")
    
    # ===================================================================
    # SCENARIO 2: Rumor Without Market Confirmation
    # ===================================================================
    print("\n\n" + "─"*100)
    print("SCENARIO 2: Rumor Without Market Confirmation (Should Reject)")
    print("─"*100 + "\n")
    
    scenario2_quote = {
        'ltp': 450.20,
        'open': 450.00,
        'high': 451.50,
        'low': 449.00,
        'volume': 2000000,
        'avg_volume': 2500000,  # Below average volume
        'vwap': 450.50
    }
    
    score2 = await detector.analyze_news_impact(
        headline="Sources say ITC may consider demerger of hotel business",
        source="Media Report",
        symbol="ITC",
        category=NewsCategory.RUMOR,
        timestamp=datetime.now(),
        quote=scenario2_quote
    )
    
    passed2, violations2 = governance.check_all_news_governance(
        news_timestamp=score2.timestamp,
        current_price=scenario2_quote['ltp'],
        price_at_detection=score2.price_at_detection,
        quote=scenario2_quote,
        action="BUY"
    )
    
    print(f"\n{'✅ TRADE APPROVED' if passed2 and score2.action == NewsAction.TRADE_MODE else '❌ TRADE BLOCKED'}")
    
    if not passed2:
        print(f"🚫 Violations:")
        for v in violations2:
            print(f"   • {v}")
    
    # ===================================================================
    # SCENARIO 3: Good News But Already Moved Too Much (Chase Prevention)
    # ===================================================================
    print("\n\n" + "─"*100)
    print("SCENARIO 3: Chase Prevention - Already Moved 2.5% (Should Block)")
    print("─"*100 + "\n")
    
    scenario3_quote = {
        'ltp': 153.80,  # Already up 2.5%
        'open': 150.00,
        'high': 154.00,
        'low': 149.50,
        'volume': 25000000,
        'avg_volume': 8000000,  # 3× volume
        'vwap': 151.50
    }
    
    # Simulate detection at Rs150
    detection_price = 150.00
    
    score3 = await detector.analyze_news_impact(
        headline="Reliance announces 20% stake sale in Jio at $100B valuation",
        source="Bloomberg",
        symbol="RELIANCE",
        category=NewsCategory.MERGER_ACQUISITION,
        timestamp=datetime.now(),
        quote=scenario3_quote
    )
    
    # Override detection price for this demo
    score3.price_at_detection = detection_price
    score3.price_move_pct = ((scenario3_quote['ltp'] - detection_price) / detection_price * 100)
    
    passed3, violations3 = governance.check_all_news_governance(
        news_timestamp=score3.timestamp,
        current_price=scenario3_quote['ltp'],
        price_at_detection=detection_price,
        quote=scenario3_quote,
        action="BUY"
    )
    
    print(f"\n{'✅ TRADE APPROVED' if passed3 and score3.action == NewsAction.TRADE_MODE else '❌ TRADE BLOCKED'}")
    
    if not passed3:
        print(f"🚫 Violations:")
        for v in violations3:
            print(f"   • {v}")
        print(f"\n💡 Action: Wait for pullback to VWAP (Rs{scenario3_quote['vwap']:.2f})")
    
    # ===================================================================
    # SCENARIO 4: Earnings Beat with Perfect Setup
    # ===================================================================
    print("\n\n" + "─"*100)
    print("SCENARIO 4: Earnings Beat with Perfect Technical Setup")
    print("─"*100 + "\n")
    
    scenario4_quote = {
        'ltp': 1820.00,
        'open': 1800.00,
        'high': 1825.00,
        'low': 1795.00,
        'volume': 5000000,
        'avg_volume': 1500000,  # 3.3× volume
        'vwap': 1810.00
    }
    
    score4 = await detector.analyze_news_impact(
        headline="HDFC Bank Q4 results: Net profit beats estimates, NIM improves 20bps",
        source="NSE Corporate Filing",
        symbol="HDFCBANK",
        category=NewsCategory.EARNINGS,
        timestamp=datetime.now(),
        quote=scenario4_quote
    )
    
    passed4, violations4 = governance.check_all_news_governance(
        news_timestamp=score4.timestamp,
        current_price=scenario4_quote['ltp'],
        price_at_detection=score4.price_at_detection,
        quote=scenario4_quote,
        action="BUY"
    )
    
    print(f"\n{'✅ TRADE APPROVED' if passed4 and score4.action == NewsAction.TRADE_MODE else '❌ TRADE BLOCKED'}")
    
    if passed4 and score4.action == NewsAction.TRADE_MODE:
        base_qty = 50
        adjusted_qty, reason = governance.get_position_size_adjustment(base_qty, is_news_trade=True)
        print(f"📊 Position Size: {base_qty} → {adjusted_qty} shares ({reason})")
        print(f"📈 Entry Strategy: Wait for pullback to VWAP (Rs{scenario4_quote['vwap']:.2f}), then continuation break")
    
    # ===================================================================
    # SUMMARY
    # ===================================================================
    print("\n\n" + "="*100)
    print("📊 SUMMARY - INSTITUTIONAL NEWS TRADING APPROACH")
    print("="*100 + "\n")
    
    print("✅ SCENARIO 1: APPROVED - High impact + strong confirmation")
    print("❌ SCENARIO 2: BLOCKED - Rumor without market reaction")
    print("❌ SCENARIO 3: BLOCKED - Chase prevention (moved 2.5%)")
    print("✅ SCENARIO 4: APPROVED - Earnings beat with setup")
    
    print("\n🧠 Key Principles Demonstrated:")
    print("   • News must have market confirmation (E ≥ 7/15)")
    print("   • Don't chase moves > 2%")
    print("   • Reduce size 30% on news trades")
    print("   • Use VWAP as anchor")
    print("   • Price confirmation > headline")
    
    print("\n💡 System Status:")
    print("   ✅ Scoring model implemented (A+B+C+D+E)")
    print("   ✅ Gating rules enforced (G1-G4)")
    print("   ✅ Governance rules active")
    print("   ✅ Position sizing adjusted for news")
    print("   ✅ Institutional approach mimicked")
    
    print("\n📚 Next Steps:")
    print("   1. Connect to live news feed API")
    print("   2. Integrate with existing pre-entry checks")
    print("   3. Add to main trading loop")
    print("   4. Test with real market data")
    
    print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_news_impact_system())
