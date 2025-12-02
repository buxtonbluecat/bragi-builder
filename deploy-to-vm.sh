#!/bin/bash
# Deploy application files to VM

set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-bb-test-rc}"
VM_NAME="${VM_NAME:-bragi-builder-vm}"
ADMIN_USERNAME="${ADMIN_USERNAME:-azureuser}"
SSH_KEY_PATH="$HOME/.ssh/id_rsa_bragi"
APP_DIR="/opt/bragi-builder"

# Get VM IP
VM_IP=$(az vm show -d --resource-group $RESOURCE_GROUP --name $VM_NAME --query publicIps -o tsv)

if [ -z "$VM_IP" ]; then
    echo "❌ Could not find VM IP. Is the VM created?"
    exit 1
fi

echo "🚀 Deploying Bragi Builder to VM"
echo "================================="
echo "VM IP: $VM_IP"
echo ""

# Test SSH connection
echo "Testing SSH connection..."
ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no $ADMIN_USERNAME@$VM_IP "echo 'SSH connection successful'" || {
    echo "❌ SSH connection failed. Please check:"
    echo "  1. VM is running"
    echo "  2. SSH key is correct: $SSH_KEY_PATH"
    echo "  3. Network security group allows SSH (port 22)"
    exit 1
}

# Copy application files
echo "Copying application files..."
rsync -avz --progress \
    -e "ssh -i $SSH_KEY_PATH" \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude '*.db' \
    ./ $ADMIN_USERNAME@$VM_IP:$APP_DIR/

# Install dependencies and start service
echo "Installing dependencies and starting service..."
ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP << 'ENDSSH'
    cd /opt/bragi-builder
    sudo chown -R bragi:bragi /opt/bragi-builder
    sudo -u bragi /opt/bragi-builder/venv/bin/pip install --upgrade pip
    sudo -u bragi /opt/bragi-builder/venv/bin/pip install -r /opt/bragi-builder/requirements.txt
    sudo systemctl restart bragi-builder
    sudo systemctl restart nginx
    sudo systemctl status bragi-builder --no-pager
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Application URL: http://$VM_IP"
echo ""
echo "To check logs:"
echo "  ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP 'sudo journalctl -u bragi-builder -f'"
