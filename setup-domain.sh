#!/bin/bash
# Script to configure custom domain and SSL for Bragi Builder on Azure VM

set -e

# Configuration
RESOURCE_GROUP="bb-test-rc"
VM_NAME="bragi-builder-vm"
ADMIN_USERNAME="azureuser"
SSH_KEY_PATH="$HOME/.ssh/id_rsa_bragi"

# Get VM IP
VM_IP=$(az vm show -d --resource-group $RESOURCE_GROUP --name $VM_NAME --query publicIps -o tsv)

if [ -z "$VM_IP" ]; then
    echo "Error: Could not get VM IP address"
    exit 1
fi

# Get domain name from user
if [ -z "$1" ]; then
    echo "Usage: $0 <domain-name>"
    echo "Example: $0 bragi-builder.example.com"
    echo ""
    echo "Current VM IP: $VM_IP"
    echo ""
    echo "Before running this script:"
    echo "1. Point your domain's A record to: $VM_IP"
    echo "2. Wait for DNS propagation (can take a few minutes)"
    echo "3. Verify DNS: dig +short <your-domain>"
    exit 1
fi

DOMAIN_NAME="$1"
EMAIL="${2:-admin@${DOMAIN_NAME#*.}}"  # Default email based on domain

echo "=== Setting up domain: $DOMAIN_NAME ==="
echo "VM IP: $VM_IP"
echo "Email for Let's Encrypt: $EMAIL"
echo ""

# Step 1: Update Nginx configuration with domain name
echo "Step 1: Updating Nginx configuration..."
ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP "sudo tee /etc/nginx/sites-available/bragi-builder > /dev/null << 'EOF'
server {
    listen 80;
    server_name $DOMAIN_NAME;

    # Let's Encrypt challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        
        # Timeouts
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
EOF
sudo nginx -t && sudo systemctl reload nginx && echo '✅ Nginx configuration updated'"

# Step 2: Create webroot directory for Let's Encrypt
echo ""
echo "Step 2: Creating webroot directory..."
ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP "sudo mkdir -p /var/www/html && sudo chown -R www-data:www-data /var/www/html && echo '✅ Webroot directory created'"

# Step 3: Obtain SSL certificate
echo ""
echo "Step 3: Obtaining SSL certificate from Let's Encrypt..."
echo "This will prompt for email and agreement to terms of service..."
ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP "sudo certbot certonly --webroot -w /var/www/html -d $DOMAIN_NAME --email $EMAIL --agree-tos --non-interactive --quiet || echo '⚠️  Certificate may already exist or DNS not propagated yet'"

# Step 4: Update Nginx with SSL configuration
echo ""
echo "Step 4: Updating Nginx with SSL configuration..."
ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP "sudo tee /etc/nginx/sites-available/bragi-builder > /dev/null << 'EOF'
# HTTP - Redirect to HTTPS
server {
    listen 80;
    server_name $DOMAIN_NAME;

    # Let's Encrypt challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    server_name $DOMAIN_NAME;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;
    add_header X-Frame-Options \"SAMEORIGIN\" always;
    add_header X-Content-Type-Options \"nosniff\" always;
    add_header X-XSS-Protection \"1; mode=block\" always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        
        # Timeouts
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
EOF
sudo nginx -t && sudo systemctl reload nginx && echo '✅ SSL configuration applied'"

# Step 5: Set up automatic certificate renewal
echo ""
echo "Step 5: Setting up automatic certificate renewal..."
ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP "sudo systemctl enable certbot.timer && sudo systemctl start certbot.timer && echo '✅ Certificate auto-renewal enabled'"

# Step 6: Test SSL certificate
echo ""
echo "Step 6: Testing SSL configuration..."
sleep 2
if curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN_NAME/health" | grep -q "200\|301\|302"; then
    echo "✅ SSL is working! Access your app at: https://$DOMAIN_NAME"
else
    echo "⚠️  SSL may not be fully configured yet. Check:"
    echo "   - DNS propagation: dig +short $DOMAIN_NAME"
    echo "   - Certificate: sudo certbot certificates"
    echo "   - Nginx logs: sudo tail -f /var/log/nginx/error.log"
fi

echo ""
echo "=== Setup Complete ==="
echo "Domain: $DOMAIN_NAME"
echo "HTTP: http://$DOMAIN_NAME (redirects to HTTPS)"
echo "HTTPS: https://$DOMAIN_NAME"
echo ""
echo "To check certificate status:"
echo "  ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP 'sudo certbot certificates'"
echo ""
echo "To manually renew certificate:"
echo "  ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP 'sudo certbot renew'"
