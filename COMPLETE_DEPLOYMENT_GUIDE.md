# Bragi Builder - Complete End-to-End Deployment Guide

## Overview

Bragi Builder now supports complete end-to-end Azure infrastructure deployment with proper networking, security, and best practices. This guide covers the full deployment process from Resource Group creation to production-ready environments.

## 🏗️ **Complete Infrastructure Stack**

### **What Gets Deployed:**

#### **1. Resource Group**
- Automatically created for each environment
- Named: `{project}-{environment}-rg`
- Located in specified Azure region

#### **2. Virtual Network (VNet)**
- **Address Space**: 10.0.0.0/16
- **4 Subnets**:
  - **App Service Subnet**: 10.0.1.0/24 (delegated to Microsoft.Web/serverFarms)
  - **Database Subnet**: 10.0.2.0/24
  - **Storage Subnet**: 10.0.3.0/24
  - **Management Subnet**: 10.0.4.0/24

#### **3. App Service Infrastructure**
- **App Service Plan**: Linux-based hosting plan
- **App Service**: Web application with HTTPS enforcement
- **Security Features**:
  - HTTPS-only access
  - TLS 1.2 minimum version
  - FTP disabled
  - Detailed logging enabled

#### **4. Storage Infrastructure**
- **Storage Account**: Blob, file, table, and queue storage
- **Security Features**:
  - HTTPS-only access
  - TLS 1.2 minimum version
  - Public blob access disabled
  - Encryption enabled
  - Network access restricted to VNet

#### **5. Database Infrastructure**
- **SQL Server**: Database management system
- **Meta Database**: For application metadata
- **DWH Database**: For data warehouse operations
- **Security Features**:
  - Port 1433 configured for SQL access
  - Firewall rules for App Service subnet (10.0.1.0/24)
  - Firewall rules for Management subnet (10.0.4.0/24)
  - Azure Services access enabled

## 🚀 **Deployment Options**

### **1. Command Line Interface (CLI)**

#### **Basic Deployment:**
```bash
python3 cli.py deploy environment dev \
  --sql-password "YourSecurePassword123!" \
  --project-name "myapp"
```

#### **Custom Configuration:**
```bash
python3 cli.py deploy environment prod \
  --sql-password "YourSecurePassword123!" \
  --project-name "myapp" \
  --location "West Europe" \
  --app-service-sku "P1" \
  --sql-database-sku "P2" \
  --storage-sku "Standard_GRS" \
  --enable-public-access
```

#### **Available SKUs:**

**App Service SKUs:**
- `F1` - Free tier
- `B1`, `B2`, `B3` - Basic tier
- `S1`, `S2`, `S3` - Standard tier
- `P1`, `P2`, `P3` - Premium tier

**SQL Database SKUs:**
- `Basic` - Basic tier
- `S0`, `S1`, `S2`, `S3` - Standard tier
- `P1`, `P2`, `P4`, `P6`, `P11`, `P15` - Premium tier

**Storage SKUs:**
- `Standard_LRS` - Locally redundant storage
- `Standard_GRS` - Geo-redundant storage
- `Standard_RAGRS` - Read-access geo-redundant storage
- `Premium_LRS` - Premium locally redundant storage

### **2. Web Interface**

#### **Using Offline Review:**
1. Go to http://localhost:8080
2. Click "Offline Review"
3. Create a new session with environment and size
4. Add the "complete-environment" template
5. Configure parameters
6. Analyze costs and configuration
7. Export for deployment

#### **Using Template Wizard:**
1. Click "Template Wizard"
2. Create a new template
3. Add resources step by step:
   - Virtual Network
   - App Service Plan
   - App Service
   - Storage Account
   - SQL Server
   - SQL Databases
4. Configure parameters and outputs
5. Generate the template

### **3. Direct Template Deployment**

#### **Using Azure CLI:**
```bash
az deployment group create \
  --resource-group "myapp-dev-rg" \
  --template-file templates/complete-environment.json \
  --parameters @parameters.json
```

#### **Using Azure Portal:**
1. Upload `complete-environment.json` template
2. Configure parameters
3. Deploy to resource group

## 🔒 **Security Configuration**

### **Network Security**

#### **VNet Configuration:**
- **Isolated Network**: All resources within private VNet
- **Subnet Segmentation**: Separate subnets for different resource types
- **Delegation**: App Service subnet delegated to Microsoft.Web/serverFarms

#### **Network Security Groups (NSGs):**
- **App Service Subnet**: Allow HTTPS (443) and HTTP (80)
- **Database Subnet**: Allow SQL (1433) from App Service subnet
- **Storage Subnet**: Allow HTTPS (443) only
- **Management Subnet**: Allow SSH (22) and RDP (3389)

