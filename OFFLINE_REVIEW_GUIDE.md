# Bragi Builder - Offline Review System

## Overview

The offline review system allows you to review, analyze, and configure Azure ARM templates without connecting to Azure. This is perfect for planning deployments, comparing configurations, and ensuring templates meet your requirements before actual deployment.

## Features

### 🎯 **Workload Configuration Management**
- **4 Workload Sizes**: Small, Medium, Large, Enterprise
- **5 Environment Types**: Dev, SIT, UAT, Pre-prod, Production
- **20 Pre-configured Combinations**: Each environment/size combination has optimized resource SKUs
- **DWH Environment Support**: Add multiple data warehouse environments (SIT, UAT, Pre-prod, Prod)

### 📊 **Template Review & Analysis**
- **Template Preview**: See exactly what resources will be created
- **Cost Estimation**: Get monthly cost estimates for each configuration
- **Resource Analysis**: Detailed breakdown of all Azure resources
- **Validation**: Built-in ARM template validation
- **Recommendations**: Smart recommendations based on configuration

### 🔧 **Session Management**
- **Create Sessions**: Start review sessions for specific environments
- **Add Templates**: Add multiple templates to a session
- **Compare Configurations**: Compare different workload sizes and environments
- **Export Sessions**: Export complete session data for sharing
- **Persistent Storage**: Sessions are saved and persist between CLI/web usage

## Quick Start

### Command Line Interface

1. **List available workload configurations:**
   ```bash
   python3 cli.py review configs
   ```

2. **Create a review session:**
   ```bash
   python3 cli.py review create "My Dev Environment" \
     --environment dev \
     --size medium \
     --dwh-environments sit \
     --dwh-environments uat
   ```

3. **Add templates to session:**
   ```bash
   python3 cli.py review add-template "session_id" main-template
   python3 cli.py review add-template "session_id" app-service
   ```

4. **Analyze the session:**
   ```bash
   python3 cli.py review analyze "session_id"
   ```

5. **Export session:**
   ```bash
   python3 cli.py review export "session_id" --output-dir exports
   ```

### Web Interface

1. **Start the web application:**
   ```bash
   python3 app.py
   ```

2. **Navigate to Offline Review:**
   - Open http://localhost:5000
   - Click "Offline Review" in the sidebar

3. **Create a new session:**
   - Click "New Review Session"
   - Choose environment and workload size
   - Select additional DWH environments
   - Click "Create Session"

4. **Add templates:**
   - Open your session
   - Click "Add Template"
   - Select template and customize parameters
   - Click "Add Template"

5. **Analyze and export:**
   - Click "Analyze" to get recommendations
   - Click "Export" to download session data

## Workload Configurations

### Small Workloads
- **App Service**: B1 (Basic)
- **Storage**: Standard_LRS
- **SQL Database**: Basic tier
- **Use Case**: Development, testing, small applications

### Medium Workloads
- **App Service**: S1 (Standard)
- **Storage**: Standard_GRS
- **SQL Database**: S0/S1 tier
- **DWH Environments**: SIT, UAT
- **Use Case**: Staging, integration testing

### Large Workloads
- **App Service**: P1 (Premium)
- **Storage**: Standard_RAGRS
- **SQL Database**: P1/P2 tier
- **DWH Environments**: SIT, UAT, Pre-prod
- **Use Case**: Pre-production, performance testing

### Enterprise Workloads
- **App Service**: P3 (Premium)
- **Storage**: Standard_RAGRS
- **SQL Database**: P4/P6 tier
- **DWH Environments**: All environments
- **Use Case**: Production, high-availability

## Template Analysis Features

### Resource Preview
- **Resource Types**: See all Azure resources that will be created
- **SKU Information**: View configured SKUs and tiers
- **Properties**: Detailed resource properties and configurations
- **Dependencies**: Resource dependencies and relationships

### Cost Estimation
- **Monthly Costs**: Estimated monthly costs for each resource
- **Cost Breakdown**: Detailed cost breakdown by resource type
- **SKU-based Pricing**: Based on current Azure pricing
- **Total Estimates**: Overall cost for the entire configuration

### Validation & Recommendations
- **Template Validation**: ARM template syntax and structure validation
- **Best Practices**: Recommendations for security and performance
- **Environment-specific**: Tailored recommendations based on environment type
- **Resource Optimization**: Suggestions for cost and performance optimization

## DWH Environment Management

### Supported Environments
- **Development (dev)**: Base development environment
- **SIT**: System Integration Testing
- **UAT**: User Acceptance Testing
- **Pre-prod**: Pre-production environment
- **Production (prod)**: Live production environment

### Configuration Options
- **Single Environment**: Deploy only the main environment
- **Multiple DWH**: Add additional data warehouse environments
- **Environment-specific SKUs**: Different resource sizes per environment
- **Cost Optimization**: Smaller SKUs for non-production environments

## Export and Sharing

### Session Export
- **Complete Data**: All templates, parameters, and analysis
- **JSON Format**: Machine-readable session data
- **ZIP Archives**: Compressed export for easy sharing
- **Template Files**: Individual ARM template files
- **Parameter Files**: Separate parameter configuration files

### Use Cases
- **Team Collaboration**: Share session data with team members
- **Documentation**: Export for documentation and approval processes
- **Version Control**: Track changes to configurations over time
- **Backup**: Backup important session configurations

## Best Practices

### Session Organization
1. **Use Descriptive Names**: Clear session names for easy identification
2. **Environment Separation**: Create separate sessions for different environments
3. **Size Comparison**: Create multiple sessions to compare different workload sizes
4. **Regular Analysis**: Run analysis regularly to get updated recommendations

### Template Management
1. **Start with Main Template**: Begin with the main-template for complete environments
2. **Add Individual Templates**: Add specific templates for detailed analysis
3. **Custom Parameters**: Use custom parameters to test different configurations
4. **Validation**: Always validate templates before adding to sessions

### Cost Optimization
1. **Compare Sizes**: Use different sessions to compare small vs large workloads
2. **Environment-specific**: Use appropriate sizes for each environment type
3. **Regular Review**: Review costs regularly as Azure pricing changes
4. **Recommendations**: Follow system recommendations for optimization

## Troubleshooting

### Common Issues
- **Session Not Found**: Ensure session ID is correct and session exists
- **Template Validation Errors**: Check template syntax and required parameters
- **Cost Estimation Issues**: Verify SKU configurations are valid
- **Export Failures**: Ensure sufficient disk space and write permissions

### Getting Help
- **CLI Help**: Use `python3 cli.py review --help` for command help
- **Web Interface**: Check browser console for JavaScript errors
- **Logs**: Check application logs for detailed error information
- **Documentation**: Refer to this guide and inline help text

## Next Steps

1. **Create Your First Session**: Start with a development environment
2. **Experiment with Sizes**: Try different workload sizes to find the right fit
3. **Add DWH Environments**: Configure additional data warehouse environments
4. **Export and Share**: Export sessions for team review and approval
5. **Deploy to Azure**: Use the validated configurations for actual deployments

The offline review system provides a safe, cost-effective way to plan and validate your Azure infrastructure before deployment. Use it to experiment with different configurations, estimate costs, and ensure your templates meet your requirements.
