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
        # First check if we have it in memory
        if deployment_name in self.deployments:
            deployment_info = self.deployments[deployment_name]
        else:
            # Try to find the deployment by searching resource groups
            deployment_info = self._find_deployment_in_azure(deployment_name)
            if not deployment_info:
                return None
        
        try:
            status = self.azure_client.get_deployment_status(
                resource_group_name=deployment_info["resource_group"],
                deployment_name=deployment_name
            )
            
            if status:
                deployment_info["status"] = status["provisioning_state"]
                deployment_info["outputs"] = status.get("outputs", {})
                deployment_info["timestamp"] = status.get("timestamp")
                
                # If deployment failed, get detailed error information
                if status["provisioning_state"] == "Failed":
                    try:
                        error_details = self.get_deployment_errors(deployment_name, deployment_info["resource_group"])
                        if error_details.get("success"):
                            deployment_info["error_details"] = error_details.get("errors", [])
                    except Exception as e:
                        print(f"Could not get error details for {deployment_name}: {e}")
                
                # Update in-memory storage
                self.deployments[deployment_name] = deployment_info
            
            return deployment_info
            
        except Exception as e:
            return {
                "deployment_name": deployment_name,
                "status": "error",
                "error": str(e)
            }
    
    def _find_deployment_in_azure(self, deployment_name: str) -> Optional[Dict]:
        """Find a deployment by searching Azure resource groups"""
        try:
            # Get all resource groups
            resource_groups = self.azure_client.list_resource_groups()
            
            for rg in resource_groups:
                # Check if this is a Bragi-managed resource group
                if rg.tags and rg.tags.get('CreatedBy') == 'Bragi Builder':
                    try:
                        # Try to get the deployment from this resource group
                        status = self.azure_client.get_deployment_status(rg.name, deployment_name)
                        if status:
                            # Reconstruct deployment info
                            return {
                                "template_name": "complete-environment",  # Default for now
                                "resource_group": rg.name,
                                "status": status["provisioning_state"],
                                "start_time": status["timestamp"].isoformat() if status["timestamp"] else None,
                                "deployment_name": deployment_name,
                                "outputs": status.get("outputs", {})
                            }
                    except:
                        # Deployment not found in this resource group, continue
                        continue
        except Exception as e:
            print(f"Error searching for deployment: {e}")
        
        return None
    
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
        # First return in-memory deployments
        tracked_deployments = list(self.deployments.values())
        
        # Also search Azure for any deployments we might have missed
        try:
            resource_groups = self.azure_client.list_resource_groups()
            
            for rg in resource_groups:
                # Look for Bragi-managed resource groups
                if (rg.tags and 
                    rg.tags.get('CreatedBy') == 'Bragi Builder' and
                    rg.tags.get('DeploymentType') in ['Manual Template', 'Environment']):
                    
                    try:
                        deployments = self.azure_client.resource_client.deployments.list_by_resource_group(rg.name)
                        
                        for deployment in deployments:
                            deployment_name = deployment.name
                            
                            # Skip if we already have this deployment tracked
                            if any(dep['deployment_name'] == deployment_name for dep in tracked_deployments):
                                continue
                            
                            # Add this deployment to our tracking
                            deployment_info = {
                                "deployment_name": deployment_name,
                                "resource_group": rg.name,
                                "status": deployment.properties.provisioning_state,
                                "start_time": deployment.properties.timestamp.isoformat(),
                                "template_name": rg.tags.get('TemplateName', 'unknown'),
                                "environment": rg.tags.get('Environment', 'unknown'),
                                "project": rg.tags.get('Project', 'unknown')
                            }
                            
                            # If deployment failed, get detailed error information
                            if deployment.properties.provisioning_state == "Failed":
                                try:
                                    error_details = self.get_deployment_errors(deployment_name, rg.name)
                                    if error_details.get("success"):
                                        deployment_info["error_details"] = error_details.get("errors", [])
                                except Exception as e:
                                    print(f"Could not get error details for {deployment_name}: {e}")
                            
                            # Add to in-memory tracking
                            self.deployments[deployment_name] = deployment_info
                            tracked_deployments.append(deployment_info)
                            
                    except Exception as e:
                        print(f"Error checking deployments in {rg.name}: {e}")
                        
        except Exception as e:
            print(f"Error searching for deployments: {e}")
        
        return tracked_deployments
    
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
            # Add environment-specific tags
            tags = {
                "Environment": environment,
                "Project": project_name,
                "DeploymentType": "Complete Environment"
            }
            self.azure_client.create_resource_group(resource_group_name, location, tags)
        
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
    
    def delete_environment(self, environment: str, project_name: str = "bragi", resource_group_name: str = None) -> Dict:
        """Delete an entire environment by deleting the resource group"""
        # Use provided resource group name or construct from project/environment
        if not resource_group_name:
            resource_group_name = f"{project_name}-{environment}-rg"
        
        try:
            # Check if resource group exists
            rg = self.azure_client.get_resource_group(resource_group_name)
            if not rg:
                return {
                    "success": False,
                    "message": f"Resource group {resource_group_name} not found"
                }
            
            # Delete the resource group using the enhanced method
            delete_result = self.azure_client.delete_resource_group(resource_group_name)
            
            if delete_result["success"]:
                # Store the operation for progress tracking
                if not hasattr(self, 'delete_operations'):
                    self.delete_operations = {}
                
                self.delete_operations[resource_group_name] = {
                    "operation": delete_result["operation"],
                    "environment": environment,
                    "project_name": project_name,
                    "started_at": datetime.now().isoformat(),
                    "status": "running"
                }
                
                return {
                    "success": True,
                    "message": f"Environment {environment} deletion initiated successfully",
                    "resource_group": resource_group_name,
                    "status": "running"
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to initiate deletion: {delete_result['message']}"
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error deleting environment: {str(e)}"
            }

    def check_delete_progress(self, resource_group_name: str) -> Dict:
        """Check the progress of a resource group deletion"""
        try:
            if not hasattr(self, 'delete_operations') or resource_group_name not in self.delete_operations:
                return {
                    "success": False,
                    "message": "No delete operation found for this resource group"
                }
            
            delete_op = self.delete_operations[resource_group_name]
            operation = delete_op["operation"]
            
            # Check the status
            status_result = self.azure_client.check_delete_status(operation)
            
            # Update our tracking
            delete_op["status"] = status_result["status"]
            delete_op["last_checked"] = datetime.now().isoformat()
            
            if status_result["status"] == "completed":
                # Clean up the tracking
                del self.delete_operations[resource_group_name]
                return {
                    "success": True,
                    "status": "completed",
                    "message": f"Environment {delete_op['environment']} deleted successfully",
                    "environment": delete_op["environment"],
                    "project_name": delete_op["project_name"]
                }
            elif status_result["status"] == "failed":
                # Clean up the tracking
                del self.delete_operations[resource_group_name]
                return {
                    "success": False,
                    "status": "failed",
                    "message": f"Environment {delete_op['environment']} deletion failed",
                    "environment": delete_op["environment"],
                    "project_name": delete_op["project_name"]
                }
            else:
                # Still running
                return {
                    "success": True,
                    "status": "running",
                    "message": f"Environment {delete_op['environment']} deletion in progress...",
                    "environment": delete_op["environment"],
                    "project_name": delete_op["project_name"],
                    "started_at": delete_op["started_at"]
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error checking delete progress: {str(e)}"
            }

    def get_deployment_errors(self, deployment_name: str, resource_group_name: str) -> Dict:
        """Get detailed error information for a failed deployment"""
        try:
            # Get the deployment details
            deployment = self.azure_client.resource_client.deployments.get(
                resource_group_name, deployment_name
            )
            
            errors = []
            
            # Check if deployment has errors
            if hasattr(deployment.properties, 'error') and deployment.properties.error:
                main_error = {
                    "code": deployment.properties.error.code,
                    "message": deployment.properties.error.message,
                    "target": getattr(deployment.properties.error, 'target', None)
                }
                errors.append(main_error)
                
                # Get detailed errors
                if hasattr(deployment.properties.error, 'details') and deployment.properties.error.details:
                    for detail in deployment.properties.error.details:
                        detail_error = {
                            "code": detail.code,
                            "message": detail.message,
                            "target": getattr(detail, 'target', None)
                        }
                        errors.append(detail_error)
            
            # Get operation details for more specific errors
            try:
                operations = self.azure_client.resource_client.deployment_operations.list(
                    resource_group_name, deployment_name
                )
                
                failed_operations = []
                for operation in operations:
                    if (hasattr(operation.properties, 'provisioning_state') and 
                        operation.properties.provisioning_state == 'Failed'):
                        
                        op_error = {
                            "resource_name": operation.properties.target_resource.resource_name,
                            "resource_type": operation.properties.target_resource.resource_type,
                            "provisioning_state": operation.properties.provisioning_state
                        }
                        
                        if hasattr(operation.properties, 'status_message') and operation.properties.status_message:
                            op_error["status_message"] = operation.properties.status_message
                        
                        failed_operations.append(op_error)
                
                if failed_operations:
                    errors.append({
                        "type": "failed_operations",
                        "operations": failed_operations
                    })
                    
            except Exception as e:
                print(f"Could not get operation details: {e}")
            
            return {
                "success": True,
                "deployment_name": deployment_name,
                "resource_group": resource_group_name,
                "errors": errors,
                "total_errors": len(errors)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting deployment errors: {str(e)}"
            }
    
    def get_environment_endpoints(self, environment: str, project_name: str = "bragi", resource_group_name: str = None) -> Dict:
        """Get public-facing endpoints and IP addresses for an environment"""
        # Use provided resource group name or construct from project/environment
        if not resource_group_name:
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
                        vnet = self.azure_client.network_client.virtual_networks.get(
                            resource_group_name, resource_name
                        )
                        address_space = []
                        if hasattr(vnet, 'address_space') and vnet.address_space and hasattr(vnet.address_space, 'address_prefixes'):
                            address_space = vnet.address_space.address_prefixes
                        
                        subnets = []
                        if hasattr(vnet, 'subnets') and vnet.subnets:
                            subnets = [subnet.name for subnet in vnet.subnets]
                        
                        endpoints["vnet"] = {
                            "name": resource_name,
                            "address_space": address_space,
                            "subnets": subnets
                        }
                    except Exception as e:
                        print(f"Error getting VNet details: {e}")
                
                elif "Microsoft.Network/publicIPAddresses" in resource_type:
                    # Get Public IP details
                    try:
                        public_ip = self.azure_client.network_client.public_ip_addresses.get(
                            resource_group_name, resource_name
                        )
                        if hasattr(public_ip, 'ip_address') and public_ip.ip_address:
                            endpoints["public_ips"].append({
                                "name": resource_name,
                                "ip_address": public_ip.ip_address,
                                "allocation_method": public_ip.public_ip_allocation_method,
                                "state": public_ip.provisioning_state
                            })
                    except Exception as e:
                        print(f"Error getting Public IP details: {e}")
            
            return endpoints
            
        except Exception as e:
            print(f"Error getting environment endpoints: {e}")
            return {}