### **Application Security**

#### **App Service Security:**
- **HTTPS Enforcement**: All traffic redirected to HTTPS
- **TLS 1.2 Minimum**: Modern encryption standards
- **FTP Disabled**: Secure file transfer only
- **Detailed Logging**: Comprehensive audit trail

#### **Storage Security:**
- **HTTPS Only**: All storage access encrypted
- **Public Access Disabled**: No anonymous blob access
- **VNet Integration**: Access restricted to VNet
- **Encryption**: Data encrypted at rest

#### **Database Security:**
- **Firewall Rules**: Access restricted to specific subnets
- **Port 1433**: SQL Server port properly configured
- **Azure Services**: Integration with Azure services enabled
- **Encryption**: Data encrypted in transit and at rest

## 📊 **Environment Configurations**

### **Development Environment**
```bash
python3 cli.py deploy environment dev \
  --sql-password "DevPassword123!" \
  --app-service-sku "B1" \
  --sql-database-sku "Basic" \
  --storage-sku "Standard_LRS"
```

### **Staging Environment**
```bash
python3 cli.py deploy environment sit \
  --sql-password "SitPassword123!" \
  --app-service-sku "S1" \
  --sql-database-sku "S0" \
  --storage-sku "Standard_GRS"
```

### **Production Environment**
```bash
python3 cli.py deploy environment prod \
  --sql-password "ProdPassword123!" \
  --app-service-sku "P1" \
  --sql-database-sku "P2" \
  --storage-sku "Standard_RAGRS"
```

## 🔍 **Monitoring and Management**

### **Deployment Monitoring**
```bash
# Check deployment status
python3 cli.py deploy status <deployment_name>

# List resources in environment
python3 cli.py resource list <resource-group-name>
```

### **Resource Management**
```bash
# List all resource groups
python3 cli.py resource groups

# Get deployment outputs
python3 cli.py deploy outputs <deployment_name>
```

### **Environment Cleanup**
```bash
# Delete entire environment
python3 cli.py resource delete-environment <environment> --project-name <project>
```

## 📋 **Deployment Checklist**

### **Pre-Deployment**
- [ ] Azure subscription configured
- [ ] Azure CLI authenticated
- [ ] Resource group location selected
- [ ] SQL password prepared (meets complexity requirements)
- [ ] SKU requirements determined
- [ ] Network requirements reviewed

### **During Deployment**
- [ ] Monitor deployment progress
- [ ] Check for any errors
- [ ] Verify resource creation
- [ ] Test connectivity

### **Post-Deployment**
- [ ] Verify HTTPS enforcement
- [ ] Test database connectivity
- [ ] Check storage access
- [ ] Review security configurations
- [ ] Document connection strings
- [ ] Set up monitoring and alerts

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Deployment Failures**
- Check Azure subscription limits
- Verify resource name uniqueness
- Ensure sufficient permissions
- Review parameter values

#### **Connectivity Issues**
- Verify firewall rules
- Check VNet configuration
- Test from correct subnet
- Review NSG rules

#### **Security Issues**
- Verify HTTPS enforcement
- Check TLS configuration
- Review access policies
- Test encryption settings

### **Getting Help**
- Check deployment logs in Azure Portal
- Use `az deployment group show` for details
- Review resource health in Azure Monitor
- Check Bragi Builder logs for errors

## 🎯 **Best Practices**

### **Security**
1. **Use Strong Passwords**: Complex SQL passwords
2. **Enable HTTPS**: Always enforce HTTPS
3. **Network Segmentation**: Use subnets appropriately
4. **Least Privilege**: Restrict access to minimum required
5. **Regular Updates**: Keep resources updated

### **Cost Management**
1. **Right-Size Resources**: Choose appropriate SKUs
2. **Environment Separation**: Use different SKUs per environment
3. **Monitor Usage**: Track resource consumption
4. **Clean Up**: Remove unused resources

### **Operational Excellence**
1. **Documentation**: Document all configurations
2. **Monitoring**: Set up alerts and monitoring
3. **Backup**: Configure backup policies
4. **Disaster Recovery**: Plan for failure scenarios

## 🚀 **Next Steps**

1. **Deploy Your First Environment**: Start with development
2. **Test Connectivity**: Verify all components work
3. **Configure Monitoring**: Set up alerts and dashboards
4. **Deploy Additional Environments**: Scale to staging and production
5. **Implement CI/CD**: Integrate with deployment pipelines

The complete end-to-end deployment provides a production-ready foundation for your Azure applications with proper security, networking, and best practices built-in.
