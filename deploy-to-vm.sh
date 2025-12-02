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

# Deploy from git
echo "Deploying from git repository..."
GIT_REPO="${GIT_REPO:-https://github.com/buxtonbluecat/bragi-builder.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"

ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP bash << ENDSSH
    set -e
    cd $APP_DIR
    
    # Clone or update repository
    if [ -d "$APP_DIR/.git" ]; then
        echo "Updating repository from git..."
        sudo -u bragi git fetch origin
        sudo -u bragi git reset --hard origin/$GIT_BRANCH
        sudo -u bragi git clean -fd
    else
        echo "Cloning repository from git..."
        # Backup venv if it exists
        if [ -d "$APP_DIR/venv" ]; then
            echo "Backing up existing venv..."
            sudo mv $APP_DIR/venv /tmp/venv-backup-$(date +%s)
        fi
        # Remove everything except venv backup
        echo "Cleaning directory..."
        sudo find $APP_DIR -mindepth 1 -maxdepth 1 ! -name venv -exec rm -rf {} \; 2>/dev/null || true
        # Clone into a temp directory first
        TEMP_DIR="/tmp/bragi-builder-$(date +%s)"
        sudo -u bragi git clone -b $GIT_BRANCH $GIT_REPO $TEMP_DIR
        # Move contents to app directory
        sudo mv $TEMP_DIR/* $TEMP_DIR/.* $APP_DIR/ 2>/dev/null || true
        sudo rm -rf $TEMP_DIR
        # Restore venv if it existed
        if [ -d "/tmp/venv-backup"* ]; then
            VENV_BACKUP=$(ls -td /tmp/venv-backup-* 2>/dev/null | head -1)
            if [ -n "$VENV_BACKUP" ]; then
                echo "Restoring venv..."
                sudo rm -rf $APP_DIR/venv
                sudo mv $VENV_BACKUP $APP_DIR/venv
            fi
        fi
    fi
    
    # Ensure proper ownership
    sudo chown -R bragi:bragi $APP_DIR
    
    # Install/update dependencies
    echo "Installing Python dependencies..."
    sudo -u bragi $APP_DIR/venv/bin/pip install --upgrade pip
    sudo -u bragi $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
    
    # Restart services
    echo "Restarting services..."
    sudo systemctl restart bragi-builder
    sudo systemctl restart nginx
    sleep 2
    sudo systemctl status bragi-builder --no-pager | head -15
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Application URL: http://$VM_IP"
echo ""
echo "To check logs:"
echo "  ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP 'sudo journalctl -u bragi-builder -f'"
