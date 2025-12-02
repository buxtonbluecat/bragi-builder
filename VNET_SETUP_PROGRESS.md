# VNet Integration Setup Progress

## ✅ Completed Steps

1. **VNet Created**: `bragi-containerapps-vnet`
   - Address Space: `10.3.0.0/16`
   - Location: UK South
   - Resource Group: `bb-test-rc`

2. **Subnet Created**: `containerapps-subnet`
   - Address Prefix: `10.3.0.0/24`
   - Delegated to: `Microsoft.App/environments`

3. **DNS Configuration**: 
   - DNS Server: `168.63.129.16` (Azure DNS resolver)
   - Configured on VNet

4. **New Environment Created**: `bragi-env-v3`
   - Integrated with VNet
   - Status: Provisioning (Waiting)

## ⏳ Current Status

The Container Apps environment `bragi-env-v3` is currently provisioning. VNet integration can take 10-15 minutes to complete.

**Check status:**
```bash
az containerapp env show --name bragi-env-v3 --resource-group bb-test-rc --query "properties.provisioningState" -o tsv
```

## 📋 Next Steps (After Environment is Ready)

1. **Deploy Container App to new environment:**
```bash
RESOURCE_GROUP="bb-test-rc"
APP_NAME="bragi-builder-ca"
ENVIRONMENT="bragi-env-v3"
ACR_NAME="bragibuilderacr"
SUBSCRIPTION_ID="693bb5f4-bea9-4714-b990-55d5a4032ae1"

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query 'passwords[0].value' -o tsv)

# Update Container App to use new environment
az containerapp update \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $ENVIRONMENT \
    --image ${ACR_LOGIN_SERVER}/bragi-builder:latest \
    --env-vars "PORT=8000" "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
```

2. **Test DNS Resolution:**
```bash
APP_URL=$(az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)
curl "https://${APP_URL}/debug/dns"
```

3. **Test Azure API Calls:**
```bash
curl "https://${APP_URL}/resource-groups"
```

## 🔄 Rollback Plan

If needed, you can continue using the old environment (`bragi-env-v2`) by keeping the Container App pointing to it. The new environment can be deleted if not needed:

```bash
az containerapp env delete --name bragi-env-v3 --resource-group bb-test-rc --yes
```

## 📝 Notes

- The old environment (`bragi-env-v2`) remains available and functional
- The Container App (`bragi-builder-ca`) is currently still using `bragi-env-v2`
- Once the new environment is ready, we'll update the Container App to use it
- VNet integration should resolve the DNS resolution issues
