# TradiqAI Website Deployment Guide

This directory contains the landing page for TradiqAI.com with subdomain configurations.

## 📁 Structure

```
web/
├── index.html          # Main landing page
├── styles.css          # Responsive styling
├── script.js           # Interactive features
├── README.md           # This file
└── docs/              # Documentation site (to be created)
```

## 🌐 Subdomain Configuration

### 1. Main Site: tradiqai.com

**Purpose:** Landing page showcasing features and capabilities

**Setup:**
1. Upload `index.html`, `styles.css`, `script.js` to your web hosting root
2. Configure DNS A record pointing to your server IP
3. Enable HTTPS with Let's Encrypt/Cloudflare

**Files:**
- `index.html` - Main landing page
- `styles.css` - Complete styling
- `script.js` - Smooth scrolling and animations

### 2. Documentation: docs.tradiqai.com

**Purpose:** Host all markdown documentation as HTML

**Deployment Options:**

#### Option A: GitHub Pages (Recommended)
```bash
# 1. Enable GitHub Pages in repository settings
# 2. Select docs/ folder as source
# 3. Configure custom domain: docs.tradiqai.com
```

#### Option B: MkDocs (Professional)
```bash
# Install MkDocs
pip install mkdocs mkdocs-material

# Create mkdocs.yml configuration
# Build and deploy
mkdocs build
mkdocs gh-deploy
```

#### Option C: Docsify (Simple)
```bash
# Install docsify-cli
npm i docsify-cli -g

# Initialize docs
docsify init ./docs

# Serve locally for testing
docsify serve ./docs
```

**DNS Configuration:**
```
Type: CNAME
Name: docs
Value: tripathideepak89.github.io
```

### 3. Dashboard: dashboard.tradiqai.com

**Purpose:** Live trading dashboard and monitoring interface

**Setup:**

#### Production Deployment

1. **Using Nginx Reverse Proxy:**

```nginx
# /etc/nginx/sites-available/dashboard.tradiqai.com
server {
    listen 80;
    server_name dashboard.tradiqai.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

2. **Enable SSL:**
```bash
sudo certbot --nginx -d dashboard.tradiqai.com
```

3. **Start Dashboard Service:**
```bash
# Create systemd service
sudo nano /etc/systemd/system/tradiqai-dashboard.service
```

```ini
[Unit]
Description=TradiqAI Dashboard
After=network.target

[Service]
Type=simple
User=tradiqai
WorkingDirectory=/opt/TradiqAI
Environment="PATH=/opt/TradiqAI/.venv/bin"
ExecStart=/opt/TradiqAI/.venv/bin/python dashboard.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable tradiqai-dashboard
sudo systemctl start tradiqai-dashboard
```

**DNS Configuration:**
```
Type: A
Name: dashboard
Value: [Your-Server-IP]
```

## 🔒 Security Configuration

### Environment Variables for Dashboard
```bash
# Dashboard authentication (add to .env)
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your-secure-password
DASHBOARD_SECRET_KEY=generate-random-key-here
ENABLE_AUTH=true
```

### CORS Configuration
```python
# In dashboard.py, add:
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tradiqai.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📊 Analytics Integration

### Google Analytics
Add to `index.html` before `</head>`:
```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

## 🚀 Deployment Checklist

### Main Site (tradiqai.com)
- [ ] Upload HTML, CSS, JS files to hosting
- [ ] Configure DNS A record
- [ ] Enable HTTPS (Let's Encrypt/Cloudflare)
- [ ] Test responsive design on mobile
- [ ] Verify all links work
- [ ] Add Google Analytics
- [ ] Submit sitemap to Google Search Console

### Documentation (docs.tradiqai.com)
- [ ] Choose deployment method (GitHub Pages/MkDocs/Docsify)
- [ ] Convert markdown files to HTML
- [ ] Configure CNAME DNS record
- [ ] Enable HTTPS
- [ ] Test all documentation links
- [ ] Add search functionality
- [ ] Create table of contents

### Dashboard (dashboard.tradiqai.com)
- [ ] Configure Nginx reverse proxy
- [ ] Enable SSL with Let's Encrypt
- [ ] Create systemd service
- [ ] Configure DNS A record
- [ ] Add authentication layer
- [ ] Set up CORS properly
- [ ] Monitor uptime (use UptimeRobot)
- [ ] Configure firewall rules

## 🌐 Example DNS Configuration

```
# Main domain
Type: A
Name: @
Value: 192.168.1.100
TTL: 3600

# Documentation
Type: CNAME
Name: docs
Value: tripathideepak89.github.io
TTL: 3600

# Dashboard
Type: A
Name: dashboard
Value: 192.168.1.100
TTL: 3600

# WWW redirect
Type: CNAME
Name: www
Value: tradiqai.com
TTL: 3600
```

## 📱 Testing

### Local Testing
```bash
# Test landing page
python -m http.server 8000
# Visit: http://localhost:8000/web/

# Test dashboard
python dashboard.py
# Visit: http://localhost:8080
```

### Production Testing
```bash
# Test SSL
curl -I https://tradiqai.com
curl -I https://docs.tradiqai.com
curl -I https://dashboard.tradiqai.com

# Test dashboard API
curl -I https://dashboard.tradiqai.com/api/account
```

## 🔧 Troubleshooting

### Landing Page Not Loading
1. Check file permissions: `chmod 644 index.html styles.css script.js`
2. Verify DNS propagation: `dig tradiqai.com`
3. Check server logs: `tail -f /var/log/nginx/error.log`

### Documentation 404 Errors
1. Verify GitHub Pages is enabled
2. Check CNAME file exists in docs/ folder
3. Wait 5-10 minutes for DNS propagation

### Dashboard Connection Issues
1. Check service status: `systemctl status tradiqai-dashboard`
2. Verify Nginx config: `nginx -t`
3. Check firewall: `sudo ufw status`
4. Review logs: `journalctl -u tradiqai-dashboard -f`

## 📈 Performance Optimization

### Landing Page
- Enable gzip compression in Nginx
- Minify CSS and JS files
- Optimize images (WebP format)
- Add CDN (Cloudflare)
- Enable browser caching

### Dashboard
- Use Redis for session management
- Enable WebSocket compression
- Implement rate limiting
- Add CDN for static assets
- Monitor with Prometheus/Grafana

## 🎨 Customization

### Branding
- Logo: Replace emoji in `.logo-icon` with custom logo
- Colors: Update CSS variables in `:root`
- Fonts: Change Google Fonts import in `<head>`

### Content
- Edit `index.html` sections as needed
- Update links to your actual GitHub/docs URLs
- Customize feature descriptions
- Add testimonials or case studies

## 📞 Support

For issues or questions:
- GitHub: https://github.com/tripathideepak89/TradiqAI/issues
- Documentation: https://docs.tradiqai.com
- Email: support@tradiqai.com (if configured)

---

**Last Updated:** February 23, 2026
