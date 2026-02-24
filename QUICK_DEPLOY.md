# 🚀 Railway Deployment - Quick Reference

## Deploy in 4 Commands

```bash
# 1. Commit deployment files
git add .
git commit -m "Add Railway deployment"
git push origin main

# 2. Go to railway.app and click:
# "New Project" → "Deploy from GitHub" → Select "autotrade-ai"

# 3. Add databases:
# Click "New" → "Database" → "PostgreSQL"
# Click "New" → "Database" → "Redis"

# 4. Set variables in Railway dashboard:
ENV=production
BROKER=zerodha
ZERODHA_API_KEY=<your_key>
SUPABASE_URL=<your_url>
# ... (see .env.railway for full list)
```

## Essential URLs

- **Railway Dashboard:** https://railway.app/dashboard
- **Deploy from GitHub:** https://railway.app/new/github
- **Your App:** `https://<project-name>.up.railway.app`
- **Custom Domain:** Settings → Networking → Custom Domain

## Quick Checks

```bash
# Health check
curl https://<your-app>.up.railway.app/health

# Check DNS
nslookup tradiqai.com

# View logs
# Railway Dashboard → Your Service → Deployments → View Logs
```

## Environment Variables (Required)

```bash
# Copy from .env.railway, minimum required:
ENV=production
DEBUG=false
BROKER=zerodha
ZERODHA_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
# DATABASE_URL and REDIS_URL auto-created when you add databases
```

## GitHub Actions (Optional)

```bash
# 1. Get Railway token from: Account Settings → Tokens
# 2. Add to GitHub: Settings → Secrets → New
#    Name: RAILWAY_TOKEN
#    Value: <your_token>
# 3. Push to deploy:
git push origin main
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| App won't start | Check Railway logs for errors |
| DB connection failed | Add PostgreSQL in Railway |
| Redis timeout | Add Redis in Railway |
| Domain not working | Wait 10-30 min for DNS |
| Missing module | Add to requirements.txt |

## Cost

- **$5/month** (includes $5 credit, effectively free for small apps)
- PostgreSQL + Redis included
- SSL certificate free

## Full Documentation

- Complete guide: [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)
- Summary: [DEPLOYMENT_READY.md](DEPLOYMENT_READY.md)
