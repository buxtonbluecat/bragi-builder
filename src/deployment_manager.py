"""
Deployment manager for handling ARM template deployments
"""
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from .azure_client import AzureClient
from .template_manager import TemplateManager


class DeploymentManager:
    """Manages ARM template deployments"""
    
    def __init__(self, azure_client: AzureClient, template_manager: TemplateManager):
        self.azure_client = azure_client
        self.template_manager = template_manager
        self.deployments = {}  # In-memory storage for deployment tracking
    
    def deploy_template(self, template_name: str, resource_group_name: str, 
                       parameters: Dict = None, deployment_name: str = None) -> Dict:
        """Deploy a template to Azure"""
        # Get the template
        template = self.template_manager.get_template(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
        
        # Validate template
        validation = self.template_manager.validate_template(template)
        if not validation["valid"]:
            raise ValueError(f"Template validation failed: {validation['errors']}")
        
        # Generate deployment name if not provided
        if not deployment_name:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            deployment_name = f"{template_name}-{timestamp}"
        
        # Deploy the template
        try:
            deployment_result = self.azure_client.deploy_template(
                resource_group_name=resource_group_name,
                template=template,
                parameters=parameters or {},
                deployment_name=deployment_name
            )
            
            # Store deployment info
            self.deployments[deployment_name] = {
                "template_name": template_name,
                "resource_group": resource_group_name,
                "parameters": parameters or {},
                "status": "started",
                "start_time": datetime.now().isoformat(),
                "operation": deployment_result["operation"]
            }
            
            return {
                "deployment_name": deployment_name,
                "status": "started",
                "message": "Deployment started successfully"
            }
            
        except Exception as e:
            raise Exception(f"Failed to deploy template: {str(e)}")
    
    def get_deployment_status(self, deployment_name: str) -> Optional[Dict]:
        """Get the status of a deployment"""
        if deployment_name not in self.deployments:
            return None
        
        deployment_info = self.deployments[deployment_name]
        
        try:
            status = self.azure_client.get_deployment_status(
                resource_group_name=deployment_info["resource_group"],
                deployment_name=deployment_name
            )
            
            if status:
                deployment_info["status"] = status["provisioning_state"]
                deployment_info["outputs"] = status.get("outputs", {})
                deployment_info["timestamp"] = status.get("timestamp")
                
                # Update in-memory storage
                self.deployments[deployment_name] = deployment_info
            
            return deployment_info
            
        except Exception as e:
            return {
                "deployment_name": deployment_name,
                "status": "error",
                "error": str(e)
            }
    
    def wait_for_deployment(self, deployment_name: str, timeout: int = 1800) -> Dict:
        """Wait for a deployment to complete"""
        if deployment_name not in self.deployments:
            raise ValueError(f"Deployment {deployment_name} not found")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_deployment_status(deployment_name)
            
            if not status:
                raise ValueError(f"Deployment {deployment_name} not found")
            
            if status["status"] in ["Succeeded", "Failed", "Canceled"]:
                return status
            
            time.sleep(10)  # Wait 10 seconds before checking again
        
        raise TimeoutError(f"Deployment {deployment_name} timed out after {timeout} seconds")
    
    def list_deployments(self) -> List[Dict]:
        """List all tracked deployments"""
        return list(self.deployments.values())
    
    def get_deployment_outputs(self, deployment_name: str) -> Optional[Dict]:
        """Get the outputs from a completed deployment"""
        status = self.get_deployment_status(deployment_name)
        
        if not status or status["status"] != "Succeeded":
            return None
        
        return status.get("outputs", {})
    
    def create_environment_deployment(self, environment: str, project_name: str = "bragi",
                                   location: str = "East US", 
                                   sql_password: str = None,
                                   app_service_sku: str = "B1",
                                   sql_database_sku: str = "Basic",
                                   storage_sku: str = "Standard_LRS",
                                   enable_public_access: bool = False) -> Dict:
        """Create a complete environment deployment using the complete environment template"""
        if not sql_password:
            raise ValueError("SQL password is required for deployment")
        
        resource_group_name = f"{project_name}-{environment}-rg"
        
        # Check if resource group exists, create if not
        rg = self.azure_client.get_resource_group(resource_group_name)
        if not rg:
            print(f"Creating resource group '{resource_group_name}' in {location}...")
            self.azure_client.create_resource_group(resource_group_name, location)
        
        # Prepare parameters for the complete environment template
        parameters = {
            "environment": {"value": environment},
            "projectName": {"value": project_name},
            "location": {"value": location},
            "sqlAdministratorLoginPassword": {"value": sql_password},
            "appServiceSku": {"value": app_service_sku},
            "sqlDatabaseSku": {"value": sql_database_sku},
            "storageSku": {"value": storage_sku},
            "enablePublicNetworkAccess": {"value": enable_public_access}
        }
        
        # Deploy the complete environment template
        return self.deploy_template(
            template_name="complete-environment",
            resource_group_name=resource_group_name,
            parameters=parameters
        )
    
    def get_environment_resources(self, environment: str, project_name: str = "bragi") -> List[Dict]:
        """Get all resources for a specific environment"""
        resource_group_name = f"{project_name}-{environment}-rg"
        
        try:
            resources = self.azure_client.list_resources_in_group(resource_group_name)
            return [
                {
                    "name": resource.name,
                    "type": resource.type,
                    "location": resource.location,
                    "resource_group": resource_group_name
                }
                for resource in resources
            ]
        except Exception as e:
            raise Exception(f"Failed to list resources: {str(e)}")
    
    def delete_environment(self, environment: str, project_name: str = "bragi") -> bool:
        """Delete an entire environment by deleting the resource group"""
        resource_group_name = f"{project_name}-{environment}-rg"
        
        try:
            # Check if resource group exists
            rg = self.azure_client.get_resource_group(resource_group_name)
            if not rg:
                return False
            
            # Delete the resource group (this will delete all resources)
            self.azure_client.resource_client.resource_groups.begin_delete(resource_group_name)
            return True
            
        except Exception as e:
            raise Exception(f"Failed to delete environment: {str(e)}")
    
    def get_environment_endpoints(self, environment: str, project_name: str = "bragi") -> Dict:
        """Get public-facing endpoints and IP addresses for an environment"""
        resource_group_name = f"{project_name}-{environment}-rg"
        
        try:
            # Get all resources in the resource group
            resources = self.azure_client.list_resources_in_group(resource_group_name)
            
            endpoints = {
                "app_service": None,
                "storage_account": None,
                "sql_server": None,
                "vnet": None,
                "public_ips": []
            }
            
            for resource in resources:
                resource_type = resource.type
                resource_name = resource.name
                
                if "Microsoft.Web/sites" in resource_type:
                    # Get App Service details
                    try:
                        app_service = self.azure_client.web_client.web_apps.get(
                            resource_group_name, resource_name
                        )
                        endpoints["app_service"] = {
                            "name": resource_name,
                            "url": f"https://{app_service.default_host_name}",
                            "hostname": app_service.default_host_name,
                            "state": app_service.state,
                            "https_only": app_service.https_only
                        }
                    except Exception as e:
                        print(f"Error getting App Service details: {e}")
                
                elif "Microsoft.Storage/storageAccounts" in resource_type:
                    # Get Storage Account details
                    try:
                        storage_account = self.azure_client.storage_client.storage_accounts.get_properties(
                            resource_group_name, resource_name
                        )
                        endpoints["storage_account"] = {
                            "name": resource_name,
                            "primary_endpoint": f"https://{resource_name}.blob.core.windows.net",
                            "primary_location": storage_account.primary_location,
                            "status": storage_account.status_of_primary
                        }
                    except Exception as e:
                        print(f"Error getting Storage Account details: {e}")
                
                elif "Microsoft.Sql/servers" in resource_type and "/databases" not in resource_type:
                    # Get SQL Server details (only for the server, not databases)
                    try:
                        sql_server = self.azure_client.sql_client.servers.get(
                            resource_group_name, resource_name
                        )
                        endpoints["sql_server"] = {
                            "name": resource_name,
                            "fqdn": sql_server.fully_qualified_domain_name,
                            "version": sql_server.version,
                            "state": sql_server.state
                        }
                    except Exception as e:
                        print(f"Error getting SQL Server details: {e}")
                
                elif "Microsoft.Network/virtualNetworks" in resource_type:
                    # Get VNet details
                    try:
                        vnet = self.azure_client.resource_client.resources.get(
                            resource_group_name, "Microsoft.Network", "", 
                            "virtualNetworks", resource_name, "2021-05-01"
                        )
                        endpoints["vnet"] = {
                            "name": resource_name,
                            "address_space": vnet.properties.address_space.address_prefixes if hasattr(vnet.properties, 'address_space') else [],
                            "subnets": [subnet.name for subnet in vnet.properties.subnets] if hasattr(vnet.properties, 'subnets') else []
                        }
                    except Exception as e:
                        print(f"Error getting VNet details: {e}")
                
                elif "Microsoft.Network/publicIPAddresses" in resource_type:
                    # Get Public IP details
                    try:
                        public_ip = self.azure_client.resource_client.resources.get(
                            resource_group_name, "Microsoft.Network", "", 
                            "publicIPAddresses", resource_name, "2021-05-01"
                        )
                        if hasattr(public_ip.properties, 'ip_address') and public_ip.properties.ip_address:
                            endpoints["public_ips"].append({
                                "name": resource_name,
                                "ip_address": public_ip.properties.ip_address,
                                "allocation_method": public_ip.properties.public_ip_allocation_method
                            })
                    except Exception as e:
                        print(f"Error getting Public IP details: {e}")
            
            return endpoints
            
        except Exception as e:
            print(f"Error getting environment endpoints: {e}")
            return {}
