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
