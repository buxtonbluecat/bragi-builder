#!/bin/bash
# Docker-based deployment script for Azure App Service

set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-bb-test-rc}"
APP_NAME="${APP_NAME:-bb-test-app}"
LOCATION="${LOCATION:-uksouth}"
ACR_NAME="${ACR_NAME:-bragibuilderacr}"

echo "🐳 Docker-based Deployment to Azure App Service"
echo "================================================"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first."
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install it first."
    exit 1
fi

# Login to Azure
echo "🔐 Logging into Azure..."
az account show &> /dev/null || az login

# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "✓ Using subscription: $SUBSCRIPTION_ID"
echo ""

# Create Azure Container Registry if it doesn't exist
echo "📦 Checking Azure Container Registry..."
if ! az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "Creating ACR: $ACR_NAME..."
    az acr create \
        --name $ACR_NAME \
        --resource-group $RESOURCE_GROUP \
        --sku Basic \
        --admin-enabled true
    echo "✓ ACR created"
else
    echo "✓ ACR exists"
fi
echo ""

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
echo "ACR Login Server: $ACR_LOGIN_SERVER"
echo ""

# Login to ACR
echo "🔐 Logging into ACR..."
az acr login --name $ACR_NAME
echo ""

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t $ACR_LOGIN_SERVER/bragi-builder:latest .
echo ""

# Push image to ACR
echo "📤 Pushing image to ACR..."
docker push $ACR_LOGIN_SERVER/bragi-builder:latest
echo ""

# Update App Service to use Docker image
echo "⚙️  Configuring App Service to use Docker image..."
az webapp config container set \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --docker-custom-image-name $ACR_LOGIN_SERVER/bragi-builder:latest \
    --docker-registry-server-url https://$ACR_LOGIN_SERVER \
    --docker-registry-server-user $(az acr credential show --name $ACR_NAME --query username -o tsv) \
    --docker-registry-server-password $(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
echo ""

# Set port
echo "🔧 Setting port configuration..."
az webapp config appsettings set \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings PORT=8000 WEBSITES_PORT=8000
echo ""

# Restart app
echo "🔄 Restarting app..."
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
echo ""

echo "✅ Deployment complete!"
echo ""
echo "App URL: https://${APP_NAME}.azurewebsites.net"
echo ""
echo "To view logs:"
echo "  az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"




