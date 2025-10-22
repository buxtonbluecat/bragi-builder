# Bragi Builder - Template Wizard

## Overview

The Template Wizard is a guided interface for creating Azure ARM templates without needing to know ARM template syntax. It provides a step-by-step process to build complex infrastructure templates through an intuitive web interface.

## Features

### 🎯 **Guided Template Creation**
- **5-Step Process**: Template info → Resource selection → Parameters → Outputs → Review & Generate
- **Visual Progress**: Progress bar shows current step and completion status
- **Session Management**: Save and resume wizard sessions
- **Real-time Validation**: Built-in template validation at each step

### 🏗️ **Resource Selection & Configuration**
- **8+ Resource Types**: App Service, Storage, SQL Server, Virtual Network, Key Vault, and more
- **Smart Forms**: Dynamic configuration forms based on resource type
- **SKU Selection**: Pre-configured SKU options for each resource
- **Dependency Management**: Automatic dependency resolution between resources

### ⚙️ **Parameter & Output Management**
- **Custom Parameters**: Define template parameters with types and descriptions
- **Output Values**: Specify values to return after deployment
- **Type Safety**: Support for string, int, bool, array, and object types
- **Validation**: Built-in parameter validation and constraints

### 🔧 **Template Generation**
- **ARM Template Output**: Generates valid ARM template JSON
- **Auto-save**: Templates are automatically saved to the template library
- **Validation**: Full ARM template validation before generation
- **Preview**: Preview generated template before saving

## Quick Start

### 1. Access the Template Wizard
- Navigate to http://localhost:8080
- Click "Template Wizard" in the sidebar
- Click "New Template" to start

### 2. Step 1: Template Information
- Enter a descriptive template name
- Add an optional description
- Click "Next" to proceed

### 3. Step 2: Select Resources
- Click "Add Resource" to open the resource selection modal
- Choose from available Azure resource types:
  - **App Service Plan**: Hosting plan for web applications
  - **App Service**: Web application hosting
  - **Storage Account**: Blob, file, table, and queue storage
  - **SQL Server**: Database management system
  - **SQL Database**: Relational database
  - **Virtual Network**: Isolated network environment
  - **Key Vault**: Secure storage for secrets and keys
  - **And more...**

### 4. Configure Each Resource
- Fill out the configuration form for each resource
- Required fields are marked with a red asterisk
- Select appropriate SKUs and options
- Click "Add Resource" to add to your template

### 5. Step 3: Define Parameters
- Add custom parameters that can be customized during deployment
- Specify parameter types (string, int, bool, etc.)
- Add descriptions and default values
- Set allowed values for validation

### 6. Step 4: Define Outputs
- Specify values to return after successful deployment
- Common outputs include connection strings, URLs, and resource IDs
- Use ARM template functions for dynamic values

### 7. Step 5: Review & Generate
- Review your template configuration
- See summary of resources, parameters, and outputs
- Click "Generate Template" to create the final ARM template
- Template is automatically saved to your template library

## Supported Resource Types

### Compute Resources
- **App Service Plan**: Linux/Windows hosting plans (F1, B1-B3, S1-S3, P1-P3)
- **App Service**: Web applications with configurable runtimes

### Storage Resources
- **Storage Account**: Blob, file, table, and queue storage
- **SKU Options**: Standard_LRS, Standard_GRS, Standard_RAGRS, Premium_LRS
- **Access Tiers**: Hot, Cool

### Database Resources
- **SQL Server**: Database management system with configurable version
- **SQL Database**: Relational databases with various SKUs
- **SKU Options**: Basic, S0-S3, P1-P6, P11-P15

### Networking Resources
- **Virtual Network**: Isolated network environments
- **Subnet**: Network segments within virtual networks
- **Network Security Group**: Security rules for network traffic
- **Public IP**: Static or dynamic public IP addresses
- **Load Balancer**: Traffic distribution across resources

### Security Resources
- **Key Vault**: Secure storage for secrets, keys, and certificates
- **SKU Options**: Standard, Premium

### Additional Resources
- **Cognitive Services**: AI and machine learning services
- **Redis Cache**: In-memory data store
- **Service Bus**: Message queuing and communication
- **Event Hub**: Real-time data streaming

