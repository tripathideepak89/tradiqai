# Deploy TradIQ AI Dashboard to Render

**Quick Deploy Time: 5-10 minutes**

Render.com provides simpler Python deployment than Railway with better version control and built-in Python 3.11 support.

## Why Render vs Railway?

✅ **Better Python 3.11 support** - Native buildpack, no Nixpacks complications  
✅ **Simpler configuration** - One `render.yaml` file vs multiple config files  
✅ **Infrastructure as Code** - Blueprint deploys web service + databases together  
✅ **Lower latency for India** - Singapore region available  
❌ **Slightly more expensive** - $24/month total (web $7 + postgres $7 + redis $10)  

## Pricing Breakdown

| Service | Plan | Cost | Specs |
|---------|------|------|-------|
| Web Service | Starter | $7/month | 512MB RAM, always on |
| PostgreSQL | Starter | $7/month | 256MB RAM, 1GB storage |
| Redis | Starter | $10/month | 25MB RAM, 25 connections |
| **Total** | | **$24/month** | |

**Free Tier Note:** Change `plan: starter` to `plan: free` in render.yaml for free hosting, but:
- Web service sleeps after 15 min inactivity
- No custom domain on free tier
- PostgreSQL not included (use your Supabase instead)

---

## 🚀 Quick Deploy (5 Steps)

### 1. Push to GitHub (if not done)

```bash
git add render.yaml RENDER_DEPLOYMENT.md
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Sign Up for Render

1. Go to https://render.com
2. Click **"Get Started for Free"**
3. Sign up with **GitHub** (easiest - auto-connects repo)
4. Authorize Render to access your GitHub account

### 3. Create Blueprint Instance

1. From Render Dashboard, click **"New +"** → **"Blueprint"**
2. **Connect Repository:**
   - Select `tripathideepak89/tradiqai` repository
   - Click **"Connect"**
3. **Blueprint Detection:**
   - Render will detect `render.yaml` automatically
   - Review the services to be created:
     - ✅ Web Service: `tradiqai-dashboard`
     - ✅ PostgreSQL: `tradiqai-postgres`
     - ✅ Redis: `tradiqai-redis`
4. **Name your blueprint:** `TradIQ AI Production`
5. Click **"Apply"**

**Wait 3-5 minutes** - Render creates all services and starts first deploy.

### 4. Set Secret Environment Variables

The `render.yaml` file includes most env vars, but secrets must be set manually:

1. **Go to Web Service:**
   - Dashboard → `tradiqai-dashboard` → **Environment** tab

2. **Add Secret Variables:**

```bash
# Groww API Credentials
GROWW_API_KEY = eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjE3NzE5Nzk0MDAsImlhdCI6MTc3MTkwMzY3MSwibmJmIjoxNzcxOTAzNjcxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIyYmJkNThmNS1lNTg2LTRmZDMtOGZmNi1iMDExZGEwZWRjNjZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2JhYTdjM2EtOWIyMy00MmM4LTlkMmUtMjRlNWMxM2VlZTU3XCIsXCJkZXZpY2VJZFwiOlwiZjM3NjJhYWMtM2JkZC01MjJjLWJhZTItZTkzNThmMDNhMThkXCIsXCJzZXNzaW9uSWRcIjpcIjU5ZDQ0YjcxLTNkMmEtNDEyNS1hMTBhLWVlODIwMDhlODQ3ZVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYkFiejlWRmU0U0JzTUVab0RoSEVuV3hSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcIm9yZGVyLWJhc2ljLGxpdmVfZGF0YS1iYXNpYyxub25fdHJhZGluZy1iYXNpYyxvcmRlcl9yZWFkX29ubHktYmFzaWNcIixcInNvdXJjZUlwQWRkcmVzc1wiOlwiOTUuMTkzLjE0OC4yNiwxMDQuMjMuMjIzLjI4LDM1LjI0MS4yMy4xMjNcIixcInR3b0ZhRXhwaXJ5VHNcIjoxNzcxOTc5NDAwMDAwfSIsImlzcyI6ImFwZXgtYXV0aC1wcm9kLWFwcCJ9.S3SGwi0aLsL26Tf_c9VNYbefqSGyQ0dkr6x95ueFrxtBRg-FY5UJ-4dZLNuzO_yEsoXujQimRzZQC992OFhsqw

GROWW_API_SECRET = LMT1j3n9j_vgY9kRP8i5EyOEo_#evm^P

# Supabase Credentials
SUPABASE_ANON_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtcGFqYmF5bHdybHF0Y3Ftd29vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4NDMxNDYsImV4cCI6MjA4NzQxOTE0Nn0.sOn5X3T1CfGtgS7ooFQJP1BL2Mz65jWtYkhYCkpLbBo

SUPABASE_SERVICE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtcGFqYmF5bHdybHF0Y3Ftd29vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTg0MzE0NiwiZXhwIjoyMDg3NDE5MTQ2fQ.TH4wJTsaEWmFm7K9yR5fPNu2ShNAVT7joKG2TdDKeGg

