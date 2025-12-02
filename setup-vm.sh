#!/bin/bash
# Setup script to run on the VM
# Installs dependencies and deploys Bragi Builder

set -e

APP_DIR="/opt/bragi-builder"
SERVICE_USER="bragi"

echo "🔧 Setting up Bragi Builder on VM..."
echo "====================================="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and dependencies
echo "Installing Python 3.11 and dependencies..."
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    sqlite3 \
    nginx \
    certbot \
    python3-certbot-nginx

# Create application user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    sudo useradd -r -s /bin/bash -d $APP_DIR $SERVICE_USER
fi

# Create application directory
sudo mkdir -p $APP_DIR
sudo chown $SERVICE_USER:$SERVICE_USER $APP_DIR

# Clone or copy application files
echo "Setting up application..."
cd $APP_DIR

# If running from local machine, we'll copy files via SCP
# For now, create directory structure
sudo -u $SERVICE_USER mkdir -p $APP_DIR/{src,static,templates}

# Create virtual environment
echo "Creating Python virtual environment..."
sudo -u $SERVICE_USER python3.11 -m venv $APP_DIR/venv

# Install Python dependencies (will be done after copying files)
# sudo -u $SERVICE_USER $APP_DIR/venv/bin/pip install --upgrade pip
# sudo -u $SERVICE_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/bragi-builder.service > /dev/null <<EOF
[Unit]
Description=Bragi Builder Application
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
Environment="FLASK_ENV=production"
Environment="PORT=8080"
ExecStart=$APP_DIR/venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 4 --timeout 600 --worker-class eventlet --log-level info --access-logfile - --error-logfile - app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
echo "Configuring nginx..."
sudo tee /etc/nginx/sites-available/bragi-builder > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/bragi-builder /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Enable and start services
echo "Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable bragi-builder
sudo systemctl enable nginx

echo ""
echo "✅ VM setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy application files to $APP_DIR"
echo "  2. Install Python dependencies: cd $APP_DIR && venv/bin/pip install -r requirements.txt"
echo "  3. Start services: sudo systemctl start bragi-builder nginx"
echo "  4. Check status: sudo systemctl status bragi-builder"
