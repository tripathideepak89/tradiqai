#!/bin/bash
# Linux VPS Deployment Script

set -e

echo "======================================"
echo "AutoTrade AI - VPS Installation"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Update system
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install dependencies
echo "Installing system dependencies..."
apt-get install -y \
    python3.13 \
    python3.13-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    git \
    nginx \
    supervisor

# Create autotrade user
echo "Creating autotrade user..."
if ! id -u autotrade > /dev/null 2>&1; then
    useradd -m -s /bin/bash autotrade
fi

# Create application directory
echo "Setting up application directory..."
APP_DIR="/opt/autotrade-ai"
mkdir -p $APP_DIR
cd $APP_DIR

# Clone or copy application files
if [ -d "/tmp/autotrade-ai" ]; then
    echo "Copying application files..."
    cp -r /tmp/autotrade-ai/* $APP_DIR/
else
    echo "Application files should be in /tmp/autotrade-ai"
    exit 1
fi

# Create virtual environment
echo "Creating Python virtual environment..."
python3.13 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs data data/backups
chown -R autotrade:autotrade $APP_DIR

# Setup PostgreSQL
echo "Setting up PostgreSQL database..."
sudo -u postgres psql << EOF
CREATE DATABASE autotrade;
CREATE USER autotrade WITH ENCRYPTED PASSWORD 'change_this_password';
GRANT ALL PRIVILEGES ON DATABASE autotrade TO autotrade;
\q
EOF

# Configure Redis
echo "Configuring Redis..."
sed -i 's/^bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
systemctl enable redis-server
systemctl restart redis-server

# Setup environment file
echo "Creating environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.production .env
    echo "Please edit /opt/autotrade-ai/.env with your configuration"
fi

# Install systemd service
echo "Installing systemd service..."
cp systemd/autotrade.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable autotrade.service

# Create log directory
mkdir -p /var/log/autotrade
chown autotrade:autotrade /var/log/autotrade

# Setup log rotation
cat > /etc/logrotate.d/autotrade << EOF
/var/log/autotrade/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 autotrade autotrade
    sharedscripts
    postrotate
        systemctl reload autotrade.service > /dev/null 2>&1 || true
    endscript
}
EOF

# Setup cron for daily backups
echo "Setting up automated backups..."
cat > /etc/cron.daily/autotrade-backup << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/autotrade-ai/data/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
sudo -u postgres pg_dump autotrade | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Backup logs
tar -czf "$BACKUP_DIR/logs_backup_$DATE.tar.gz" /opt/autotrade-ai/logs/

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /etc/cron.daily/autotrade-backup

# Setup firewall (optional)
if command -v ufw &> /dev/null; then
    echo "Configuring firewall..."
    ufw allow 22/tcp  # SSH
    ufw allow 5432/tcp  # PostgreSQL (if remote access needed)
    ufw --force enable
fi

# Create monitoring script
cat > /usr/local/bin/autotrade-status << 'EOF'
#!/bin/bash
echo "======================================"
echo "AutoTrade AI System Status"
echo "======================================"
echo ""

# Service status
echo "Service Status:"
systemctl status autotrade.service --no-pager | head -n 10

echo ""
echo "Resource Usage:"
ps aux | grep "python.*main.py" | grep -v grep

echo ""
echo "Recent Logs:"
tail -n 20 /var/log/autotrade/app.log

echo ""
echo "Database Status:"
sudo -u postgres psql -c "SELECT count(*) as active_trades FROM trades WHERE status = 'OPEN';" autotrade

echo ""
echo "Disk Usage:"
df -h /opt/autotrade-ai
EOF

chmod +x /usr/local/bin/autotrade-status

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit configuration: nano /opt/autotrade-ai/.env"
echo "2. Start service: systemctl start autotrade.service"
echo "3. Check status: autotrade-status"
echo "4. View logs: journalctl -u autotrade.service -f"
echo ""
echo "Management commands:"
echo "  Start:   systemctl start autotrade.service"
echo "  Stop:    systemctl stop autotrade.service"
echo "  Restart: systemctl restart autotrade.service"
echo "  Status:  autotrade-status"
echo "  Logs:    tail -f /var/log/autotrade/app.log"
echo ""
