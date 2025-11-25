# Azure App Service Deployment Guide

This guide walks you through deploying Bragi Builder to Azure App Service with Azure AD authentication.

## Prerequisites

1. **Azure CLI** installed and configured
   ```bash
   az --version  # Verify installation
   az login     # Login to Azure
   ```

2. **Azure Subscription** with appropriate permissions

3. **Azure AD Tenant** access (for app registration)

## Step 1: Register Azure AD Application

### 1.1 Create App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Fill in:
   - **Name**: `Bragi Builder`
   - **Supported account types**: Single tenant (or multi-tenant if needed)
   - **Redirect URI**: 
     - Platform: Web
     - URI: `http://localhost:8080/login/authorized` (for local dev)
5. Click **Register**

### 1.2 Configure Authentication

1. In your app registration, go to **Authentication**
2. Under **Platform configurations**, click **Add a platform** → **Web**
3. Add redirect URIs:
   - `http://localhost:8080/login/authorized` (local development)
   - `https://your-app-name.azurewebsites.net/login/authorized` (production - update after deployment)
4. Under **Implicit grant and hybrid flows**, enable **ID tokens**
5. Click **Save**

### 1.3 Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add description: `Bragi Builder Secret`
4. Set expiration (recommend 12-24 months)
5. Click **Add**
6. **IMPORTANT**: Copy the secret value immediately (you won't see it again!)

### 1.4 Note Required Values

Save these values for later:
- **Tenant ID** (Directory ID) - Found in Overview
- **Application (client) ID** - Found in Overview
- **Client Secret Value** - From step 1.3

## Step 2: Deploy to Azure App Service

### 2.1 Quick Deployment (Using deploy.sh)

```bash
# Set environment variables (optional, or edit deploy.sh)
export AZURE_RESOURCE_GROUP="bragi-builder-rg"
export AZURE_APP_SERVICE_NAME="bragi-builder"
export AZURE_LOCATION="eastus"
export AZURE_SKU="B1"

# Run deployment script
./deploy.sh
```

The script will:
- Create resource group (if needed)
- Create App Service Plan (if needed)
- Create App Service (if needed)
- Enable Managed Identity
- Configure WebSocket support
- Deploy your application

### 2.2 Manual Deployment

If you prefer manual steps:

```bash
# 1. Create resource group
az group create --name bragi-builder-rg --location eastus

# 2. Create App Service Plan
az appservice plan create \
    --name bragi-plan \
    --resource-group bragi-builder-rg \
    --location eastus \
    --sku B1 \
    --is-linux

# 3. Create App Service
az webapp create \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --plan bragi-plan \
    --runtime "PYTHON:3.11"

# 4. Enable WebSocket
az webapp config set \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --web-sockets-enabled true

# 5. Set startup command
az webapp config set \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --startup-file "startup.sh"

# 6. Enable Managed Identity
az webapp identity assign \
    --name bragi-builder \
    --resource-group bragi-builder-rg

# 7. Deploy application
az webapp up \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --runtime "PYTHON:3.11"
```

## Step 3: Configure Environment Variables

### 3.1 Set Application Settings

```bash
az webapp config appsettings set \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --settings \
        AZURE_SUBSCRIPTION_ID="your-subscription-id" \
        AZURE_AD_TENANT_ID="your-tenant-id" \
        AZURE_AD_CLIENT_ID="your-azure-ad-client-id" \
        AZURE_AD_CLIENT_SECRET="your-azure-ad-client-secret" \
        AZURE_AD_REDIRECT_URI_PROD="https://bragi-builder.azurewebsites.net/login/authorized" \
        SECRET_KEY="generate-a-secure-random-secret-key" \
        FLASK_ENV="production"
```

**Important Notes:**
- Replace all placeholder values with your actual values
- Generate a secure `SECRET_KEY` (you can use: `python -c "import secrets; print(secrets.token_hex(32))"`)
- Update `AZURE_AD_REDIRECT_URI_PROD` with your actual App Service URL

### 3.2 Update Azure AD Redirect URI

1. Go back to Azure AD App Registration
2. Navigate to **Authentication**
3. Add production redirect URI: `https://your-app-name.azurewebsites.net/login/authorized`
4. Click **Save**

## Step 4: Configure Database Persistence (Optional)

### Option A: Azure Files (for SQLite)

If you want to keep using SQLite:

```bash
# 1. Create storage account
az storage account create \
    --name bragistorage \
    --resource-group bragi-builder-rg \
    --location eastus \
    --sku Standard_LRS

# 2. Create file share
az storage share create \
    --name bragi-data \
    --account-name bragistorage

# 3. Get storage account key
STORAGE_KEY=$(az storage account keys list \
    --resource-group bragi-builder-rg \
    --account-name bragistorage \
    --query "[0].value" -o tsv)

# 4. Mount Azure Files to App Service
az webapp config storage-account add \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --custom-id bragi-data \
    --storage-type AzureFiles \
    --share-name bragi-data \
    --account-name bragistorage \
    --access-key $STORAGE_KEY \
    --mount-path /home/data

# 5. Update app to use mounted path
az webapp config appsettings set \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --settings \
        DATABASE_PATH="/home/data/deployments.db"
```

Then update `src/deployment_store.py` to use the environment variable:
```python
db_path = os.getenv('DATABASE_PATH', 'deployments.db')
```

### Option B: Azure SQL Database (Recommended for Production)

For production, consider migrating to Azure SQL Database for better scalability and reliability.

## Step 5: Grant Managed Identity Permissions

The App Service Managed Identity needs permissions to manage Azure resources:

```bash
# Get the Managed Identity principal ID
PRINCIPAL_ID=$(az webapp identity show \
    --name bragi-builder \
    --resource-group bragi-builder-rg \
    --query principalId -o tsv)

# Grant Contributor role at subscription level (or resource group level)
az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Contributor" \
    --scope "/subscriptions/your-subscription-id"
```

**Note**: For production, use least privilege principle - grant only necessary permissions at resource group level.

## Step 6: Verify Deployment

1. **Check App Service Status**
   ```bash
   az webapp show --name bragi-builder --resource-group bragi-builder-rg --query state
   ```

2. **View Logs**
   ```bash
   az webapp log tail --name bragi-builder --resource-group bragi-builder-rg
   ```

3. **Test Application**
   - Open: `https://your-app-name.azurewebsites.net`
   - You should be redirected to Azure AD login
   - After login, you should see the dashboard

## Step 7: Continuous Deployment (Optional)

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure App Service

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Azure Login
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Deploy to App Service
      uses: azure/webapps-deploy@v2
      with:
        app-name: 'bragi-builder'
        package: .
```

## Troubleshooting

### Application Won't Start

1. **Check Logs**
   ```bash
   az webapp log tail --name bragi-builder --resource-group bragi-builder-rg
   ```

2. **Verify Startup Command**
   ```bash
   az webapp config show --name bragi-builder --resource-group bragi-builder-rg --query linuxFxVersion
   ```

3. **Check Environment Variables**
   ```bash
   az webapp config appsettings list --name bragi-builder --resource-group bragi-builder-rg
   ```

### Authentication Not Working

1. Verify redirect URIs match exactly in Azure AD
2. Check that `AZURE_AD_CLIENT_SECRET` is set correctly
3. Verify `AZURE_AD_TENANT_ID` and `AZURE_AD_CLIENT_ID` are correct
4. Check App Service logs for authentication errors

### WebSocket Issues

1. Verify WebSocket is enabled:
   ```bash
   az webapp config show --name bragi-builder --resource-group bragi-builder-rg --query webSocketsEnabled
   ```

2. Check that your client is using `wss://` (secure WebSocket) for production

## Security Best Practices

1. **Never commit secrets** - Use App Service Configuration for secrets
2. **Use Managed Identity** - Avoid storing service principal credentials
3. **Enable HTTPS only** - App Service does this by default
4. **Regular updates** - Keep dependencies updated
5. **Monitor access** - Use Azure AD audit logs
6. **Least privilege** - Grant minimum required permissions to Managed Identity

## Cost Optimization

- **App Service Plan**: Start with B1 (Basic) for development, scale up as needed
- **Storage**: Use Azure Files Standard_LRS for SQLite (cheap)
- **Consider**: Azure SQL Database Basic tier for production ($5/month)

## Next Steps

- Set up custom domain
- Configure Application Insights for monitoring
- Set up backup strategy
- Implement CI/CD pipeline
- Add staging environment

## Support

For issues or questions:
- Check application logs in Azure Portal
- Review Azure AD authentication logs
- Check App Service metrics and health

