#!/bin/bash
# Bragi Builder - VM Deployment Script
# Deploys the application to an Azure Linux VM

set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-bb-test-rc}"
VM_NAME="${VM_NAME:-bragi-builder-vm}"
LOCATION="${LOCATION:-uksouth}"
VM_SIZE="${VM_SIZE:-Standard_B2s}"  # 2 vCPU, 4GB RAM
ADMIN_USERNAME="${ADMIN_USERNAME:-azureuser}"
IMAGE="${IMAGE:-Ubuntu2204}"  # Ubuntu 22.04 LTS

echo "🚀 Bragi Builder - VM Deployment"
echo "=================================="
echo ""
echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  VM Name: $VM_NAME"
echo "  Location: $LOCATION"
echo "  VM Size: $VM_SIZE"
echo "  Image: $IMAGE"
echo ""

# Login to Azure
az account show &> /dev/null || az login

# Create resource group if it doesn't exist
if ! az group show --name $RESOURCE_GROUP &> /dev/null; then
    echo "Creating resource group: $RESOURCE_GROUP..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
fi

# Generate SSH key if it doesn't exist
SSH_KEY_PATH="$HOME/.ssh/id_rsa_bragi"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -f $SSH_KEY_PATH -N "" -C "bragi-builder-vm"
fi

# Create NSG with rules for SSH and HTTP/HTTPS
echo "Creating Network Security Group..."
az network nsg create \
    --resource-group $RESOURCE_GROUP \
    --name ${VM_NAME}-nsg \
    --location $LOCATION

az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name ${VM_NAME}-nsg \
    --name AllowSSH \
    --priority 1000 \
    --protocol Tcp \
    --destination-port-ranges 22 \
    --access Allow

az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name ${VM_NAME}-nsg \
    --name AllowHTTP \
    --priority 1001 \
    --protocol Tcp \
    --destination-port-ranges 80 \
    --access Allow

az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name ${VM_NAME}-nsg \
    --name AllowHTTPS \
    --priority 1002 \
    --protocol Tcp \
    --destination-port-ranges 443 \
    --access Allow

az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name ${VM_NAME}-nsg \
    --name AllowAppPort \
    --priority 1003 \
    --protocol Tcp \
    --destination-port-ranges 8080 \
    --access Allow

# Create public IP
echo "Creating public IP..."
az network public-ip create \
    --resource-group $RESOURCE_GROUP \
    --name ${VM_NAME}-ip \
    --allocation-method Static \
    --sku Standard

# Create VNet and subnet (or use existing)
VNET_NAME="${VM_NAME}-vnet"
SUBNET_NAME="${VM_NAME}-subnet"

if ! az network vnet show --resource-group $RESOURCE_GROUP --name $VNET_NAME &> /dev/null; then
    echo "Creating VNet..."
    az network vnet create \
        --resource-group $RESOURCE_GROUP \
        --name $VNET_NAME \
        --address-prefix 10.4.0.0/16 \
        --subnet-name $SUBNET_NAME \
        --subnet-prefix 10.4.0.0/24 \
        --location $LOCATION
fi

# Create NIC
echo "Creating network interface..."
az network nic create \
    --resource-group $RESOURCE_GROUP \
    --name ${VM_NAME}-nic \
    --vnet-name $VNET_NAME \
    --subnet $SUBNET_NAME \
    --public-ip-address ${VM_NAME}-ip \
    --network-security-group ${VM_NAME}-nsg

# Create VM
echo "Creating VM..."
az vm create \
    --resource-group $RESOURCE_GROUP \
    --name $VM_NAME \
    --image $IMAGE \
    --size $VM_SIZE \
    --admin-username $ADMIN_USERNAME \
    --ssh-key-values $SSH_KEY_PATH.pub \
    --nics ${VM_NAME}-nic \
    --public-ip-sku Standard

# Get VM IP
VM_IP=$(az vm show -d --resource-group $RESOURCE_GROUP --name $VM_NAME --query publicIps -o tsv)
echo ""
echo "✅ VM created successfully!"
echo "  VM IP: $VM_IP"
echo "  SSH: ssh -i $SSH_KEY_PATH $ADMIN_USERNAME@$VM_IP"
echo ""
echo "Next steps:"
echo "  1. Run setup-vm.sh to install dependencies and deploy the app"
echo "  2. Or manually SSH and run the setup script"
