# Network Configuration Analysis

## Current Container Apps Network Configuration

### Environment: `bragi-env-v2`
- **Public Network Access**: Enabled
- **VNet Integration**: Not configured (null)
- **Custom DNS Servers**: None configured
- **Static IP**: 145.133.67.157

### Container App: `bragi-builder-ca`
- **Outbound IPs**: Multiple (20.108.216.9, 20.108.217.125, 74.177.201.70, etc.)
- **Inbound IP**: Via ingress FQDN
- **DNS Resolution**: Using Azure default DNS (failing)

## Problem

DNS resolution is completely failing for all domains:
- `management.azure.com` - timeout
- `login.microsoftonline.com` - timeout  
- `google.com` - timeout

This suggests Azure's default DNS resolver is not accessible or not working properly.

## Solution Options

### Option 1: VNet Integration with Azure DNS (Recommended)

**Steps:**
1. Create a VNet and subnet for Container Apps
2. Configure VNet DNS servers to use Azure DNS (`168.63.129.16`)
3. Integrate Container Apps environment with VNet
4. Ensure NSG rules allow DNS traffic (port 53) to `168.63.129.16`

**Benefits:**
- Explicit DNS control
- Can troubleshoot DNS issues more easily
- Better network isolation if needed

**Commands:**
```bash
# Create VNet
az network vnet create \
    --resource-group bb-test-rc \
    --name bragi-vnet \
    --address-prefix 10.0.0.0/16 \
    --subnet-name containerapps-subnet \
    --subnet-prefix 10.0.1.0/24

# Configure DNS servers
az network vnet update \
    --resource-group bb-test-rc \
    --name bragi-vnet \
    --dns-servers 168.63.129.16

# Update Container Apps environment with VNet
az containerapp env update \
    --name bragi-env-v2 \
    --resource-group bb-test-rc \
    --infrastructure-subnet-resource-id /subscriptions/693bb5f4-bea9-4714-b990-55d5a4032ae1/resourceGroups/bb-test-rc/providers/Microsoft.Network/virtualNetworks/bragi-vnet/subnets/containerapps-subnet
```

### Option 2: Check DNS Connectivity

Test if Azure DNS resolver is reachable from the container:
- Add endpoint to test connectivity to `168.63.129.16:53`
- Check if DNS queries work when using explicit DNS server

### Option 3: Different Region

Create environment in different region to see if it's region-specific DNS issue.

## Next Steps

1. **Immediate**: Test if DNS issue persists (may be transient)
2. **Short-term**: Set up VNet integration with Azure DNS
3. **Long-term**: Consider if VNet integration is needed for other reasons (private endpoints, etc.)
