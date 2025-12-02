# VNet Integration Impact Analysis

## Current Resources in `bb-test-rc` Resource Group

### Bragi Builder Resources:
- ✅ `bragi-env-v2` - Container Apps Environment
- ✅ `bragi-builder-ca` - Container App
- ✅ `bragibuilderacr` - Azure Container Registry
- ✅ `bb-test-plan` - App Service Plan
- ✅ `bb-test-app` - App Service
- ✅ Multiple Log Analytics workspaces (auto-created)

### Existing VNets:
- ❌ **No VNets in `bb-test-rc` resource group**
- ℹ️ **Separate VNet exists**: `optbragivnet` in `opt_bragi` resource group (unrelated)

## Impact Assessment: ✅ SAFE TO PROCEED

### ✅ What WILL Be Affected:
1. **Container Apps Environment (`bragi-env-v2`)**:
   - Will be integrated with new VNet
   - DNS configuration will change to use Azure DNS resolver
   - Should resolve DNS issues

2. **Container App (`bragi-builder-ca`)**:
   - Will use VNet for outbound traffic
   - DNS resolution will use configured DNS servers
   - No downtime expected (seamless integration)

### ✅ What WILL NOT Be Affected:
1. **Other Resource Groups**: 
   - VNet will be created in `bb-test-rc` only
   - No impact on other resource groups or subscriptions

2. **Existing App Service (`bb-test-app`)**:
   - App Service is separate from Container Apps
   - Will continue to work independently
   - Can optionally integrate later if needed

3. **Azure Container Registry (`bragibuilderacr`)**:
   - ACR is independent of Container Apps networking
   - Will continue to work normally
   - Container Apps can pull images via public endpoint or private endpoint (if configured)

4. **Other Azure Resources**:
   - No impact on resources outside `bb-test-rc`
   - No impact on `optbragivnet` or other VNets
   - No impact on other subscriptions or tenants

5. **Log Analytics Workspaces**:
   - These are independent services
   - No network dependency on Container Apps VNet

## Proposed VNet Configuration

### Address Space:
- **VNet**: `10.1.0.0/16` (different from template defaults of `10.0.0.0/16` to avoid confusion)
- **Subnet**: `10.1.0.0/24` (dedicated for Container Apps)

### DNS Configuration:
- **Primary DNS**: `168.63.129.16` (Azure DNS resolver)
- This ensures proper resolution of Azure services and external domains

### Network Isolation:
- VNet is isolated to Container Apps environment
- No peering or connections to other VNets
- No impact on existing network infrastructure

## Rollback Plan

If issues occur, VNet integration can be removed:
```bash
az containerapp env update \
    --name bragi-env-v2 \
    --resource-group bb-test-rc \
    --infrastructure-subnet-resource-id ""
```

This will revert to public network access (current state).

## Recommendation

✅ **SAFE TO PROCEED** - VNet integration is isolated to Container Apps and will not affect:
- Other resource groups
- Other VNets
- Existing App Service
- ACR
- Any other Azure resources

The VNet will be created specifically for Container Apps DNS resolution and will be completely isolated.
