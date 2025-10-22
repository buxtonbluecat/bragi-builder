# Bragi Builder 🏗️

**Azure ARM Template Builder and Deployment Manager**

Bragi Builder is a comprehensive tool for building, managing, and deploying Azure ARM templates with a focus on speed and ease of use for product development teams.

## 🚀 Features

### **Template Management**
- **Pre-built Templates**: App Service, Storage, SQL Server, VNet, and more
- **Template Wizard**: Guided ARM template creation without ARM knowledge
- **Template Validation**: Built-in validation and error checking
- **Template Library**: Organize and manage your templates

### **Deployment Management**
- **Complete Environment Deployment**: End-to-end infrastructure deployment
- **Resource Group Management**: Automatic resource group creation
- **Deployment Monitoring**: Track deployment status and progress
- **Multi-Environment Support**: Dev, SIT, UAT, Pre-prod, Prod

### **Offline Review System**
- **Workload Configuration**: Define sizes (Small, Medium, Large, Enterprise)
- **Cost Estimation**: Analyze costs before deployment
- **Session Management**: Save and review configurations offline
- **Team Collaboration**: Share configurations and reviews

### **Security & Networking**
- **VNet Integration**: Complete network infrastructure with subnets
- **HTTPS Enforcement**: App Service and Storage HTTPS-only
- **SQL Security**: Port 1433 configuration with firewall rules
- **Network Segmentation**: Proper subnet isolation and NSG rules

## 🏗️ Infrastructure Stack

### **Complete Environment Deployment**
- **Resource Group**: Auto-created per environment
- **Virtual Network**: 10.0.0.0/16 with 4 subnets
- **App Service**: Linux-based with HTTPS enforcement
- **Storage Account**: HTTPS-only with VNet integration
- **SQL Server**: Port 1433 with subnet firewall rules
- **Databases**: Meta and DWH databases included

### **Network Architecture**
- **App Service Subnet**: 10.0.1.0/24 (HTTPS/HTTP)
- **Database Subnet**: 10.0.2.0/24 (SQL 1433)
- **Storage Subnet**: 10.0.3.0/24 (HTTPS only)
- **Management Subnet**: 10.0.4.0/24 (SSH/RDP)

## 🛠️ Setup

### **Prerequisites**
- Python 3.8+
- Azure CLI
- Azure Subscription

### **Installation**
```bash
# Clone the repository
git clone https://github.com/yourusername/bragi-builder.git
cd bragi-builder

# Install dependencies
pip install -r requirements.txt

# Configure Azure credentials
cp env.example .env
# Edit .env with your Azure credentials
```

### **Azure Configuration**
```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "your-subscription-id"

# Create service principal (optional)
az ad sp create-for-rbac --name "bragi-builder" --role contributor
```

## 🚀 Usage

### **Web Interface**
```bash
python3 app.py
# Access at http://localhost:8080
```

### **Command Line Interface**
```bash
# Deploy complete environment
python3 cli.py deploy environment dev \
  --sql-password "YourPassword123!" \
  --app-service-sku "B1" \
  --sql-database-sku "Basic"

# List templates
python3 cli.py template list

# Create offline review session
python3 cli.py review create "My App" \
  --environment dev --size medium

# Check deployment status
python3 cli.py deploy status <deployment-name>
```

### **Template Wizard**
1. Go to http://localhost:8080
2. Click "Template Wizard"
3. Follow the 5-step guided process:
   - Template Information
   - Resource Selection
   - Parameter Configuration
   - Output Definition
   - Review & Generate

## 📋 Available Templates

- **complete-environment**: Full infrastructure stack
- **vnet-complete**: Virtual Network with subnets
- **app-service**: App Service with HTTPS enforcement
- **blob-storage**: Storage Account with security
- **sql-server**: SQL Server with firewall rules
- **sql-database**: Individual SQL Database

## 🔒 Security Features

- **HTTPS Enforcement**: All web traffic encrypted
- **TLS 1.2 Minimum**: Modern encryption standards
- **Network Isolation**: Private VNet with subnet segmentation
- **Firewall Rules**: Subnet-based access control
- **Encryption**: Data encrypted at rest and in transit
- **Access Control**: Least privilege principles

## 📊 Environment Configurations

### **Development**
```bash
python3 cli.py deploy environment dev \
  --sql-password "DevPassword123!" \
  --app-service-sku "B1" \
  --sql-database-sku "Basic"
```

### **Production**
```bash
python3 cli.py deploy environment prod \
  --sql-password "ProdPassword123!" \
  --app-service-sku "P1" \
  --sql-database-sku "P2" \
  --storage-sku "Standard_RAGRS"
```

## 🎯 Use Cases

- **Rapid Prototyping**: Quickly spin up development environments
- **Infrastructure as Code**: Version control your infrastructure
- **Environment Management**: Consistent deployments across environments
- **Cost Optimization**: Right-size resources for each environment
- **Security Compliance**: Built-in security best practices

## 📚 Documentation

- [Complete Deployment Guide](COMPLETE_DEPLOYMENT_GUIDE.md)
- [Template Wizard Guide](TEMPLATE_WIZARD_GUIDE.md)
- [Offline Review Guide](OFFLINE_REVIEW_GUIDE.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/bragi-builder/issues)
- **Documentation**: [Wiki](https://github.com/yourusername/bragi-builder/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/bragi-builder/discussions)

## 🏆 Acknowledgments

- Azure Resource Manager team
- Flask community
- Python Azure SDK contributors

---

**Built with ❤️ for faster Azure deployments**