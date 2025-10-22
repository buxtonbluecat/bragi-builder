"""
Template Wizard - Guided ARM template creation
"""
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class ResourceType(Enum):
    APP_SERVICE = "Microsoft.Web/sites"
    APP_SERVICE_PLAN = "Microsoft.Web/serverfarms"
    STORAGE_ACCOUNT = "Microsoft.Storage/storageAccounts"
    SQL_SERVER = "Microsoft.Sql/servers"
    SQL_DATABASE = "Microsoft.Sql/servers/databases"
    VIRTUAL_NETWORK = "Microsoft.Network/virtualNetworks"
    SUBNET = "Microsoft.Network/virtualNetworks/subnets"
    NETWORK_SECURITY_GROUP = "Microsoft.Network/networkSecurityGroups"
    PUBLIC_IP = "Microsoft.Network/publicIPAddresses"
    LOAD_BALANCER = "Microsoft.Network/loadBalancers"
    KEY_VAULT = "Microsoft.KeyVault/vaults"
    COGNITIVE_SERVICES = "Microsoft.CognitiveServices/accounts"
    REDIS_CACHE = "Microsoft.Cache/Redis"
    SERVICE_BUS = "Microsoft.ServiceBus/namespaces"
    EVENT_HUB = "Microsoft.EventHub/namespaces"


@dataclass
class ResourceTemplate:
    """Template for a specific Azure resource type"""
    resource_type: ResourceType
    name: str
    display_name: str
    description: str
    api_version: str
    required_parameters: List[str]
    optional_parameters: List[str]
    default_properties: Dict[str, Any]
    sku_options: Dict[str, List[str]] = None
    dependencies: List[str] = None


