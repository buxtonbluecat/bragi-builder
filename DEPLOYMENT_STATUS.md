# Bragi Builder - Azure Container Apps Deployment Status

**Last Updated:** 2025-12-01

## ✅ Deployment Complete - Environment Recreated

### What's Working
1. **Container Apps Environment**: `bragi-env-v2` - Created successfully
2. **Container App**: `bragi-builder-ca` - Running and healthy
3. **Docker Image**: Built for AMD64, pushed to ACR (`bragibuilderacr.azurecr.io/bragi-builder:latest`)
4. **Managed Identity**: Enabled (Principal ID: `0adbd678-2687-4da0-8346-8ba2141964f5`)
5. **Permissions**: Reader role granted at subscription scope ✅
6. **Application Health**: Health endpoint responding successfully
7. **Container Runtime**: Gunicorn running with eventlet workers
8. **Environment Variables**: `PORT=8000`, `AZURE_SUBSCRIPTION_ID` set correctly
9. **Revision Status**: Healthy and active

### ❌ Critical Issue: Complete DNS Resolution Failure

**Problem**: Container cannot resolve **ANY** DNS names, including:
- `management.azure.com` (Azure APIs)
- `login.microsoftonline.com` (Authentication)
- `google.com` (General internet)

**Error**: 
```
[Errno -3] Lookup timed out
```

**Impact**: 
- Cannot make any outbound network calls requiring DNS
- Cannot list resource groups
- Cannot access Azure management APIs
- Cannot authenticate (even with service principal)
- All Azure SDK operations fail

**Root Cause**: Complete DNS resolution failure in Container Apps environment - appears to be a platform-level issue.

**Network Configuration**:
- `publicNetworkAccess`: Enabled
- `vnetConfiguration`: null (no VNet integration)
- `staticIp`: 145.133.67.157

## Infrastructure Details

| Component | Value |
|-----------|-------|
| **Resource Group** | `bb-test-rc` |
| **Container App** | `bragi-builder-ca` |
| **Environment** | `bragi-env-v2` |
| **Location** | UK South |
| **ACR** | `bragibuilderacr.azurecr.io` |
| **Image** | `bragibuilderacr.azurecr.io/bragi-builder:latest` |
| **URL** | `https://bragi-builder-ca.proudstone-681971d8.uksouth.azurecontainerapps.io` |
| **Managed Identity** | System-assigned (enabled) |
| **Principal ID** | `0adbd678-2687-4da0-8346-8ba2141964f5` |
| **Role Assignment** | Reader on subscription ✅ |
| **Revision** | `bragi-builder-ca--z3wxjfp` (Healthy) |

## Next Steps

### Option 1: Wait and Retry (Recommended First Step)
DNS failures can be temporary Azure platform issues. Wait 15-30 minutes and test again:

```bash
APP_URL="bragi-builder-ca.proudstone-681971d8.uksouth.azurecontainerapps.io"
curl "https://${APP_URL}/debug/dns"
```

### Option 2: Try Different Region
Create a new environment in a different Azure region (e.g., `eastus`, `westus2`) to see if it's region-specific:

```bash
az containerapp env create \
    --name bragi-env-v3 \
    --resource-group bb-test-rc \
    --location eastus
```

### Option 3: Configure Custom DNS (If VNet Integration)
If you need VNet integration, configure Azure DNS (`168.63.129.16`) as the DNS server.

### Option 4: Contact Azure Support
This appears to be a platform-level DNS issue. Contact Azure support with:
- Environment name: `bragi-env-v2`
- Resource group: `bb-test-rc`
- Static IP: `145.133.67.157`
- Issue: Complete DNS resolution failure (all domains timing out)

## Testing Commands

```bash
# Get current URL
APP_URL=$(az containerapp show \
    --name bragi-builder-ca \
    --resource-group bb-test-rc \
    --query "properties.configuration.ingress.fqdn" -o tsv)

# Test health endpoint (should work)
curl "https://${APP_URL}/health"

# Test DNS resolution from inside container
curl "https://${APP_URL}/debug/dns"

# Test resource groups endpoint (will fail due to DNS)
curl "https://${APP_URL}/resource-groups"

# View logs
az containerapp logs show \
    --name bragi-builder-ca \
    --resource-group bb-test-rc \
    --follow

# Check managed identity
az containerapp identity show \
    --name bragi-builder-ca \
    --resource-group bb-test-rc

# Check role assignments
az role assignment list \
    --assignee 0adbd678-2687-4da0-8346-8ba2141964f5 \
    --scope "/subscriptions/693bb5f4-bea9-4714-b990-55d5a4032ae1"
```

## Files Modified

- ✅ `src/azure_client.py` - Added ManagedIdentityCredential support
- ✅ `app.py` - Added `/health` and `/debug/dns` endpoints
- ✅ `deploy-container-apps.sh` - Updated deployment script
- ✅ `Dockerfile` - Uses entrypoint script for PORT handling
- ✅ `docker-entrypoint.sh` - Handles PORT environment variable

## Code Changes Summary

### Authentication Flow
1. **Service Principal** (if env vars set) → `ClientSecretCredential`
2. **Managed Identity** (in Azure) → `DefaultAzureCredential` → `ManagedIdentityCredential`
3. **Azure CLI** (local dev) → `DefaultAzureCredential` → `AzureCliCredential`

### Environment Variables Required
- `AZURE_SUBSCRIPTION_ID` - ✅ Set (`693bb5f4-bea9-4714-b990-55d5a4032ae1`)
- `AZURE_CLIENT_ID` - Optional (for service principal)
- `AZURE_CLIENT_SECRET` - Optional (for service principal)
- `AZURE_TENANT_ID` - Optional (for service principal)
- `PORT` - ✅ Set to 8000

## Notes

- ✅ Application code is ready and deployed correctly
- ✅ Managed identity authentication is configured correctly
- ✅ Permissions are granted correctly
- ✅ Container is running and healthy
- ❌ **DNS resolution is completely broken** - this is blocking all network operations
- ⏳ This appears to be an Azure Container Apps platform issue
- 🔍 Consider trying a different region or contacting Azure support

## Quick Reference

**Current URL**: `https://bragi-builder-ca.proudstone-681971d8.uksouth.azurecontainerapps.io`

**Resource Group**: `bb-test-rc`

**Environment**: `bragi-env-v2`

**Subscription ID**: `693bb5f4-bea9-4714-b990-55d5a4032ae1`

**Tenant ID**: `ccebb17e-cbf7-4aa3-b2ab-8e65565864a0`

**Managed Identity Principal ID**: `0adbd678-2687-4da0-8346-8ba2141964f5`

