#!/bin/bash
# Azure Container Apps deployment script

set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-bb-test-rc}"
APP_NAME="${APP_NAME:-bragi-builder-ca}"
LOCATION="${LOCATION:-uksouth}"
ACR_NAME="${ACR_NAME:-bragibuilderacr}"
ENVIRONMENT="${ENVIRONMENT:-bragi-env}"

echo "🚀 Azure Container Apps Deployment"
echo "=================================="
echo ""

# Login to Azure
az account show &> /dev/null || az login

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv 2>/dev/null || echo "")

if [ -z "$ACR_LOGIN_SERVER" ]; then
    echo "Creating ACR: $ACR_NAME..."
    az acr create \
        --name $ACR_NAME \
        --resource-group $RESOURCE_GROUP \
        --sku Basic \
        --admin-enabled true
    ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
fi

echo "ACR: $ACR_LOGIN_SERVER"
echo ""

# Build and push Docker image
echo "🔨 Building and pushing Docker image..."
az acr build --registry $ACR_NAME --image bragi-builder:latest .
echo ""

# Create Container Apps environment if it doesn't exist
echo "🌍 Creating Container Apps environment..."
if ! az containerapp env show --name $ENVIRONMENT --resource-group $RESOURCE_GROUP &> /dev/null; then
    az containerapp env create \
        --name $ENVIRONMENT \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION
fi
echo ""

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Create or update Container App
echo "📦 Creating/updating Container App..."
az containerapp create \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $ENVIRONMENT \
    --image $ACR_LOGIN_SERVER/bragi-builder:latest \
    --registry-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --target-port 8000 \
    --ingress external \
    --cpu 1.0 \
    --memory 2.0Gi \
    --min-replicas 1 \
    --max-replicas 3 \
    --env-vars PORT=8000 \
    || az containerapp update \
        --name $APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --image $ACR_LOGIN_SERVER/bragi-builder:latest
echo ""

# Get app URL
APP_URL=$(az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)
echo "✅ Deployment complete!"
echo ""
echo "App URL: https://${APP_URL}"
echo ""
echo "To view logs:"
echo "  az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow"