class TemplateWizard:
    """Guided template creation wizard"""
    
    def __init__(self):
        self.resource_templates = self._load_resource_templates()
        self.wizard_sessions = {}
    
    def _load_resource_templates(self) -> Dict[ResourceType, ResourceTemplate]:
        """Load predefined resource templates"""
        templates = {}
        
        # App Service Plan
        templates[ResourceType.APP_SERVICE_PLAN] = ResourceTemplate(
            resource_type=ResourceType.APP_SERVICE_PLAN,
            name="appServicePlan",
            display_name="App Service Plan",
            description="Hosting plan for web applications",
            api_version="2021-02-01",
            required_parameters=["location", "sku"],
            optional_parameters=["capacity", "kind"],
            default_properties={
                "kind": "linux",
                "properties": {
                    "reserved": True
                }
            },
            sku_options={
                "sku": ["F1", "B1", "B2", "B3", "S1", "S2", "S3", "P1", "P2", "P3"],
                "tier": ["Free", "Basic", "Standard", "Premium"]
            }
        )
        
        # App Service
        templates[ResourceType.APP_SERVICE] = ResourceTemplate(
            resource_type=ResourceType.APP_SERVICE,
            name="appService",
            display_name="App Service",
            description="Web application hosting",
            api_version="2021-02-01",
            required_parameters=["location", "serverFarmId"],
            optional_parameters=["kind", "siteConfig"],
            default_properties={
                "kind": "app,linux",
                "properties": {
                    "siteConfig": {
                        "linuxFxVersion": "DOTNETCORE|6.0",
                        "appSettings": []
                    },
                    "httpsOnly": True
                }
            },
            dependencies=["appServicePlan"]
        )
        
        # Storage Account
        templates[ResourceType.STORAGE_ACCOUNT] = ResourceTemplate(
            resource_type=ResourceType.STORAGE_ACCOUNT,
            name="storageAccount",
            display_name="Storage Account",
            description="Blob, file, table, and queue storage",
            api_version="2021-09-01",
            required_parameters=["location", "sku"],
            optional_parameters=["kind", "accessTier"],
            default_properties={
                "kind": "StorageV2",
                "properties": {
                    "supportsHttpsTrafficOnly": True,
                    "minimumTlsVersion": "TLS1_2",
                    "allowBlobPublicAccess": False
                }
            },
            sku_options={
                "sku": ["Standard_LRS", "Standard_GRS", "Standard_RAGRS", "Premium_LRS"],
                "accessTier": ["Hot", "Cool"]
            }
        )
        
        # SQL Server
        templates[ResourceType.SQL_SERVER] = ResourceTemplate(
            resource_type=ResourceType.SQL_SERVER,
            name="sqlServer",
            display_name="SQL Server",
            description="Database management system",
            api_version="2021-11-01",
            required_parameters=["location", "administratorLogin", "administratorLoginPassword"],
            optional_parameters=["version", "publicNetworkAccess"],
            default_properties={
                "properties": {
                    "version": "12.0",
                    "publicNetworkAccess": "Disabled"
                }
            }
        )
        
        # SQL Database
        templates[ResourceType.SQL_DATABASE] = ResourceTemplate(
            resource_type=ResourceType.SQL_DATABASE,
            name="sqlDatabase",
            display_name="SQL Database",
            description="Relational database",
            api_version="2021-11-01",
            required_parameters=["location", "serverId"],
            optional_parameters=["sku", "maxSizeBytes", "collation"],
            default_properties={
                "properties": {
                    "collation": "SQL_Latin1_General_CP1_CI_AS",
                    "maxSizeBytes": 2147483648
                }
            },
            sku_options={
                "sku": ["Basic", "S0", "S1", "S2", "S3", "P1", "P2", "P4", "P6", "P11", "P15"]
            },
            dependencies=["sqlServer"]
        )
        
        # Virtual Network
        templates[ResourceType.VIRTUAL_NETWORK] = ResourceTemplate(
            resource_type=ResourceType.VIRTUAL_NETWORK,
            name="virtualNetwork",
            display_name="Virtual Network",
            description="Isolated network environment",
            api_version="2021-05-01",
            required_parameters=["location", "addressSpace"],
            optional_parameters=["dnsServers"],
            default_properties={
                "properties": {
                    "addressSpace": {
                        "addressPrefixes": ["10.0.0.0/16"]
                    },
                    "subnets": []
                }
            }
        )
        
        # Key Vault
        templates[ResourceType.KEY_VAULT] = ResourceTemplate(
            resource_type=ResourceType.KEY_VAULT,
            name="keyVault",
            display_name="Key Vault",
            description="Secure storage for secrets, keys, and certificates",
            api_version="2021-10-01",
            required_parameters=["location", "tenantId"],
            optional_parameters=["sku", "accessPolicies"],
            default_properties={
                "properties": {
                    "enabledForDeployment": False,
                    "enabledForDiskEncryption": False,
                    "enabledForTemplateDeployment": True,
                    "enableSoftDelete": True,
                    "softDeleteRetentionInDays": 90,
                    "enableRbacAuthorization": True
                }
            },
            sku_options={
                "sku": ["standard", "premium"]
            }
        )
        
        return templates
    
    def start_wizard_session(self, session_name: str, description: str = "") -> str:
        """Start a new wizard session"""
        session_id = f"wizard_{session_name}_{len(self.wizard_sessions)}"
        
        self.wizard_sessions[session_id] = {
            "session_id": session_id,
            "session_name": session_name,
            "description": description,
            "step": 1,
            "total_steps": 5,
            "template": {
                "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
                "contentVersion": "1.0.0.0",
                "parameters": {},
                "variables": {},
                "resources": [],
                "outputs": {}
            },
            "selected_resources": [],
            "resource_configs": {},
            "parameters": {},
            "outputs": {},
            "created_at": None
        }
        
        return session_id
    
    def get_available_resources(self) -> List[Dict]:
        """Get list of available resource types"""
        return [
            {
                "type": rt.value,
                "name": template.name,
                "display_name": template.display_name,
                "description": template.description,
                "api_version": template.api_version,
                "required_parameters": template.required_parameters,
                "optional_parameters": template.optional_parameters,
                "sku_options": template.sku_options or {}
            }
            for rt, template in self.resource_templates.items()
        ]
    
    def add_resource_to_session(self, session_id: str, resource_type: str, 
                              resource_name: str, configuration: Dict) -> Dict:
        """Add a resource to the wizard session"""
        if session_id not in self.wizard_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.wizard_sessions[session_id]
        
        # Find the resource template
        resource_template = None
        for rt, template in self.resource_templates.items():
            if rt.value == resource_type:
                resource_template = template
                break
        
        if not resource_template:
            raise ValueError(f"Resource type {resource_type} not supported")
        
        # Create resource definition
        resource_def = {
            "type": resource_type,
            "apiVersion": resource_template.api_version,
            "name": resource_name,
            "location": configuration.get("location", "[resourceGroup().location]"),
            "properties": resource_template.default_properties.get("properties", {}).copy()
        }
        
        # Apply configuration
        if "sku" in configuration:
            resource_def["sku"] = configuration["sku"]
        
        if "kind" in configuration:
            resource_def["kind"] = configuration["kind"]
        
        # Add dependencies
        if resource_template.dependencies:
            resource_def["dependsOn"] = []
            for dep in resource_template.dependencies:
                # Find matching resource in session
                for selected in session["selected_resources"]:
                    if selected["template_name"] == dep:
                        resource_def["dependsOn"].append(f"[resourceId('{selected['resource_type']}', '{selected['resource_name']}')]")
        
        # Store resource configuration
        session["selected_resources"].append({
            "resource_type": resource_type,
            "resource_name": resource_name,
            "template_name": resource_template.name,
            "display_name": resource_template.display_name,
            "configuration": configuration
        })
        
        session["resource_configs"][resource_name] = {
            "resource_type": resource_type,
            "template_name": resource_template.name,
            "configuration": configuration
        }
        
        return {
            "resource_name": resource_name,
            "resource_type": resource_type,
            "display_name": resource_template.display_name,
            "configuration": configuration
        }
    
    def add_parameter(self, session_id: str, param_name: str, param_config: Dict) -> Dict:
        """Add a parameter to the template"""
        if session_id not in self.wizard_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.wizard_sessions[session_id]
        
        parameter_def = {
            "type": param_config.get("type", "string"),
            "metadata": {
                "description": param_config.get("description", "")
            }
        }
        
        if "defaultValue" in param_config:
            parameter_def["defaultValue"] = param_config["defaultValue"]
        
        if "allowedValues" in param_config:
            parameter_def["allowedValues"] = param_config["allowedValues"]
        
        session["template"]["parameters"][param_name] = parameter_def
        session["parameters"][param_name] = param_config
        
        return parameter_def
    
    def add_output(self, session_id: str, output_name: str, output_config: Dict) -> Dict:
        """Add an output to the template"""
        if session_id not in self.wizard_sessions[session_id]:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.wizard_sessions[session_id]
        
        output_def = {
            "type": output_config.get("type", "string"),
            "value": output_config.get("value", "")
        }
        
        session["template"]["outputs"][output_name] = output_def
        session["outputs"][output_name] = output_config
        
        return output_def
    
    def generate_template(self, session_id: str) -> Dict:
        """Generate the final ARM template from the wizard session"""
        if session_id not in self.wizard_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.wizard_sessions[session_id]
        template = session["template"].copy()
        
        # Add all selected resources
        for resource_info in session["selected_resources"]:
            resource_def = self._create_resource_definition(resource_info, session)
            template["resources"].append(resource_def)
        
        # Add variables for resource references
        variables = {}
        for resource_info in session["selected_resources"]:
            resource_name = resource_info["resource_name"]
            resource_type = resource_info["resource_type"]
            variables[f"{resource_name}Id"] = f"[resourceId('{resource_type}', '{resource_name}')]"
        
        template["variables"] = variables
        
        return template
    
    def _create_resource_definition(self, resource_info: Dict, session: Dict) -> Dict:
        """Create a resource definition from resource info"""
        resource_type = resource_info["resource_type"]
        resource_name = resource_info["resource_name"]
        configuration = resource_info["configuration"]
        
        # Get the resource template
        resource_template = None
        for rt, template in self.resource_templates.items():
            if rt.value == resource_type:
                resource_template = template
                break
        
        if not resource_template:
            raise ValueError(f"Resource type {resource_type} not supported")
        
        # Create base resource definition
        resource_def = {
            "type": resource_type,
            "apiVersion": resource_template.api_version,
            "name": resource_name,
            "location": configuration.get("location", "[resourceGroup().location]"),
            "properties": resource_template.default_properties.get("properties", {}).copy()
        }
        
        # Apply configuration
        if "sku" in configuration:
            resource_def["sku"] = configuration["sku"]
        
        if "kind" in configuration:
            resource_def["kind"] = configuration["kind"]
        
        # Add dependencies
        if resource_template.dependencies:
            resource_def["dependsOn"] = []
            for dep in resource_template.dependencies:
                # Find matching resource in session
                for selected in session["selected_resources"]:
                    if selected["template_name"] == dep:
                        resource_def["dependsOn"].append(f"[resourceId('{selected['resource_type']}', '{selected['resource_name']}')]")
        
        return resource_def
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get a wizard session"""
        return self.wizard_sessions.get(session_id)
    
    def list_sessions(self) -> List[Dict]:
        """List all wizard sessions"""
        return [
            {
                "session_id": session_id,
                "session_name": session["session_name"],
                "description": session["description"],
                "step": session["step"],
                "total_steps": session["total_steps"],
                "selected_resources": len(session["selected_resources"]),
                "created_at": session.get("created_at")
            }
            for session_id, session in self.wizard_sessions.items()
        ]
    
    def update_session_step(self, session_id: str, step: int):
        """Update the current step in the wizard"""
        if session_id in self.wizard_sessions:
            self.wizard_sessions[session_id]["step"] = step
    
    def get_resource_configuration_form(self, resource_type: str) -> Dict:
        """Get configuration form for a specific resource type"""
        resource_template = None
        for rt, template in self.resource_templates.items():
            if rt.value == resource_type:
                resource_template = template
                break
        
        if not resource_template:
            return {}
        
        form_config = {
            "resource_type": resource_type,
            "display_name": resource_template.display_name,
            "description": resource_template.description,
            "fields": []
        }
        
        # Add required parameters
        for param in resource_template.required_parameters:
            field_config = {
                "name": param,
                "label": param.replace("_", " ").title(),
                "type": "text",
                "required": True,
                "placeholder": f"Enter {param}"
            }
            
            if param == "location":
                field_config["type"] = "select"
                field_config["options"] = [
                    "East US", "West US", "West Europe", "East Asia", 
                    "Southeast Asia", "North Europe", "South Central US"
                ]
            elif param == "sku" and resource_template.sku_options and "sku" in resource_template.sku_options:
                field_config["type"] = "select"
                field_config["options"] = resource_template.sku_options["sku"]
            elif param == "administratorLoginPassword":
                field_config["type"] = "password"
            elif param == "serverFarmId":
                field_config["type"] = "select"
                field_config["options"] = "dynamic"  # Will be populated from selected resources
                field_config["depends_on"] = "appServicePlan"
            
            form_config["fields"].append(field_config)
        
        # Add optional parameters
        for param in resource_template.optional_parameters:
            field_config = {
                "name": param,
                "label": param.replace("_", " ").title(),
                "type": "text",
                "required": False,
                "placeholder": f"Enter {param} (optional)"
            }
            
            if param == "accessTier" and resource_template.sku_options and "accessTier" in resource_template.sku_options:
                field_config["type"] = "select"
                field_config["options"] = resource_template.sku_options["accessTier"]
            elif param == "kind":
                field_config["type"] = "select"
                field_config["options"] = ["linux", "windows", "app,linux", "app,windows"]
            
            form_config["fields"].append(field_config)
        
        return form_config
