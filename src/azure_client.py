"""
Azure client for managing ARM template deployments
"""
import os
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.sql import SqlManagementClient
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
    
    def _get_credential(self):
        """Get Azure credentials based on environment"""
        # Try service principal first
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        tenant_id = os.getenv('AZURE_TENANT_ID')
        
        if all([client_id, client_secret, tenant_id]):
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        
        # Fall back to default credential (Azure CLI, Managed Identity, etc.)
        return DefaultAzureCredential()
    
    def deploy_template(self, resource_group_name: str, template: dict, 
                       parameters: dict = None, deployment_name: str = None):
        """Deploy an ARM template to a resource group"""
        if not deployment_name:
            deployment_name = f"deployment-{os.urandom(4).hex()}"
        
        deployment_properties = {
            "mode": "Incremental",
            "template": template,
            "parameters": parameters or {}
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
            
            return {
                "name": deployment.name,
                "provisioning_state": deployment.properties.provisioning_state,
                "timestamp": deployment.properties.timestamp,
                "outputs": deployment.properties.outputs
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
            raise Exception(f"Failed to list resource groups: {str(e)}")
    
    def create_resource_group(self, name: str, location: str):
        """Create a new resource group"""
        try:
            resource_group = self.resource_client.resource_groups.create_or_update(
                name=name,
                parameters={"location": location}
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
