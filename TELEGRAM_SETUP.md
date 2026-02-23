# Setting Up Telegram Alerts

Telegram alerts are highly recommended for monitoring your trading system. Here's how to set them up:

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and send: `/newbot`
3. Follow the instructions:
   - Choose a name (e.g., "My Trading Bot")
   - Choose a username (must end in 'bot', e.g., "my_trading_bot")
4. BotFather will give you a **TOKEN** - save this!
   - Example: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

## Step 2: Get Your Chat ID

### Method 1: Using a Helper Bot (Easiest)

1. Search for **@userinfobot** in Telegram
2. Start a chat with it
3. It will immediately send you your **Chat ID**
   - Example: `123456789`

### Method 2: Using the API

1. Send a message to your bot (the one you just created)
2. Visit this URL (replace YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Look for `"chat":{"id":123456789}` in the response
4. That number is your Chat ID

## Step 3: Test Your Bot

Use this Python script to test:

```python
import asyncio
from telegram import Bot

async def test_telegram():
    bot_token = "YOUR_TOKEN_HERE"
    chat_id = "YOUR_CHAT_ID_HERE"
    
    bot = Bot(token=bot_token)
    
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🤖 Test message from TradiqAI!\n\nIf you see this, your Telegram setup is working! ✅"
        )
        print("✅ Message sent successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")

# Run test
asyncio.run(test_telegram())
```

Save as `test_telegram.py` and run:
```powershell
python test_telegram.py
```

## Step 4: Update .env File

Add your credentials to `.env`:

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
ENABLE_ALERTS=true
```

## Step 5: Verify in Trading System

Start the system and you should receive a startup message:

```powershell
python main.py
```

Expected message in Telegram:
```
🚀 TradiqAI System Started

Capital: ₹50,000
Mode: PAPER
Strategies: 1

Time: 2026-02-17 09:15:00 IST
```

## Message Types You'll Receive

### 1. System Events
- ℹ️ System startup/shutdown
- ⚠️ Warnings (risk limits approaching)
- ❌ Errors
- 🚨 Critical alerts (kill switch, daily loss limit)

### 2. Trade Alerts
- 📊 Trade entries (with details)
- ✅ Winning exits
- ❌ Losing exits

### 3. Daily Summary
Sent at market close:
```
📊 DAILY TRADING SUMMARY

Date: 2026-02-17

💰 P&L: ₹450.00
📈 Trades: 3
✅ Won: 2
❌ Lost: 1
📊 Win Rate: 66.7%
💹 Largest Win: ₹300.00
📉 Largest Loss: ₹-150.00
📊 Max Drawdown: 2.50%
```

### 4. Risk Warnings
```
⚠️ WARNING

Daily loss limit approaching: 85.0%

Current loss: ₹1,275.00
Limit: ₹1,500.00

Time: 2026-02-17 14:30:00 IST
```

## Troubleshooting

### Issue: "Bot was blocked by the user"

**Solution**: Make sure you've started a chat with your bot. Send it any message (like `/start`) before running the system.

### Issue: "Chat not found"

**Solution**: 
1. Verify your Chat ID is correct
2. Make sure you've sent at least one message to your bot
3. Don't use quotes around the Chat ID in .env

### Issue: "Wrong token"

**Solution**: 
1. Double-check the token from BotFather
2. Make sure there are no extra spaces
3. Token format: `NUMBER:LETTERS_AND_NUMBERS`

### Issue: Rate limiting

**Solution**: The system already has built-in rate limiting, but if you're testing:
1. Don't spam the bot
2. Wait a few seconds between messages
3. Telegram allows ~30 messages per second

## Advanced: Group Alerts

To send alerts to a group:

1. Create a Telegram group
2. Add your bot to the group
3. Make the bot an admin (optional, but recommended)
4. Use [@userinfobot](https://t.me/userinfobot) in the group to get the Group ID
   - Group IDs start with a minus sign (e.g., `-123456789`)
5. Use this Group ID as your `TELEGRAM_CHAT_ID`

## Privacy & Security

⚠️ **Important Security Notes:**

1. **Never share your bot token** - it's like a password
2. **Keep .env file private** - add it to .gitignore (already done)
3. **Bot can only send messages** - it can't see your Telegram messages
4. **Consider using a separate bot** for live vs paper trading

## Customizing Alerts

To customize which alerts you receive, edit `monitoring.py`:

```python
# Example: Only send critical alerts
if severity in ["ERROR", "CRITICAL"]:
    await self.send_alert(message, severity, urgent)
```

## Alternative: Slack Integration

If you prefer Slack, you can modify `monitoring.py` to use Slack webhooks instead of Telegram. The structure is similar.

---

**Tip**: Set up alerts even for paper trading! It's a great way to monitor your system without constantly checking logs.
