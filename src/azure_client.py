"""
Azure client for managing ARM template deployments
"""
import os
from datetime import datetime
from typing import List, Dict
from azure.identity import DefaultAzureCredential, ClientSecretCredential, ManagedIdentityCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.core.exceptions import ResourceNotFoundError


class AzureClient:
    """Azure client for managing resources and deployments"""
    
    def __init__(self, subscription_id: str = None):
        self.subscription_id = subscription_id or os.getenv('AZURE_SUBSCRIPTION_ID')
        if not self.subscription_id:
            raise ValueError("Azure subscription ID is required")
        
        # Initialize credentials
        self.credential = self._get_credential()
        
        # Initialize clients
        self.resource_client = ResourceManagementClient(
            self.credential, 
            self.subscription_id
        )
        self.web_client = WebSiteManagementClient(
            self.credential, 
            self.subscription_id
        )
        self.storage_client = StorageManagementClient(
            self.credential, 
            self.subscription_id
        )
        self.sql_client = SqlManagementClient(
            self.credential, 
            self.subscription_id
        )
        self.network_client = NetworkManagementClient(
            self.credential, 
            self.subscription_id
        )
        self.compute_client = ComputeManagementClient(
            self.credential, 
            self.subscription_id
        )
    
    def _get_credential(self):
        """Get Azure credentials based on environment"""
        # Try service principal first (only if all are properly set and not empty)
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        tenant_id = os.getenv('AZURE_TENANT_ID')
        
        if all([client_id, client_secret, tenant_id]) and all([client_id.strip(), client_secret.strip(), tenant_id.strip()]) and not any([client_id == 'your-client-id', client_secret == 'your-client-secret', tenant_id == 'your-tenant-id']):
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        
        # Try managed identity explicitly if running in Azure (Container Apps, App Service, etc.)
        # Container Apps and App Service provide managed identity via IMDS endpoint
        # ManagedIdentityCredential will be tried first by DefaultAzureCredential,
        # but we can also try it explicitly. However, DefaultAzureCredential handles
        # the fallback better, so we'll use it but ensure it tries managed identity first.
        # The exclude_environment_credential=True prevents issues with empty env vars,
        # but managed identity should still work via IMDS endpoint.
        return DefaultAzureCredential(exclude_environment_credential=True)
    
    def deploy_template(self, resource_group_name: str, template: dict, 
                       parameters: dict = None, deployment_name: str = None):
        """Deploy an ARM template to a resource group"""
        if not deployment_name:
            deployment_name = f"deployment-{os.urandom(4).hex()}"
        
        deployment_properties = {
            "properties": {
                "mode": "Incremental",
                "template": template,
                "parameters": parameters or {}
            }
        }
        
        try:
            deployment_operation = self.resource_client.deployments.begin_create_or_update(
                resource_group_name=resource_group_name,
                deployment_name=deployment_name,
                parameters=deployment_properties
            )
            
            return {
                "deployment_name": deployment_name,
                "operation": deployment_operation,
                "status": "started"
            }
        except Exception as e:
            raise Exception(f"Failed to start deployment: {str(e)}")
    
    def get_deployment_status(self, resource_group_name: str, deployment_name: str):
        """Get the status of a deployment"""
        try:
            deployment = self.resource_client.deployments.get(
                resource_group_name=resource_group_name,
                deployment_name=deployment_name
            )
            
            # Convert outputs to serializable format
            outputs = {}
            if deployment.properties.outputs:
                outputs = dict(deployment.properties.outputs)
            
            return {
                "name": deployment.name,
                "provisioning_state": deployment.properties.provisioning_state,
                "timestamp": deployment.properties.timestamp,
                "outputs": outputs
            }
        except ResourceNotFoundError:
            return None
        except Exception as e:
            raise Exception(f"Failed to get deployment status: {str(e)}")
    
    def list_resource_groups(self):
        """List all resource groups in the subscription"""
        try:
            resource_groups = self.resource_client.resource_groups.list()
            return [rg for rg in resource_groups]
        except Exception as e:
            # Clean up error message to avoid HTML-like content in JSON responses
            error_str = str(e)
            # Extract just the error message, not object representations
            if 'Failed to resolve' in error_str or 'Lookup timed out' in error_str:
                error_msg = "DNS resolution failed. Please check network connectivity and DNS configuration."
            elif 'urllib3' in error_str or '<' in error_str:
                # Extract meaningful error message without object representations
                import re
                error_msg = re.sub(r'<[^>]+object at 0x[0-9a-f]+>', '', error_str)
                error_msg = error_msg.strip()
                if not error_msg or error_msg == 'Failed to list resource groups: ':
                    error_msg = "Failed to connect to Azure management API. Please check network connectivity."
            else:
                error_msg = error_str
            raise Exception(f"Failed to list resource groups: {error_msg}")
    
    def create_resource_group(self, name: str, location: str, tags: dict = None):
        """Create a new resource group with optional tags"""
        try:
            # Default Bragi tags
            default_tags = {
                "CreatedBy": "Bragi Builder",
                "Project": "Bragi",
                "Environment": "Unknown",
                "CreatedDate": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Merge with any provided tags
            if tags:
                default_tags.update(tags)
            
            resource_group = self.resource_client.resource_groups.create_or_update(
                resource_group_name=name,
                parameters={
                    "location": location,
                    "tags": default_tags
                }
            )
            return resource_group
        except Exception as e:
            raise Exception(f"Failed to create resource group: {str(e)}")
    
    def get_resource_group(self, name: str):
        """Get a resource group by name"""
        try:
            return self.resource_client.resource_groups.get(name)
        except ResourceNotFoundError:
            return None
        except Exception as e:
            raise Exception(f"Failed to get resource group: {str(e)}")
    
    def list_resources_in_group(self, resource_group_name: str):
        """List all resources in a resource group"""
        try:
            resources = self.resource_client.resources.list_by_resource_group(
                resource_group_name
            )
            return [resource for resource in resources]
        except Exception as e:
            raise Exception(f"Failed to list resources: {str(e)}")
    
    def validate_resource_group_name(self, name: str) -> Dict:
        """Validate that a resource group name is available and follows naming conventions"""
        try:
            # Check if resource group already exists
            existing_rg = self.get_resource_group(name)
            if existing_rg:
                return {
                    "is_valid": False,
                    "error": "Resource group already exists",
                    "suggestion": f"Choose a different name or use the existing resource group '{name}'"
                }
            
            # Validate naming conventions
            if len(name) < 1 or len(name) > 90:
                return {
                    "is_valid": False,
                    "error": "Resource group name must be 1-90 characters long"
                }
            
            # Check for invalid characters
            import re
            if not re.match(r'^[a-zA-Z0-9._-]+$', name):
                return {
                    "is_valid": False,
                    "error": "Resource group name can only contain letters, numbers, periods, underscores, and hyphens"
                }
            
            # Check if name ends with period
            if name.endswith('.'):
                return {
                    "is_valid": False,
                    "error": "Resource group name cannot end with a period"
                }
            
            return {
                "is_valid": True,
                "message": "Resource group name is available"
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Validation failed: {str(e)}"
            }

    def delete_resource_group(self, name: str) -> Dict:
        """Delete a resource group and all its resources"""
        try:
            print(f"Deleting resource group: {name}")
            delete_operation = self.resource_client.resource_groups.begin_delete(name)
            print(f"Delete operation initiated: {delete_operation}")
            
            return {
                "success": True,
                "operation": delete_operation,
                "message": "Resource group deletion initiated successfully"
            }
        except Exception as e:
            print(f"Error deleting resource group {name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to initiate deletion: {str(e)}"
            }

    def check_delete_status(self, operation) -> Dict:
        """Check the status of a delete operation"""
        try:
            if operation.done():
                if operation.result():
                    return {
                        "status": "completed",
                        "success": True,
                        "message": "Resource group deleted successfully"
                    }
                else:
                    return {
                        "status": "failed",
                        "success": False,
                        "message": "Resource group deletion failed"
                    }
            else:
                return {
                    "status": "running",
                    "success": True,
                    "message": "Resource group deletion in progress..."
                }
        except Exception as e:
            return {
                "status": "error",
                "success": False,
                "message": f"Error checking delete status: {str(e)}"
            }
    
    def get_available_regions(self) -> List[Dict]:
        """Get all available Azure regions"""
        try:
            locations = self.resource_client.providers.list()
            regions = []
            
            for provider in locations:
                if provider.namespace == "Microsoft.Resources":
                    for resource_type in provider.resource_types:
                        if resource_type.resource_type == "resourceGroups":
                            for location in resource_type.locations:
                                regions.append({
                                    "name": location,
                                    "display_name": location.replace(" ", "").title(),
                                    "available": True
                                })
                            break
            
            # Sort regions alphabetically
            regions.sort(key=lambda x: x["name"])
            return regions
            
        except Exception as e:
            print(f"Error getting available regions: {e}")
            return []
    
    def validate_region_capabilities(self, location: str) -> Dict:
        """Validate what services can be deployed in a specific region"""
        try:
            capabilities = {
                "app_service": False,
                "storage": False,
                "sql_server": False,
                "vnet": False,
                "overall": True
            }
            
            # Check App Service availability
            try:
                web_sites = self.web_client.app_service_plans.list()
                # If we can list app service plans, the service is available
                capabilities["app_service"] = True
            except Exception:
                capabilities["app_service"] = False
            
            # Check Storage availability
            try:
                storage_accounts = self.storage_client.storage_accounts.list()
                capabilities["storage"] = True
            except Exception:
                capabilities["storage"] = False
            
            # Check SQL Server availability
            try:
                sql_servers = self.sql_client.servers.list()
                capabilities["sql_server"] = True
            except Exception:
                capabilities["sql_server"] = False
            
            # VNet is generally available in all regions
            capabilities["vnet"] = True
            
            # Overall capability (all required services available)
            capabilities["overall"] = all([
                capabilities["app_service"],
                capabilities["storage"],
                capabilities["sql_server"],
                capabilities["vnet"]
            ])
            
            return capabilities
            
        except Exception as e:
            print(f"Error validating region capabilities: {e}")
            return {
                "app_service": False,
                "storage": False,
                "sql_server": False,
                "vnet": False,
                "overall": False
            }