SUPABASE_DB_PASSWORD = Conversant02
```

3. **Click "Save Changes"** - This will trigger a redeploy automatically.

### 5. Verify Deployment

**Check Health Endpoint:**
```bash
curl https://tradiqai-dashboard.onrender.com/health
```

Expected response:
```json
{"status":"healthy","timestamp":"2026-02-24T..."}
```

**Check Logs:**
- Dashboard → `tradiqai-dashboard` → **Logs** tab
- Look for: `Application startup complete` and `Uvicorn running on http://0.0.0.0:10000`

---

## 🌐 Connect Custom Domain (tradiqai.com)

### Step 1: Add Domain in Render

1. Go to **Web Service** → **Settings** → **Custom Domain**
2. Click **"Add Custom Domain"**
3. Enter: `tradiqai.com`
4. Click **"Add Custom Domain"** again for `www.tradiqai.com`

Render will show DNS records to configure.

### Step 2: Configure Namecheap DNS

1. Log into **Namecheap** → Manage `tradiqai.com` → **Advanced DNS**

2. **Delete existing A/CNAME records** (if any)

3. **Add these records:**

| Type | Host | Value | TTL |
|------|------|-------|-----|
| CNAME | @ | tradiqai-dashboard.onrender.com | Automatic |
| CNAME | www | tradiqai-dashboard.onrender.com | Automatic |

4. **Save Changes**

### Step 3: Wait for DNS Propagation

- **Propagation time:** 5-30 minutes (sometimes up to 24 hours)
- **Check status:** https://www.whatsmydns.net/#CNAME/tradiqai.com

### Step 4: Enable HTTPS (Automatic)

- Render auto-provisions **Let's Encrypt SSL certificate**
- Once DNS propagates, SSL is enabled automatically
- **Force HTTPS:** Settings → Custom Domain → Enable "Redirect HTTP to HTTPS"

### Step 5: Verify Domain

```bash
curl https://tradiqai.com/health
curl https://www.tradiqai.com/health
```

Both should return `{"status":"healthy",...}`

---

## 🔄 Update Supabase Site URL

After domain is connected, update Supabase allowed URLs:

1. Go to **Supabase Dashboard** → Project `lmpajbaylwrlqtcqmwoo`
2. **Authentication** → **URL Configuration**
3. Update:
   - **Site URL:** `https://tradiqai.com`
   - **Redirect URLs:** Add these:
     ```
     https://tradiqai.com/**
     https://www.tradiqai.com/**
     https://tradiqai-dashboard.onrender.com/**
     ```
4. **Save** changes

---

## 📊 Database Management

### Access PostgreSQL Database

**Connection details automatically available in web service environment:**
- `DATABASE_URL` is auto-set by Render from `tradiqai-postgres` database

**Connect via psql (for manual access):**

1. Go to **Dashboard** → `tradiqai-postgres` → **Info** tab
2. Copy **External Connection String**:
   ```
   postgresql://tradiqai_user:<password>@dpg-xxxx.singapore-postgres.render.com/tradiqai
   ```

3. Connect:
   ```bash
   psql "postgresql://tradiqai_user:<password>@dpg-xxxx.singapore-postgres.render.com/tradiqai"
   ```

**OR use Render Shell:**
```bash
# From Render dashboard: tradiqai-postgres → Shell tab
\dt  # List tables
SELECT * FROM users;
```

### Access Redis Cache

**Connection details automatically available in web service:**
- `REDIS_URL` is auto-set from `tradiqai-redis` database

**Connect via redis-cli:**

1. Get connection details: Dashboard → `tradiqai-redis` → **Info**
2. Copy **External Connection String**:
   ```
   redis://:<password>@red-xxxx.singapore-redis.render.com:6379
   ```

3. Connect:
   ```bash
   redis-cli -u "redis://:<password>@red-xxxx.singapore-redis.render.com:6379"
   ```

---

## 🔍 Monitoring & Logs

### View Live Logs

**Dashboard → tradiqai-dashboard → Logs**

Real-time logs with filtering:
- Filter by log level (INFO, ERROR, DEBUG)
- Search text
- Download logs

### Monitor Resource Usage

**Dashboard → tradiqai-dashboard → Metrics**

Track:
- CPU usage
- Memory usage
- Request count
- Response times
- Deploy history

### Health Checks

Render automatically pings `/health` endpoint every 30 seconds:
- ✅ **Healthy:** Returns 200 status
- ❌ **Unhealthy:** Auto-restarts service after 3 failed checks

---

## 🐛 Troubleshooting

### Build Fails with Python Version Error

**Issue:** Wrong Python version detected

**Fix:**
1. Ensure `render.yaml` has:
   ```yaml
   envVars:
     - key: PYTHON_VERSION
       value: 3.11.8
   ```
2. Check build logs for: `Using Python 3.11.8`

### Service Won't Start - Port Error

**Issue:** App not binding to `$PORT` environment variable

**Fix:**
- `dashboard.py` must read port from `PORT` env var (already configured in `start.sh`)
- Render automatically sets `PORT` - don't hardcode 9000