## Configuration Options

### Resource Configuration
Each resource type has specific configuration options:

#### App Service Plan
- **Location**: Azure region
- **SKU**: Pricing tier (F1, B1, S1, P1, etc.)
- **Tier**: Service tier (Free, Basic, Standard, Premium)
- **Capacity**: Number of instances
- **Kind**: Linux or Windows

#### Storage Account
- **Location**: Azure region
- **SKU**: Storage type (Standard_LRS, Standard_GRS, etc.)
- **Access Tier**: Hot or Cool
- **Kind**: StorageV2 (default)

#### SQL Server
- **Location**: Azure region
- **Administrator Login**: SQL admin username
- **Administrator Password**: SQL admin password
- **Version**: SQL Server version (12.0 default)
- **Public Network Access**: Enabled/Disabled

#### SQL Database
- **Location**: Azure region
- **Server ID**: Reference to SQL Server
- **SKU**: Database pricing tier
- **Max Size**: Maximum database size in bytes
- **Collation**: Database collation

### Parameter Types
- **String**: Text values
- **Int**: Integer values
- **Bool**: True/False values
- **Array**: List of values
- **Object**: Complex objects
- **SecureString**: Encrypted strings (for passwords)

### Output Types
- **String**: Text output
- **Int**: Integer output
- **Bool**: Boolean output
- **Array**: Array output
- **Object**: Object output

## Best Practices

### Resource Naming
- Use descriptive names for resources
- Follow Azure naming conventions
- Use consistent naming patterns
- Include environment prefixes when appropriate

### Parameter Design
- Make parameters meaningful and descriptive
- Provide helpful descriptions
- Use appropriate default values
- Set validation constraints where possible

### Output Values
- Include commonly needed values (URLs, connection strings)
- Use ARM template functions for dynamic values
- Provide both human-readable and machine-readable outputs

### Template Organization
- Group related resources logically
- Use consistent parameter naming
- Include comprehensive descriptions
- Validate templates before deployment

## Advanced Features

### Dependency Management
- Resources automatically detect dependencies
- Dependencies are added to the `dependsOn` property
- Circular dependencies are prevented
- Resource references are generated automatically

### SKU Optimization
- Pre-configured SKU options for each resource type
- Cost-effective defaults for development environments
- Production-ready configurations available
- Easy switching between different tiers

### Template Validation
- Real-time validation during wizard steps
- Full ARM template validation before generation
- Error messages with specific guidance
- Best practice recommendations

### Session Management
- Save wizard progress at any step
- Resume sessions later
- Multiple concurrent sessions
- Session cleanup and management

## Troubleshooting

### Common Issues
- **Resource Dependencies**: Ensure dependent resources are added first
- **Parameter Validation**: Check parameter types and constraints
- **SKU Compatibility**: Verify SKU combinations are valid
- **Location Availability**: Ensure selected regions support required services

### Getting Help
- **Validation Errors**: Check the validation panel for specific errors
- **Resource Configuration**: Review resource documentation for required fields
- **Parameter Issues**: Ensure parameter types match expected values
- **Template Generation**: Check the generated template for syntax errors

## Integration

### Template Library
- Generated templates are automatically saved
- Access through the Templates page
- Full editing and deployment capabilities
- Version control and history

### Offline Review
- Use generated templates in offline review sessions
- Test configurations before deployment
- Cost estimation and analysis
- Team collaboration and approval

### Deployment
- Deploy generated templates directly to Azure
- Use with existing deployment workflows
- Integration with CI/CD pipelines
- Environment-specific deployments

## Next Steps

1. **Create Your First Template**: Start with a simple web application
2. **Experiment with Resources**: Try different resource combinations
3. **Add Parameters**: Make templates flexible and reusable
4. **Define Outputs**: Include useful deployment information
5. **Deploy and Test**: Use your generated templates in real deployments

The Template Wizard makes ARM template creation accessible to everyone, regardless of their experience with Azure Resource Manager. Use it to quickly prototype infrastructure, create reusable templates, and learn ARM template best practices.
