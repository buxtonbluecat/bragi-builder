#!/bin/bash
# Bragi Builder - Azure App Service Deployment Script
# This script deploys the application to Azure App Service

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - Update these values
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-bragi-builder-rg}"
APP_SERVICE_NAME="${AZURE_APP_SERVICE_NAME:-bragi-builder}"
APP_SERVICE_PLAN="${AZURE_APP_SERVICE_PLAN:-bragi-plan}"
LOCATION="${AZURE_LOCATION:-eastus}"
SKU="${AZURE_SKU:-B1}"

echo -e "${GREEN}🚀 Bragi Builder - Azure App Service Deployment${NC}"
echo "=========================================="
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed. Please install it first.${NC}"
    echo "Visit: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in to Azure
echo -e "${YELLOW}Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Not logged in. Please log in to Azure...${NC}"
    az login
fi

# Get current subscription
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo -e "${GREEN}✓ Using subscription: ${SUBSCRIPTION_ID}${NC}"
echo ""

# Create resource group if it doesn't exist
echo -e "${YELLOW}Checking resource group...${NC}"
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}Creating resource group: ${RESOURCE_GROUP}...${NC}"
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    echo -e "${GREEN}✓ Resource group created${NC}"
else
    echo -e "${GREEN}✓ Resource group exists${NC}"
fi
echo ""

# Create App Service Plan if it doesn't exist
echo -e "${YELLOW}Checking App Service Plan...${NC}"
if ! az appservice plan show --name "$APP_SERVICE_PLAN" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}Creating App Service Plan: ${APP_SERVICE_PLAN}...${NC}"
    az appservice plan create \
        --name "$APP_SERVICE_PLAN" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku "$SKU" \
        --is-linux
    echo -e "${GREEN}✓ App Service Plan created${NC}"
else
    echo -e "${GREEN}✓ App Service Plan exists${NC}"
fi
echo ""

# Create App Service if it doesn't exist
echo -e "${YELLOW}Checking App Service...${NC}"
if ! az webapp show --name "$APP_SERVICE_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}Creating App Service: ${APP_SERVICE_NAME}...${NC}"
    az webapp create \
        --name "$APP_SERVICE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --plan "$APP_SERVICE_PLAN" \
        --runtime "PYTHON:3.11"
    echo -e "${GREEN}✓ App Service created${NC}"
else
    echo -e "${GREEN}✓ App Service exists${NC}"
fi
echo ""

# Configure App Service settings
echo -e "${YELLOW}Configuring App Service...${NC}"

# Enable WebSocket support
az webapp config set \
    --name "$APP_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --web-sockets-enabled true

# Set startup command
az webapp config set \
    --name "$APP_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --startup-file "startup.sh"

# Configure Python version
az webapp config appsettings set \
    --name "$APP_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        ENABLE_ORYX_BUILD=true \
        PYTHON_VERSION=3.11

echo -e "${GREEN}✓ App Service configured${NC}"
echo ""

# Enable Managed Identity
echo -e "${YELLOW}Enabling Managed Identity...${NC}"
IDENTITY_ID=$(az webapp identity assign \
    --name "$APP_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query principalId -o tsv)
echo -e "${GREEN}✓ Managed Identity enabled: ${IDENTITY_ID}${NC}"
echo ""

# Deploy the application
echo -e "${YELLOW}Deploying application...${NC}"
echo "This may take a few minutes..."
az webapp up \
    --name "$APP_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --runtime "PYTHON:3.11" \
    --logs

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "App URL: https://${APP_SERVICE_NAME}.azurewebsites.net"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Configure environment variables in Azure Portal"
echo "2. Set up Azure AD authentication"
echo "3. Configure Azure Files mount for SQLite (if needed)"
echo "4. Grant Managed Identity permissions to access Azure resources"
echo ""
echo "To view logs:"
echo "  az webapp log tail --name $APP_SERVICE_NAME --resource-group $RESOURCE_GROUP"


