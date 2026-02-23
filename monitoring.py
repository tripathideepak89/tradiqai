"""Monitoring and alerting system"""
import logging
from typing import Dict, Optional
import asyncio
from datetime import datetime, date, time
from telegram import Bot
from telegram.error import TelegramError
import pytz

from config import settings
from database import redis_client

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class MonitoringService:
    """Monitoring service with alerts and health checks"""
    
    def __init__(self):
        self.telegram_bot: Optional[Bot] = None
        self.telegram_chat_id = settings.telegram_chat_id
        
        if settings.enable_alerts and settings.telegram_bot_token:
            self.telegram_bot = Bot(token=settings.telegram_bot_token)
        
        self.kill_switch_key = "monitoring:kill_switch"
        self.health_check_key = "monitoring:health_check"
    
    async def send_alert(
        self,
        message: str,
        severity: str = "INFO",
        urgent: bool = False
    ) -> bool:
        """Send alert via Telegram
        
        Args:
            message: Alert message
            severity: INFO, WARNING, ERROR, CRITICAL
            urgent: If True, adds indicators to message
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not self.telegram_bot or not self.telegram_chat_id:
                logger.warning("Telegram not configured, skipping alert")
                return False
            
            # Format message with severity
            icon_map = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "CRITICAL": "🚨"
            }
            
            icon = icon_map.get(severity, "ℹ️")
            
            if urgent:
                formatted_message = f"🔴 URGENT {icon}\n\n{message}"
            else:
                formatted_message = f"{icon} {severity}\n\n{message}"
            
            formatted_message += f"\n\nTime: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST"
            
            await self.telegram_bot.send_message(
                chat_id=self.telegram_chat_id,
                text=formatted_message
            )
            
            logger.info(f"Alert sent: {severity} - {message}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    async def send_daily_summary(self, metrics: Dict) -> bool:
        """Send daily trading summary"""
        try:
            message = "[SUMMARY] DAILY TRADING SUMMARY\n\n"
            message += f"Date: {date.today().strftime('%Y-%m-%d')}\n\n"
            message += f"P&L: Rs{metrics.get('net_pnl', 0):.2f}\n"
            message += f"Trades: {metrics.get('trades_taken', 0)}\n"
            message += f"Won: {metrics.get('trades_won', 0)}\n"
            message += f"Lost: {metrics.get('trades_lost', 0)}\n"
            message += f"Win Rate: {metrics.get('win_rate', 0):.1f}%\n"
            message += f"Largest Win: Rs{metrics.get('largest_win', 0):.2f}\n"
            message += f"Largest Loss: Rs{metrics.get('largest_loss', 0):.2f}\n"
            message += f"Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%\n"
            
            return await self.send_alert(message, severity="INFO")
            
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False
    
    async def send_trade_alert(self, trade_info: Dict) -> bool:
        """Send alert for trade entry/exit"""
        try:
            if trade_info.get('action') == 'ENTRY':
                message = f"[ENTRY] TRADE ENTRY\n\n"
                message += f"Symbol: {trade_info['symbol']}\n"
                message += f"Direction: {trade_info['direction']}\n"
                message += f"Entry: Rs{trade_info['entry_price']:.2f}\n"
                message += f"Stop Loss: Rs{trade_info['stop_loss']:.2f}\n"
                message += f"Target: Rs{trade_info['target']:.2f}\n"
                message += f"Quantity: {trade_info['quantity']}\n"
                message += f"Risk: Rs{trade_info['risk']:.2f}\n"
                message += f"Strategy: {trade_info['strategy']}"
                
            else:  # EXIT
                pnl = trade_info.get('pnl', 0)
                icon = "[WIN]" if pnl > 0 else "[LOSS]"
                
                message = f"{icon} TRADE EXIT\n\n"
                message += f"Symbol: {trade_info['symbol']}\n"
                message += f"Entry: Rs{trade_info['entry_price']:.2f}\n"
                message += f"Exit: Rs{trade_info['exit_price']:.2f}\n"
                message += f"P&L: Rs{pnl:.2f}\n"
                message += f"Reason: {trade_info.get('reason', 'N/A')}\n"
                message += f"Holding: {trade_info.get('holding_time', 'N/A')}"
            
            return await self.send_alert(message, severity="INFO")
            
        except Exception as e:
            logger.error(f"Failed to send trade alert: {e}")
            return False
    
    def activate_kill_switch(self, reason: str = "Manual activation") -> bool:
        """Activate kill switch - stops all trading immediately"""
        try:
            redis_client.set(
                self.kill_switch_key,
                f"{reason}|{datetime.now().isoformat()}",
                ex=86400  # Expire after 24 hours
            )
            
            logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
            
            # Send urgent alert
            asyncio.create_task(
                self.send_alert(
                    f"🚨 KILL SWITCH ACTIVATED\n\nReason: {reason}",
                    severity="CRITICAL",
                    urgent=True
                )
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to activate kill switch: {e}")
            return False
    
    def deactivate_kill_switch(self) -> bool:
        """Deactivate kill switch"""
        try:
            redis_client.delete(self.kill_switch_key)
            logger.info("Kill switch deactivated")
            
            asyncio.create_task(
                self.send_alert(
                    "✅ Kill switch deactivated - Trading can resume",
                    severity="INFO"
                )
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate kill switch: {e}")
            return False
    
    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active"""
        try:
            return redis_client.exists(self.kill_switch_key) > 0
        except Exception as e:
            logger.error(f"Failed to check kill switch: {e}")
            return True  # Fail safe - assume active on error
    
    def get_kill_switch_reason(self) -> Optional[str]:
        """Get kill switch activation reason"""
        try:
            data = redis_client.get(self.kill_switch_key)
            if data:
                parts = data.split('|')
                return parts[0] if parts else None
            return None
        except Exception as e:
            logger.error(f"Failed to get kill switch reason: {e}")
            return None
    
    async def health_check(self) -> Dict[str, bool]:
        """Perform system health check
        
        Returns:
            Dictionary with health status of various components
        """
        health = {
            "database": False,
            "redis": False,
            "broker": False,
            "market_hours": False,
            "kill_switch": False
        }
        
        try:
            # Database check
            from database import engine
            with engine.connect() as conn:
                conn.execute("SELECT 1")
                health["database"] = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
        
        try:
            # Redis check
            redis_client.ping()
            health["redis"] = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        try:
            # Market hours check
            health["market_hours"] = self.is_market_open()
        except Exception as e:
            logger.error(f"Market hours check failed: {e}")
        
        try:
            # Kill switch check
            health["kill_switch"] = not self.is_kill_switch_active()
        except Exception as e:
            logger.error(f"Kill switch check failed: {e}")
        
        # Store health check result
        try:
            redis_client.set(
                self.health_check_key,
                f"{'healthy' if all(health.values()) else 'unhealthy'}|{datetime.now().isoformat()}",
                ex=300  # 5 minutes
            )
        except:
            pass
        
        return health
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        try:
            now = datetime.now(IST)
            current_time = now.time()
            current_date = now.date()
            
            # Parse market hours
            market_open = time.fromisoformat(settings.market_open_time)
            market_close = time.fromisoformat(settings.market_close_time)
            
            # Check if weekday (Monday = 0, Sunday = 6)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
            
            # Check time
            if market_open <= current_time <= market_close:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check market hours: {e}")
            return False
    
    def is_trading_day(self, check_date: date = None) -> bool:
        """Check if given date is a trading day
        
        Note: This is a basic implementation. You should integrate with
        a holiday calendar API for accurate results.
        """
        if check_date is None:
            check_date = date.today()
        
        # Check if weekend
        weekday = check_date.weekday()
        if weekday >= 5:  # Saturday or Sunday
            return False
        
        # TODO: Check against NSE holiday calendar
        # You should maintain a list of market holidays
        
        return True
    
    async def start_monitoring(self) -> None:
        """Start continuous monitoring"""
        logger.info("Starting monitoring service...")
        
        while True:
            try:
                # Health check every 5 minutes
                health = await self.health_check()
                
                # Alert if any component is unhealthy
                unhealthy = [k for k, v in health.items() if not v]
                if unhealthy:
                    await self.send_alert(
                        f"⚠️ Unhealthy components: {', '.join(unhealthy)}",
                        severity="WARNING"
                    )
                
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)
