# AutoTrade AI - Deployment Guide

## Table of Contents
1. [Local Development Deployment](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Linux VPS Deployment](#linux-vps-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployment (AWS/GCP/Azure)](#cloud-deployment)
6. [Monitoring & Maintenance](#monitoring)

---

## 1. Local Development Deployment

### Current Setup (Already Running)

Your system is currently running locally with:
- Python virtual environment
- SQLite database
- Simplified live-quote strategy

**Commands:**
```powershell
# Start system
.venv\Scripts\Activate.ps1; python main.py

# Monitor system
python live_monitor.py

# View logs
Get-Content logs\trading_2026-02-17.log -Tail 50 -Wait
```

---

## 2. Docker Deployment (Recommended for Windows/Mac)

### Prerequisites
- Docker Desktop installed
- Docker Compose available

### Quick Start

**Windows:**
```powershell
.\deploy.ps1
```

**Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh
```

### What It Includes
- Trading application container
- PostgreSQL database
- Redis cache
- Prometheus (monitoring)
- Grafana (dashboards)

### Configuration

1. **Update .env file:**
```bash
cp .env .env.backup
# Edit .env with production credentials
```

2. **Build and start:**
```bash
docker-compose up -d
```

3. **View logs:**
```bash
docker-compose logs -f app
```

### Management Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart trading app
docker-compose restart app

# View logs
docker-compose logs -f app

# Access database
docker-compose exec postgres psql -U postgres -d autotrade

# Shell access
docker-compose exec app /bin/bash

# View resource usage
docker stats
```

### Accessing Services

- **Grafana Dashboards:** http://localhost:3000 (admin/admin)
- **Prometheus Metrics:** http://localhost:9090
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

---

## 3. Linux VPS Deployment (Ubuntu 22.04+)

### Prerequisites
- Ubuntu 22.04 or later
- Root access
- At least 2GB RAM, 2 CPU cores, 20GB storage

### Installation Steps

1. **Copy files to server:**
```bash
# On your local machine
scp -r . user@your-server-ip:/tmp/autotrade-ai
```

2. **Run installation script:**
```bash
# On the server
ssh user@your-server-ip
sudo bash /tmp/autotrade-ai/install_vps.sh
```

3. **Configure application:**
```bash
sudo nano /opt/autotrade-ai/.env
# Update with your API credentials
```

4. **Start service:**
```bash
sudo systemctl start autotrade.service
sudo systemctl enable autotrade.service
```

### VPS Management Commands

```bash
# Check status
autotrade-status

# View logs
journalctl -u autotrade.service -f

# Start/Stop/Restart
sudo systemctl start autotrade.service
sudo systemctl stop autotrade.service
sudo systemctl restart autotrade.service

# Database access
sudo -u postgres psql autotrade

# Manual backup
sudo /etc/cron.daily/autotrade-backup
```

### Firewall Configuration

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow PostgreSQL (if remote access needed)
sudo ufw allow 5432/tcp

# Enable firewall
sudo ufw enable
```

---

## 4. Kubernetes Deployment (GKE/EKS/AKS)

### Prerequisites
- Kubernetes cluster (GKE, EKS, or AKS)
- kubectl configured
- Container registry access

### Deployment Steps

1. **Build and push Docker image:**
```bash
# Build
docker build -t your-registry/autotrade-ai:latest .

# Push
docker push your-registry/autotrade-ai:latest
```

2. **Update Kubernetes manifests:**
```bash
# Edit kubernetes/deployment.yaml
# Update image: your-registry/autotrade-ai:latest
# Update secrets with your credentials
```

3. **Apply configurations:**
```bash
kubectl apply -f kubernetes/deployment.yaml
```

4. **Verify deployment:**
```bash
kubectl get pods -n autotrade
kubectl logs -f deployment/autotrade-app -n autotrade
```

### Kubernetes Management

```bash
# View pods
kubectl get pods -n autotrade

# View logs
kubectl logs -f deployment/autotrade-app -n autotrade

# Restart deployment
kubectl rollout restart deployment/autotrade-app -n autotrade

# Scale (if needed)
kubectl scale deployment/autotrade-app --replicas=1 -n autotrade

# Get shell access
kubectl exec -it deployment/autotrade-app -n autotrade -- /bin/bash

# Port forward for local access
kubectl port-forward service/postgres 5432:5432 -n autotrade
```

---

## 5. Cloud Deployment

### AWS Deployment

#### Option A: EC2 Instance
1. Launch Ubuntu 22.04 EC2 instance (t3.medium recommended)
2. Configure security groups (allow SSH, PostgreSQL)
3. Follow [Linux VPS Deployment](#linux-vps-deployment) steps

#### Option B: ECS with Fargate
```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name autotrade-cluster

# Register task definition
aws ecs register-task-definition --cli-input-json file://aws/task-definition.json

# Create service
aws ecs create-service \
    --cluster autotrade-cluster \
    --service-name autotrade-service \
    --task-definition autotrade:1 \
    --desired-count 1 \
    --launch-type FARGATE
```

### GCP Deployment

#### Option A: Compute Engine
1. Create Ubuntu VM (e2-medium recommended)
2. Configure firewall rules
3. Follow [Linux VPS Deployment](#linux-vps-deployment) steps

#### Option B: GKE
```bash
# Create GKE cluster
gcloud container clusters create autotrade-cluster \
    --num-nodes=2 \
    --machine-type=e2-medium

# Deploy
kubectl apply -f kubernetes/deployment.yaml
```

### Azure Deployment

#### Option A: Virtual Machine
1. Create Ubuntu 22.04 VM (Standard_B2s recommended)
2. Configure NSG rules
3. Follow [Linux VPS Deployment](#linux-vps-deployment) steps

#### Option B: AKS
```bash
# Create AKS cluster
az aks create \
    --resource-group autotrade-rg \
    --name autotrade-cluster \
    --node-count 2 \
    --node-vm-size Standard_B2s

# Deploy
kubectl apply -f kubernetes/deployment.yaml
```

---

## 6. Monitoring & Maintenance

### System Health Checks

**Docker:**
```bash
docker-compose ps
docker-compose logs --tail=100 app
```

**VPS:**
```bash
autotrade-status
systemctl status autotrade.service
```

**Kubernetes:**
```bash
kubectl get pods -n autotrade
kubectl describe pod <pod-name> -n autotrade
```

### Monitoring Metrics

Access Grafana dashboard at `http://your-server:3000`:
- P&L tracking
- Trade statistics
- Win/loss ratios
- System resource usage
- API response times

### Log Management

**View logs:**
```bash
# Docker
docker-compose logs -f app

# VPS
tail -f /var/log/autotrade/app.log
journalctl -u autotrade.service -f

# Kubernetes
kubectl logs -f deployment/autotrade-app -n autotrade
```

### Backup & Recovery

**Automated Backups:**
- Database: Daily automatic backup (30-day retention)
- Logs: Rotated daily, kept for 30 days
- Location: `/opt/autotrade-ai/data/backups`

**Manual Backup:**
```bash
# Database
pg_dump -U postgres autotrade | gzip > backup_$(date +%Y%m%d).sql.gz

# Application data
tar -czf data_backup_$(date +%Y%m%d).tar.gz /opt/autotrade-ai/data/
```

**Restore:**
```bash
# Database
gunzip < backup_20260217.sql.gz | psql -U postgres autotrade

# Application data
tar -xzf data_backup_20260217.tar.gz -C /
```

### Performance Tuning

**Database Optimization:**
```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_timestamp ON trades(entry_timestamp);

-- Vacuum database
VACUUM ANALYZE;
```

**Resource Limits:**
```yaml
# docker-compose.yml
resources:
  limits:
    cpus: '2'
    memory: 2G
  reservations:
    cpus: '1'
    memory: 1G
```

### Security Best Practices

1. **Use environment variables for secrets**
2. **Enable SSL/TLS for database connections**
3. **Restrict firewall rules to necessary ports**
4. **Regular security updates:**
```bash
sudo apt update && sudo apt upgrade -y
```
5. **Monitor failed login attempts**
6. **Use strong passwords for all services**

### Troubleshooting

**Common Issues:**

1. **Container won't start:**
```bash
docker-compose logs app
docker-compose down && docker-compose up -d
```

2. **Database connection errors:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres
# Or
systemctl status postgresql
```

3. **API authentication failures:**
- Check API key/secret in .env
- Verify token hasn't expired
- Test API connection manually

4. **High memory usage:**
```bash
# Check resource usage
docker stats
# Or
htop
```

### Support & Updates

**Update application:**
```bash
# Docker
docker-compose pull
docker-compose up -d

# VPS
cd /opt/autotrade-ai
sudo -u autotrade git pull
sudo systemctl restart autotrade.service

# Kubernetes
kubectl set image deployment/autotrade-app \
    autotrade=your-registry/autotrade-ai:new-version \
    -n autotrade
```

---

## Quick Reference

| Deployment Method | Best For | Complexity | Cost |
|-------------------|----------|------------|------|
| Local Development | Testing, Development | Low | Free |
| Docker | Windows/Mac, Easy setup | Medium | Free |
| VPS | Production, Full control | Medium | $5-20/mo |
| Kubernetes | Scale, High availability | High | $50-200/mo |
| Cloud Managed | Enterprise, Reliability | Medium-High | Varies |

---

## Deployment Checklist

- [ ] Update `.env` with production credentials
- [ ] Set `PAPER_TRADING=false` for live trading
- [ ] Configure Telegram alerts
- [ ] Test with small capital first
- [ ] Set up monitoring dashboards
- [ ] Configure automated backups
- [ ] Document API credentials securely
- [ ] Set up log rotation
- [ ] Test failover scenarios
- [ ] Create runbook for common issues

---

**System is ready for deployment!** Choose the method that best fits your requirements.
