# Bragi Builder - Deployment Options Guide

This guide covers multiple ways to deploy Bragi Builder to Azure, ranked by reliability and ease of use.

## 🐳 Option 1: Docker Container Deployment (RECOMMENDED)

**Best for:** Production deployments, reliability, full control

### Why Docker?
- ✅ Full control over Python environment and dependencies
- ✅ Dependencies installed during build (not runtime)
- ✅ Consistent across environments
- ✅ Easier to debug and troubleshoot
- ✅ Works with both App Service and Container Apps

### Prerequisites
- Docker installed locally
- Azure CLI installed
- Azure Container Registry (ACR) - will be created automatically

### Quick Start
```bash
# Build and deploy using Docker
./deploy-docker.sh
```

### Manual Steps
```bash
# 1. Build Docker image
docker build -t bragi-builder:latest .

# 2. Tag for ACR
docker tag bragi-builder:latest <acr-name>.azurecr.io/bragi-builder:latest

# 3. Push to ACR
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/bragi-builder:latest

# 4. Configure App Service to use Docker
az webapp config container set \
    --name <app-name> \
    --resource-group <resource-group> \
    --docker-custom-image-name <acr-name>.azurecr.io/bragi-builder:latest
```

---

## 🚀 Option 2: Azure Container Apps

**Best for:** Modern containerized apps, auto-scaling, simpler than App Service

### Why Container Apps?
- ✅ Simpler than App Service for containers
- ✅ Built-in auto-scaling
- ✅ Pay-per-use pricing
- ✅ Better for microservices

### Quick Start
```bash
./deploy-container-apps.sh
```

---

## 📦 Option 3: Azure CLI ZIP Deploy

**Best for:** Quick deployments, when Docker isn't available

### Steps
```bash
# 1. Create ZIP file
zip -r deploy.zip . -x "*.git*" "__pycache__/*" "*.pyc" "*.log" ".env*"

# 2. Deploy using Azure CLI
az webapp deployment source config-zip \
    --name <app-name> \
    --resource-group <resource-group> \
    --src deploy.zip
```

**Note:** This still uses Oryx build, so may have the same issues we've been experiencing.

---

## 🔧 Option 4: VS Code Azure Extension

**Best for:** Visual deployment, IDE integration

### Steps
1. Install "Azure App Service" extension in VS Code
2. Right-click on project folder
3. Select "Deploy to Web App"
4. Follow the wizard

---

## 📋 Option 5: Azure DevOps Pipelines

**Best for:** CI/CD, automated deployments

### Create `azure-pipelines.yml`:
```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: Docker@2
  inputs:
    containerRegistry: 'AzureContainerRegistry'
    repository: 'bragi-builder'
    command: 'buildAndPush'
    Dockerfile: '**/Dockerfile'
    tags: |
      $(Build.BuildId)
      latest

- task: AzureWebApp@1
  inputs:
    azureSubscription: 'Azure-Service-Connection'
    appName: 'bragi-builder-app'
    deployToSlotOrASE: false
    appSettings: |
      -PORT 8000
```

---

## 🎯 Recommendation

**For immediate deployment:** Use **Option 1 (Docker)** - it's the most reliable and gives you full control.

**For long-term:** Consider **Option 2 (Container Apps)** for better scalability and simpler management.

---

## Troubleshooting

### Docker Build Fails
- Check Docker is running: `docker ps`
- Verify Dockerfile syntax
- Check internet connection for pip installs

### Container Won't Start
- Check logs: `az webapp log tail --name <app-name> --resource-group <rg>`
- Verify PORT environment variable is set
- Check gunicorn is installed in requirements.txt

### ACR Authentication Issues
- Run: `az acr login --name <acr-name>`
- Check ACR admin is enabled: `az acr update --name <acr-name> --admin-enabled true`