### Database Connection Fails

**Issue:** `DATABASE_URL` not set or wrong format

**Fix:**
1. Verify database is created: Dashboard → Databases → `tradiqai-postgres`
2. Check environment: Web Service → Environment → `DATABASE_URL` should be auto-populated
3. Manual restart: Settings → **Manual Deploy** → **Deploy latest commit**

### Redis Connection Timeout

**Issue:** Redis not responding

**Fix:**
1. Check Redis is running: Dashboard → `tradiqai-redis` → should show "Available"
2. Verify `REDIS_URL` in web service environment
3. Check Redis logs for errors

### Deployment Stuck / Slow

**Issue:** Build taking >10 minutes

**Fix:**
1. Check build logs for hanging step
2. Common culprit: `pip install` of large packages
3. Consider adding `.renderignore` to exclude unnecessary files:
   ```
   .git/
   .venv/
   __pycache__/
   *.pyc
   .env
   ```

### Health Check Fails

**Issue:** Service keeps restarting

**Fix:**
1. Check logs for application errors
2. Verify `/health` endpoint returns 200:
   ```bash
   curl -I https://tradiqai-dashboard.onrender.com/health
   ```
3. Temporarily disable health check: Settings → Health Check Path → (leave empty)

---

## 💰 Cost Optimization

### Use Free Tier (Development)

Change in `render.yaml`:
```yaml
services:
  - type: web
    plan: free  # Changes from $7 to free
    # NOTE: Service sleeps after 15 min inactivity
```

**Limitations:**
- 750 hours/month free (then $0.10/hour)
- Sleeps after 15 minutes of inactivity (30 sec cold start)
- No custom domains

**Keep databases?** 
- PostgreSQL Starter: $7/month (no free tier)
- Redis Starter: $10/month (no free tier)
- **Alternative:** Use your existing Supabase for PostgreSQL (already configured in render.yaml)

### Use External Supabase (Save $7/month)

Remove PostgreSQL from render.yaml and update `DATABASE_URL`:

```yaml
envVars:
  # Use your existing Supabase instead of Render PostgreSQL
  - key: DATABASE_URL
    value: postgresql://postgres.lmpajbaylwrlqtcqmwoo:Conversant02@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

Delete `databases` section for PostgreSQL.

**Total cost:** $17/month (web $7 + redis $10) or $10/month (redis only if using free web tier)

---

## 🔐 Security Best Practices

### Environment Variables

✅ **DO:**
- Set all secrets via Render dashboard (not in render.yaml)
- Use `sync: false` for sensitive values in render.yaml
- Rotate API keys regularly

❌ **DON'T:**
- Commit `.env` file to git (already in .gitignore)
- Share Supabase service key publicly
- Hardcode secrets in code

### Database Access

- Use Render's internal networking for db connections (automatically configured)
- Keep `ipAllowList: []` for internal access
- Add specific IPs if accessing externally

### SSL/HTTPS

- Render provides free SSL via Let's Encrypt (automatic)
- Enable "Force HTTPS" for custom domains
- Update Supabase with HTTPS URLs only

---

## 🚀 Deploy Updates

### Automatic Deploys (Recommended)

**Already configured!** Any push to `main` branch triggers auto-deploy.

```bash
git add .
git commit -m "Update dashboard features"
git push origin main
```

Render automatically:
1. Detects push to GitHub
2. Starts new build
3. Runs tests (if configured)
4. Deploys new version
5. Zero-downtime switch

### Manual Deploy

**From Render Dashboard:**
1. `tradiqai-dashboard` → **Manual Deploy**
2. Select branch: `main`
3. Click **Deploy**

### Rollback

**If deployment breaks:**
1. Dashboard → **Events** tab
2. Find last working deploy
3. Click **⋯** → **Rollback to this version**

---

## 📚 Additional Resources

- **Render Docs:** https://render.com/docs
- **Python on Render:** https://render.com/docs/deploy-flask
- **Blueprint Spec:** https://render.com/docs/blueprint-spec
- **Render Status:** https://status.render.com

---

## ✅ Deployment Checklist

- [ ] Pushed `render.yaml` to GitHub
- [ ] Signed up for Render (with GitHub)
- [ ] Created Blueprint from repository
- [ ] Set secret environment variables (GROWW, Supabase)
- [ ] Verified deployment at `.onrender.com` URL
- [ ] Added custom domain `tradiqai.com`
- [ ] Updated Namecheap DNS records
- [ ] Waited for DNS propagation (5-30 min)
- [ ] Verified HTTPS works
- [ ] Updated Supabase Site URL
- [ ] Tested login/trading functionality
- [ ] Monitoring logs for errors
- [ ] Set up auto-deploy on push

---

**Your dashboard will be live at:**
- 🔗 **Render URL:** https://tradiqai-dashboard.onrender.com
- 🔗 **Custom Domain:** https://tradiqai.com (after DNS setup)

**Cost:** $24/month or less with optimizations

**Questions?** Check troubleshooting section or Render support.
