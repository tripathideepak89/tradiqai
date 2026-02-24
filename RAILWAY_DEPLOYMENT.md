# 🚂 Railway Deployment Guide for TradiqAI Dashboard

Complete guide to deploy your trading dashboard to Railway in under 10 minutes.

---

## 📋 Prerequisites

- ✅ GitHub account with your repository pushed
- ✅ Railway account (sign up at [railway.app](https://railway.app))
- ✅ Domain registered at Namecheap (tradiqai.com)
- ✅ Supabase project for authentication

---

## 🚀 Quick Deploy (5 Steps)

### **Step 1: Sign Up & Connect GitHub**

1. Go to [railway.app](https://railway.app) and sign up with GitHub
2. Grant Railway access to your `autotrade-ai` repository
3. You'll get $5 free credit monthly (enough for starter plan)

### **Step 2: Create New Project**

1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose **`autotrade-ai`** from the list
4. Railway will automatically:
   - Detect Python app
   - Read `railway.toml` configuration
   - Install dependencies from `requirements.txt`

### **Step 3: Add PostgreSQL & Redis**

In your Railway project:

1. Click **"New"** → **"Database"** → **"Add PostgreSQL"**
   - Railway automatically creates `DATABASE_URL` variable
   
2. Click **"New"** → **"Database"** → **"Add Redis"**
   - Railway automatically creates `REDIS_URL` variable

### **Step 4: Configure Environment Variables**

Click on your service → **"Variables"** tab → Add these:

```bash
# Application
ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Trading Configuration
INITIAL_CAPITAL=50000
MAX_DAILY_LOSS=1500
MAX_PER_TRADE_RISK=400
MAX_OPEN_TRADES=2
BROKER=zerodha

# Zerodha (get from https://kite.zerodha.com/connect/login)
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_USER_ID=your_user_id
ZERODHA_PASSWORD=your_password
ZERODHA_TOTP_SECRET=your_totp_secret

# Groww (optional)
GROWW_API_KEY=your_groww_token
GROWW_API_URL=https://api.groww.in/v1

# Supabase (from https://app.supabase.com)
SUPABASE_URL=https://lmpajbaylwrlqtcqmwoo.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# Telegram (optional alerts)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ENABLE_ALERTS=true

# Trading Settings
PAPER_TRADING=false
ENABLE_KILL_SWITCH=true
MARKET_OPEN_TIME=09:15
MARKET_CLOSE_TIME=15:30
```

**💡 Note:** `DATABASE_URL` and `REDIS_URL` are auto-created when you add databases.

### **Step 5: Connect Custom Domain**

1. In Railway, go to **"Settings"** → **"Networking"** → **"Custom Domain"**
2. Click **"Add Domain"** → Enter `tradiqai.com`
3. Railway will show DNS records to add:

Go to your **Namecheap DNS settings**:
```
Type: CNAME
Host: @
Value: <your-app>.up.railway.app
TTL: Automatic
```

```
Type: CNAME
Host: www
Value: <your-app>.up.railway.app
TTL: Automatic
```

4. Wait 5-10 minutes for DNS propagation
5. Railway auto-provisions SSL certificate (HTTPS)

---

## 🔧 GitHub Actions Auto-Deploy (Optional)

### Enable Automated Deployments

1. **Get Railway Token:**
   - Go to Railway Dashboard → Account Settings → Tokens
   - Create a new token → Copy it

2. **Add to GitHub Secrets:**
   - Go to your GitHub repo → Settings → Secrets and variables → Actions
   - Click **"New repository secret"**
   - Name: `RAILWAY_TOKEN`
   - Value: (paste your Railway token)

3. **Add Other Secrets (if needed):**
   - `DATABASE_URL`
   - `REDIS_URL`
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`

4. **Push to Deploy:**
   ```bash
   git add .
   git commit -m "Deploy to Railway"
   git push origin main
   ```

GitHub Actions will automatically:
- ✅ Run tests
- ✅ Install dependencies
- ✅ Deploy to Railway
- ✅ Healthcheck the deployment

---

## 📊 Verify Deployment

### Check 1: Railway Deployment Logs
```
Railway Dashboard → Your Service → Deployments → View Logs
```
Look for:
```
✅ Starting TradiqAI Dashboard in production mode...
✅ Application startup complete
✅ Uvicorn running on 0.0.0.0:XXXX
```

### Check 2: Health Endpoint
```bash
curl https://tradiqai.com/health
```
Should return:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-24T...",
  "version": "1.0.0"
}
```

### Check 3: Access Dashboard
```
https://tradiqai.com
```
Should show login page.

### Check 4: Database Connection
```bash
# In Railway service terminal
python -c "from config import settings; print('DB connected!' if settings.database_url else 'No DB')"
```

---

## 🔐 Update Supabase URLs

After deployment, update your Supabase project:

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project → **Authentication** → **URL Configuration**
3. Update:
   - **Site URL:** `https://tradiqai.com`
   - **Redirect URLs:** Add these:
     ```
     https://tradiqai.com/**
     https://www.tradiqai.com/**
     ```
4. Save changes

---

## 💰 Pricing

| Plan | Price | Includes |
|------|-------|----------|
| **Hobby** | Free | $5 credit/month, 500 hours execution |
| **Developer** | $5/month | $5 credit + unlimited execution |
| **Team** | $20/month | $20 credit + priority support |

**Your estimated cost:** ~$5-10/month
- Dashboard service: $5
- PostgreSQL: Included
- Redis: Included
- Bandwidth: Usually included in free tier

---

## 🛠️ Troubleshooting

### Issue: "Application failed to start"
**Check:**
```bash
# In Railway logs, look for:
ModuleNotFoundError: No module named 'xxx'
```
**Fix:** Add missing package to `requirements.txt` and redeploy.

### Issue: "Database connection failed"
**Check:**
```bash
echo $DATABASE_URL  # Should show postgres://...
```
**Fix:** Ensure PostgreSQL database is added to project.

### Issue: "Redis connection timeout"
**Fix:** Add Redis database in Railway project.

### Issue: Port binding error
**Fix:** Railway automatically sets `$PORT` variable. Ensure your app uses:
```python
port = int(os.getenv("PORT", 8080))
```

### Issue: Domain not working
**Check DNS:**
```bash
nslookup tradiqai.com
```
Should point to Railway's servers.

**Fix:** Wait 10-30 minutes for DNS propagation.

---

## 📈 Monitoring & Logs

### Real-time Logs
```
Railway Dashboard → Service → Deployments → View Logs
```

### Metrics Dashboard
```
Railway Dashboard → Service → Metrics
```
Shows:
- CPU usage
- Memory usage
- Request rate
- Response times

### Set Up Alerts
1. Go to **Settings** → **Observability**
2. Configure alerts for:
   - High memory usage (>80%)
   - High CPU usage (>90%)
   - Deployment failures

---

## 🔄 Update Deployment

### Method 1: Git Push (with GitHub Actions)
```bash
git add .
git commit -m "Update dashboard"
git push origin main
# Auto-deploys via GitHub Actions
```

### Method 2: Manual Railway Deploy
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Deploy
railway up
```

### Method 3: Railway Dashboard
1. Go to Deployments
2. Click **"Deploy"** button
3. Select branch to deploy

---

## 📚 Next Steps

- [ ] Set up monitoring alerts
- [ ] Configure backup strategy for database
- [ ] Set up staging environment
- [ ] Add Telegram alerts for trades
- [ ] Configure rate limiting
- [ ] Set up log aggregation

---

## 🆘 Support

- **Railway Docs:** https://docs.railway.app
- **Railway Discord:** https://discord.gg/railway
- **Supabase Support:** https://supabase.com/support
- **TradiqAI Issues:** Open issue in your GitHub repo

---

## ✅ Deployment Checklist

- [ ] Railway account created
- [ ] GitHub repo connected
- [ ] PostgreSQL database added
- [ ] Redis database added
- [ ] Environment variables configured
- [ ] Custom domain connected (tradiqai.com)
- [ ] SSL certificate active
- [ ] Supabase URLs updated
- [ ] Health check passing
- [ ] Dashboard accessible at https://tradiqai.com
- [ ] GitHub Actions configured (optional)
- [ ] Monitoring alerts set up

🎉 **Your trading dashboard is now live in production!**
