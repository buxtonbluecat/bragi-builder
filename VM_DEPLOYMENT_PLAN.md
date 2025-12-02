# Bragi Builder - VM Deployment Plan

## Overview
This document outlines the complete step-by-step process for deploying Bragi Builder to an Azure Linux VM, incorporating lessons learned from previous deployments.

## Prerequisites
- Azure CLI installed and authenticated
- SSH key pair for VM access
- Git repository access (https://github.com/buxtonbluecat/bragi-builder.git)
- Subscription ID: `693bb5f4-bea9-4714-b990-55d5a4032ae1`

## Step-by-Step Deployment Process

### Phase 1: Infrastructure Provisioning

#### Step 1.1: Create Resource Group
- **Action**: Create resource group `bb-test-rc` in `uksouth`
- **Command**: `az group create --name bb-test-rc --location uksouth`
- **Verification**: Confirm resource group exists

#### Step 1.2: Generate SSH Key (if needed)
- **Action**: Generate SSH key pair for VM access
- **Location**: `~/.ssh/id_rsa_bragi`
- **Verification**: Check key files exist

#### Step 1.3: Create Network Security Group (NSG)
- **Action**: Create NSG with rules for:
  - SSH (port 22)
  - HTTP (port 80)
  - HTTPS (port 443)
  - Application port (port 8080)
- **Verification**: Confirm NSG rules are created

#### Step 1.4: Create Virtual Network (VNet)
- **Action**: Create VNet with subnet
  - VNet: `10.4.0.0/16`
  - Subnet: `10.4.0.0/24`
  - **IMPORTANT**: Configure DNS servers to use Azure DNS (`168.63.129.16`) during VNet creation
- **Verification**: Confirm VNet and subnet exist with DNS configured

#### Step 1.5: Create Public IP
- **Action**: Create static public IP address
- **SKU**: Standard
- **Verification**: Confirm IP is allocated

#### Step 1.6: Create Network Interface
- **Action**: Create NIC with:
  - Public IP attached
  - NSG attached
  - Connected to VNet/subnet
- **Verification**: Confirm NIC is created and configured

#### Step 1.7: Create Virtual Machine
- **Action**: Create Ubuntu 22.04 LTS VM
  - Size: Standard_B2s (2 vCPU, 4GB RAM)
  - Image: Ubuntu2204
  - SSH key: Use generated key
  - **IMPORTANT**: Enable System-Assigned Managed Identity during creation
- **Verification**: 
  - VM is running
  - Can SSH to VM
  - Managed Identity is enabled

### Phase 2: DNS Configuration (Critical - Do Early!)

#### Step 2.1: Configure systemd-resolved
- **Action**: Configure DNS on VM to use Azure DNS
  - Set primary DNS: `168.63.129.16` (Azure DNS)
  - Set fallback DNS: `8.8.8.8`, `8.8.4.4` (Google DNS)
  - Disable DNSSEC (can cause issues)
- **Commands**:
  ```bash
  sudo sed -i 's/#DNS=/DNS=168.63.129.16/' /etc/systemd/resolved.conf
  sudo sed -i 's/#FallbackDNS=/FallbackDNS=8.8.8.8 8.8.4.4/' /etc/systemd/resolved.conf
  sudo sed -i 's/#DNSSEC=yes/DNSSEC=no/' /etc/systemd/resolved.conf
  sudo systemctl restart systemd-resolved
  ```
- **Verification**: 
  - `resolvectl status` shows Azure DNS
  - `nslookup management.azure.com` succeeds
  - `dig management.azure.com` succeeds

#### Step 2.2: Test DNS Resolution
- **Action**: Verify DNS works from command line and Python
- **Tests**:
  ```bash
  # Command line
  nslookup management.azure.com
  dig management.azure.com
  
  # Python
  python3 -c "import socket; print(socket.gethostbyname('management.azure.com'))"
  ```
- **Verification**: All tests succeed

### Phase 3: System Setup

#### Step 3.1: Update System Packages
- **Action**: Update and upgrade Ubuntu packages
- **Command**: `sudo apt-get update && sudo apt-get upgrade -y`
- **Verification**: Packages updated

#### Step 3.2: Install Base Dependencies
- **Action**: Install required system packages
  - Python 3.11 and venv
  - pip
  - git
  - sqlite3
  - nginx
  - certbot (for SSL)
- **Command**: `sudo apt-get install -y python3.11 python3.11-venv python3-pip git sqlite3 nginx certbot python3-certbot-nginx`
- **Verification**: All packages installed

#### Step 3.3: Create Service User
- **Action**: Create dedicated user `bragi` for running the application
- **Command**: `sudo useradd -r -s /bin/bash -d /opt/bragi-builder bragi`
- **Verification**: User exists

#### Step 3.4: Create Application Directory
- **Action**: Create `/opt/bragi-builder` with correct ownership
- **Command**: `sudo mkdir -p /opt/bragi-builder && sudo chown bragi:bragi /opt/bragi-builder`
- **Verification**: Directory exists with correct ownership

### Phase 4: Application Deployment

#### Step 4.1: Clone Repository
- **Action**: Clone application from Git repository
- **Command**: `sudo -u bragi git clone https://github.com/buxtonbluecat/bragi-builder.git /opt/bragi-builder`
- **Verification**: Files are present

#### Step 4.2: Create Virtual Environment
- **Action**: Create Python virtual environment
- **Command**: `sudo -u bragi python3.11 -m venv /opt/bragi-builder/venv`
- **Verification**: venv directory exists

#### Step 4.3: Install Python Dependencies
- **Action**: Install all required Python packages
- **Command**: 
  ```bash
  sudo -u bragi /opt/bragi-builder/venv/bin/pip install --upgrade pip
  sudo -u bragi /opt/bragi-builder/venv/bin/pip install -r /opt/bragi-builder/requirements.txt
  ```
- **Verification**: 
  - No errors during installation
  - gunicorn is installed
  - All dependencies are present

#### Step 4.4: Configure Application Environment
- **Action**: Set environment variables
  - `AZURE_SUBSCRIPTION_ID`: `693bb5f4-bea9-4714-b990-55d5a4032ae1`
  - `PORT`: `8080`
  - `FLASK_ENV`: `production`
- **Verification**: Environment variables are set

### Phase 5: Service Configuration

#### Step 5.1: Create systemd Service
- **Action**: Create systemd service file for Gunicorn
- **Key Points**:
  - Use `sync` worker class instead of `eventlet` (avoids DNS issues)
  - Set appropriate timeouts
  - Run as `bragi` user
  - Auto-restart on failure
- **Service File**: `/etc/systemd/system/bragi-builder.service`
- **Verification**: Service file is created correctly

#### Step 5.2: Configure Nginx
- **Action**: Configure Nginx as reverse proxy
- **Key Points**:
  - Proxy to `127.0.0.1:8080`
  - Support WebSockets
  - Set proper headers
- **Config File**: `/etc/nginx/sites-available/bragi-builder`
- **Verification**: 
  - Config syntax is valid (`sudo nginx -t`)
  - Symlink to sites-enabled exists

#### Step 5.3: Enable and Start Services
- **Action**: Enable and start both services
- **Commands**:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable bragi-builder
  sudo systemctl enable nginx
  sudo systemctl start bragi-builder
  sudo systemctl start nginx
  ```
- **Verification**: 
  - Both services are running
  - No errors in logs

### Phase 6: Azure Authentication Setup

#### Step 6.1: Verify Managed Identity
- **Action**: Confirm Managed Identity is enabled on VM
- **Command**: `az vm identity show --resource-group bb-test-rc --name bragi-builder-vm`
- **Verification**: Managed Identity principal ID is returned

#### Step 6.2: Grant Permissions
- **Action**: Grant Reader role at subscription level
- **Command**: 
  ```bash
  PRINCIPAL_ID=$(az vm identity show --resource-group bb-test-rc --name bragi-builder-vm --query principalId -o tsv)
  az role assignment create \
    --assignee-object-id $PRINCIPAL_ID \
    --role "Reader" \
    --scope "/subscriptions/693bb5f4-bea9-4714-b990-55d5a4032ae1"
  ```
- **Verification**: Role assignment exists

#### Step 6.3: Test Managed Identity Access
- **Action**: Verify Managed Identity can access Azure APIs
- **Test**: Use IMDS endpoint to get access token
- **Command**: 
  ```bash
  curl -H "Metadata:true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"
  ```
- **Verification**: Access token is returned

### Phase 7: Testing and Validation

#### Step 7.1: Test Application Health
- **Action**: Verify application is responding
- **Test**: `curl http://<VM_IP>/health`
- **Expected**: JSON response with `"status": "healthy"`
- **Verification**: Health endpoint responds correctly

#### Step 7.2: Test DNS Resolution from Application
- **Action**: Verify DNS works from within application context
- **Test**: `curl http://<VM_IP>/debug/dns`
- **Expected**: All DNS tests succeed
- **Verification**: No DNS timeouts

#### Step 7.3: Test Azure API Access
- **Action**: Verify application can access Azure APIs
- **Test**: `curl http://<VM_IP>/resource-groups`
- **Expected**: JSON response with resource groups list
- **Verification**: No authentication or DNS errors

#### Step 7.4: Test Web Interface
- **Action**: Access application in browser
- **URL**: `http://<VM_IP>`
- **Tests**:
  - Home page loads
  - Environments page loads
  - Resource groups are listed
  - No console errors
- **Verification**: All pages work correctly

#### Step 7.5: Check Application Logs
- **Action**: Review application logs for errors
- **Command**: `sudo journalctl -u bragi-builder -n 50 --no-pager`
- **Verification**: No critical errors

### Phase 8: Post-Deployment Configuration (Optional)

#### Step 8.1: SSL Certificate (Optional)
- **Action**: Configure SSL certificate with Let's Encrypt
- **Command**: `sudo certbot --nginx -d <your-domain>`
- **Verification**: HTTPS works

#### Step 8.2: Firewall Hardening (Optional)
- **Action**: Review and tighten NSG rules
- **Verification**: Only necessary ports are open

## Key Improvements from Previous Deployments

1. **DNS Configuration Early**: Configure DNS immediately after VM creation, before application deployment
2. **Use Sync Workers**: Changed from `eventlet` to `sync` worker class to avoid DNS resolution issues
3. **Managed Identity at Creation**: Enable Managed Identity during VM creation, not after
4. **Comprehensive Testing**: Test DNS resolution at multiple stages
5. **Better Error Handling**: Improved error messages to avoid HTML-like content in JSON responses

## Troubleshooting Checklist

If issues occur, check:
- [ ] DNS resolution works from command line
- [ ] DNS resolution works from Python
- [ ] Managed Identity is enabled and has permissions
- [ ] Application service is running
- [ ] Nginx is running and proxying correctly
- [ ] Network Security Group allows required ports
- [ ] Application logs show no errors
- [ ] Virtual environment has all dependencies installed

## Rollback Plan

If deployment fails:
1. Stop services: `sudo systemctl stop bragi-builder nginx`
2. Review logs: `sudo journalctl -u bragi-builder -n 100`
3. Fix issues and restart services
4. If needed, delete VM and start over: `az vm delete --resource-group bb-test-rc --name bragi-builder-vm --yes`

## Estimated Time

- Phase 1 (Infrastructure): 5-10 minutes
- Phase 2 (DNS): 2-3 minutes
- Phase 3 (System Setup): 5-10 minutes
- Phase 4 (Application): 5-10 minutes
- Phase 5 (Services): 2-3 minutes
- Phase 6 (Authentication): 2-3 minutes
- Phase 7 (Testing): 5-10 minutes
- **Total**: ~30-50 minutes

## Next Steps After Deployment

1. Monitor application logs for first 24 hours
2. Set up log aggregation (optional)
3. Configure backup for SQLite database (optional)
4. Set up monitoring and alerts (optional)
5. Document any custom configurations
