"""
Self-Deployment Module
Handles deployment of Bragi Builder itself to Azure App Service
"""
import os
import json
import subprocess
import time
from typing import Dict, Optional, List
from datetime import datetime
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceExistsError, HttpResponseError
from azure.identity import DefaultAzureCredential


class AppDeploymentManager:
    """Manages self-deployment of Bragi Builder to Azure App Service"""
    
    def __init__(self, azure_client=None):
        """Initialize with Azure client or create new one"""
        if azure_client:
            self.resource_client = azure_client.resource_client
            self.web_client = azure_client.web_client
            self.subscription_id = azure_client.subscription_id
            self.credential = azure_client.credential
        else:
            # Create new Azure client for deployment
            self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
            if not self.subscription_id:
                raise ValueError("AZURE_SUBSCRIPTION_ID environment variable is required")
            
            self.credential = DefaultAzureCredential(exclude_environment_credential=True)
            self.resource_client = ResourceManagementClient(
                self.credential,
                self.subscription_id
            )
            self.web_client = WebSiteManagementClient(
                self.credential,
                self.subscription_id
            )
        
        self.deployments = {}  # Track deployment operations
    
    def validate_deployment_config(self, config: Dict) -> Dict:
        """Validate deployment configuration"""
        errors = []
        warnings = []
        
        # Required fields
        required_fields = ['resource_group', 'app_service_name', 'location']
        for field in required_fields:
            if not config.get(field):
                errors.append(f"{field} is required")
        
        # Validate app service name (must be globally unique)
        app_service_name = config.get('app_service_name', '')
        if app_service_name:
            if len(app_service_name) < 3 or len(app_service_name) > 60:
                errors.append("App Service name must be 3-60 characters")
            if not app_service_name.replace('-', '').replace('_', '').isalnum():
                errors.append("App Service name can only contain letters, numbers, hyphens, and underscores")
        
        # Validate SKU
        valid_skus = ['F1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3']
        sku = config.get('sku', 'B1')
        if sku not in valid_skus:
            warnings.append(f"SKU {sku} may not be valid. Valid SKUs: {', '.join(valid_skus)}")
        
        # Check if resource group exists
        resource_group = config.get('resource_group')
        if resource_group:
            try:
                rg = self.resource_client.resource_groups.get(resource_group)
                if rg:
                    warnings.append(f"Resource group '{resource_group}' already exists")
            except:
                pass  # Resource group doesn't exist, which is fine
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def check_app_service_name_availability(self, app_service_name: str) -> Dict:
        """Check if App Service name is available"""
        try:
            # Use Azure CLI to check name availability (more reliable)
            result = subprocess.run(
                ['az', 'webapp', 'list', '--query', f"[?name=='{app_service_name}'].name", '-o', 'json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                existing = json.loads(result.stdout)
                if existing:
                    return {
                        'available': False,
                        'message': f"App Service name '{app_service_name}' is already taken"
                    }
                else:
                    return {
                        'available': True,
                        'message': f"App Service name '{app_service_name}' is available"
                    }
            else:
                # Fallback: try to check via SDK
                return {
                    'available': True,  # Assume available if check fails
                    'message': 'Could not verify availability, proceeding...'
                }
        except Exception as e:
            return {
                'available': True,  # Assume available if check fails
                'message': f'Availability check failed: {str(e)}'
            }
    
    def create_resource_group(self, name: str, location: str) -> Dict:
        """Create resource group"""
        try:
            resource_group_params = {
                'location': location,
                'tags': {
                    'CreatedBy': 'Bragi Builder',
                    'Purpose': 'Self-Deployment',
                    'CreatedDate': datetime.now().strftime('%Y-%m-%d')
                }
            }
            
            rg = self.resource_client.resource_groups.create_or_update(
                name,
                resource_group_params
            )
            
            return {
                'success': True,
                'resource_group': rg.name,
                'location': rg.location
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_app_service_plan(self, name: str, resource_group: str, location: str, sku: str = 'B1') -> Dict:
        """Create App Service Plan"""
        try:
            # Map SKU to proper tier and size
            sku_parts = {
                'F1': ('Free', 'F1'),
                'B1': ('Basic', 'B1'),
                'B2': ('Basic', 'B2'),
                'B3': ('Basic', 'B3'),
                'S1': ('Standard', 'S1'),
                'S2': ('Standard', 'S2'),
                'S3': ('Standard', 'S3'),
                'P1': ('Premium', 'P1'),
                'P2': ('Premium', 'P2'),
                'P3': ('Premium', 'P3'),
            }
            
            tier, size = sku_parts.get(sku, ('Basic', 'B1'))
            
            plan_params = {
                'location': location,
                'sku': {
                    'name': size,
                    'tier': tier
                },
                'kind': 'linux',
                'reserved': True  # Linux plan
            }
            
            print(f"Creating App Service Plan '{name}' with SKU {sku} ({tier}/{size})...")
            
            # Create the plan - this is a long-running operation
            plan_poller = self.web_client.app_service_plans.begin_create_or_update(
                resource_group,
                name,
                plan_params
            )
            
            # Wait for the operation to complete
            plan = plan_poller.result()
            
            print(f"App Service Plan created: {plan.name}, SKU: {plan.sku.name}")
            
            return {
                'success': True,
                'plan_name': plan.name,
                'sku': sku,
                'plan_id': plan.id
            }
        except ResourceExistsError:
            # Plan already exists, get it
            try:
                plan = self.web_client.app_service_plans.get(resource_group, name)
                print(f"App Service Plan '{name}' already exists, reusing it")
                return {
                    'success': True,
                    'plan_name': plan.name,
                    'sku': sku,
                    'plan_id': plan.id,
                    'message': 'App Service Plan already exists, reusing it'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"App Service Plan exists but could not be retrieved: {str(e)}"
                }
        except HttpResponseError as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            print(f"HTTP Error creating App Service Plan: {error_msg}")
            return {
                'success': False,
                'error': f"Failed to create App Service Plan: {error_msg}",
                'error_details': {
                    'status_code': e.status_code if hasattr(e, 'status_code') else None,
                    'message': error_msg
                }
            }
        except Exception as e:
            error_msg = str(e)
            print(f"Error creating App Service Plan: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f"Failed to create App Service Plan: {error_msg}",
                'error_type': type(e).__name__
            }
    
    def create_app_service(self, name: str, resource_group: str, plan_name: str, location: str) -> Dict:
        """Create App Service"""
        try:
            # First verify the App Service Plan exists
            try:
                plan = self.web_client.app_service_plans.get(resource_group, plan_name)
                if not plan:
                    return {
                        'success': False,
                        'error': f"App Service Plan '{plan_name}' not found in resource group '{resource_group}'"
                    }
                print(f"Verified App Service Plan exists: {plan.name}")
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Failed to verify App Service Plan: {str(e)}"
                }
            
            app_params = {
                'location': location,
                'server_farm_id': f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/serverfarms/{plan_name}",
                'site_config': {
                    'linux_fx_version': 'PYTHON|3.11',
                    'always_on': True,
                    'web_sockets_enabled': True,
                    'app_settings': []
                },
                'https_only': True
            }
            
            print(f"Creating App Service '{name}' in resource group '{resource_group}'...")
            print(f"Using App Service Plan: {plan_name}")
            
            # Create the App Service - this is a long-running operation
            app_poller = self.web_client.web_apps.begin_create_or_update(
                resource_group,
                name,
                app_params
            )
            
            # Wait for the operation to complete
            app = app_poller.result()
            
            print(f"App Service created: {app.name}, State: {app.state}, Hostname: {app.default_host_name}")
            
            return {
                'success': True,
                'app_name': app.name,
                'default_host_name': app.default_host_name,
                'state': app.state,
                'id': app.id
            }
        except ResourceExistsError:
            # App Service already exists, try to get it
            try:
                app = self.web_client.web_apps.get(resource_group, name)
                print(f"App Service '{name}' already exists, using existing instance")
                return {
                    'success': True,
                    'app_name': app.name,
                    'default_host_name': app.default_host_name,
                    'state': app.state,
                    'id': app.id,
                    'message': 'App Service already exists, using existing instance'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"App Service '{name}' already exists but could not be retrieved: {str(e)}"
                }
        except HttpResponseError as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            print(f"HTTP Error creating App Service: {error_msg}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text if hasattr(e.response, 'text') else e.response}")
            return {
                'success': False,
                'error': f"Failed to create App Service: {error_msg}",
                'error_details': {
                    'status_code': e.status_code if hasattr(e, 'status_code') else None,
                    'message': error_msg
                }
            }
        except Exception as e:
            error_msg = str(e)
            print(f"Error creating App Service: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f"Failed to create App Service: {error_msg}",
                'error_type': type(e).__name__
            }
    
    def verify_app_service_exists(self, name: str, resource_group: str) -> Dict:
        """Verify that App Service was created successfully"""
        try:
            app = self.web_client.web_apps.get(resource_group, name)
            return {
                'exists': True,
                'app_name': app.name,
                'state': app.state,
                'default_host_name': app.default_host_name,
                'id': app.id
            }
        except Exception as e:
            return {
                'exists': False,
                'error': str(e)
            }
    
    def enable_managed_identity(self, app_name: str, resource_group: str) -> Dict:
        """Enable Managed Identity for App Service"""
        try:
            # Actually enable managed identity
            identity_result = self.web_client.web_apps.update(
                resource_group,
                app_name,
                {
                    'identity': {
                        'type': 'SystemAssigned'
                    }
                }
            )
            
            principal_id = None
            if identity_result.identity:
                principal_id = identity_result.identity.principal_id
            
            return {
                'success': True,
                'principal_id': principal_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def configure_app_settings(self, app_name: str, resource_group: str, settings: Dict) -> Dict:
        """Configure App Service application settings"""
        try:
            # Get current settings
            current_settings = self.web_client.web_apps.list_application_settings(
                resource_group,
                app_name
            )
            
            # Merge with new settings
            app_settings = {}
            if current_settings.properties:
                app_settings.update(current_settings.properties)
            
            app_settings.update(settings)
            
            # Update settings
            self.web_client.web_apps.update_application_settings(
                resource_group,
                app_name,
                {
                    'properties': app_settings
                }
            )
            
            return {
                'success': True,
                'settings_count': len(app_settings)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def configure_github_deployment(self, app_name: str, resource_group: str, 
                                   repo_url: str, branch: str = 'main', 
                                   github_token: str = None) -> Dict:
        """Configure GitHub as deployment source (recommended for production)"""
        try:
            # Use Azure CLI to configure GitHub deployment
            # This is more reliable than SDK for GitHub integration
            cmd = [
                'az', 'webapp', 'deployment', 'source', 'config',
                '--name', app_name,
                '--resource-group', resource_group,
                '--repo-url', repo_url,
                '--branch', branch,
                '--manual-integration'  # Manual integration (no webhook setup)
            ]
            
            # If GitHub token provided, use it for private repos
            if github_token:
                cmd.extend(['--github-token', github_token])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'GitHub deployment configured: {repo_url} (branch: {branch})',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or result.stdout or 'Failed to configure GitHub deployment',
                    'output': result.stdout
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'GitHub configuration timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def deploy_from_github(self, app_name: str, resource_group: str, 
                          repo_url: str, branch: str = 'main') -> Dict:
        """Trigger a deployment from GitHub"""
        try:
            # Sync the deployment from GitHub
            result = subprocess.run(
                ['az', 'webapp', 'deployment', 'source', 'sync',
                 '--name', app_name,
                 '--resource-group', resource_group],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for sync
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Deployment from GitHub triggered successfully',
                    'output': result.stdout,
                    'note': 'Deployment is running in Azure. Check App Service logs for progress.'
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or result.stdout or 'Failed to sync from GitHub',
                    'output': result.stdout
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'GitHub sync timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def deploy_application(self, app_name: str, resource_group: str, source_path: str = '.') -> Dict:
        """Deploy application code to App Service"""
        try:
            # Get the absolute path to ensure we're deploying from the right location
            import os
            abs_source_path = os.path.abspath(source_path)
            print(f"Deploying from: {abs_source_path}")
            
            # First, ensure we have a startup.sh file
            startup_file = os.path.join(abs_source_path, 'startup.sh')
            if not os.path.exists(startup_file):
                print("Warning: startup.sh not found, creating default...")
                # Create a basic startup.sh if it doesn't exist
                with open(startup_file, 'w') as f:
                    f.write("""#!/bin/bash
PORT=${PORT:-8000}
if command -v gunicorn &> /dev/null; then
    gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 600 --worker-class eventlet --log-level info app:app
else
    export WEBSITES_PORT=$PORT
    python3 app.py
fi
""")
                os.chmod(startup_file, 0o755)
            
            # First, set the startup file separately (az webapp up doesn't support --startup-file)
            print(f"Setting startup file: startup.sh")
            startup_result = subprocess.run(
                ['az', 'webapp', 'config', 'set',
                 '--name', app_name,
                 '--resource-group', resource_group,
                 '--startup-file', 'startup.sh'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if startup_result.returncode != 0:
                print(f"Warning: Failed to set startup file: {startup_result.stderr}")
            else:
                print("✓ Startup file configured")
            
            # Use Azure CLI for deployment
            # az webapp up will:
            # 1. Create a .deployment file if needed
            # 2. Deploy the code
            # 3. Configure the runtime
            # Note: This can take 15-20 minutes for first deployment
            print(f"Running: az webapp up --name {app_name} --resource-group {resource_group} --runtime PYTHON:3.11")
            print("Note: This may take 15-20 minutes for the first deployment. Please be patient...")
            
            result = None
            try:
                result = subprocess.run(
                    ['az', 'webapp', 'up',
                     '--name', app_name,
                     '--resource-group', resource_group,
                     '--runtime', 'PYTHON:3.11'],
                    cwd=abs_source_path,
                    capture_output=True,
                    text=True,
                    timeout=1800  # 30 minute timeout (first deployments can take 15-20 min)
                )
                
                print(f"Deployment command exit code: {result.returncode}")
                if result.stdout:
                    print(f"Deployment stdout: {result.stdout[:1000]}")  # First 1000 chars
                if result.stderr:
                    print(f"Deployment stderr: {result.stderr[:1000]}")  # First 1000 chars
                
                if result.returncode == 0:
                    return {
                        'success': True,
                        'message': 'Application code deployed successfully',
                        'output': result.stdout
                    }
                else:
                    # Check if it's a non-critical error
                    error_output = result.stderr or result.stdout or 'Deployment failed'
                    
                    # Some errors are warnings but deployment might still work
                    if 'already exists' in error_output.lower() or 'already configured' in error_output.lower():
                        return {
                            'success': True,
                            'message': 'Application appears to be deployed (may have been already configured)',
                            'output': result.stdout,
                            'warning': error_output
                        }
                    
                    return {
                        'success': False,
                        'error': error_output,
                        'output': result.stdout,
                        'exit_code': result.returncode
                    }
            except subprocess.TimeoutExpired:
                # Even if timeout, check if deployment might have succeeded
                print("Deployment command timed out. Checking if deployment succeeded anyway...")
                
                # Check if app is accessible
                try:
                    check_result = subprocess.run(
                        ['az', 'webapp', 'show',
                         '--name', app_name,
                         '--resource-group', resource_group,
                         '--query', 'state'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if check_result.returncode == 0 and 'Running' in check_result.stdout:
                        return {
                            'success': True,
                            'message': 'Deployment timed out, but App Service appears to be running. Deployment may have completed in the background.',
                            'warning': 'The deployment command timed out, but the app is running. You may want to verify the deployment manually.',
                            'manual_command': f'az webapp up --name {app_name} --resource-group {resource_group}'
                        }
                except Exception as e:
                    print(f"Could not verify app status: {e}")
                
                return {
                    'success': False,
                    'error': 'Deployment timed out after 30 minutes. The deployment may still be in progress. You can check status manually or try deploying again.',
                    'manual_command': f'az webapp up --name {app_name} --resource-group {resource_group}',
                    'note': 'First deployments can take 15-20 minutes. Consider running the deployment manually in a separate terminal.'
                }
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'Azure CLI not found. Please install Azure CLI to deploy code automatically.'
            }
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Exception during deployment: {error_trace}")
            return {
                'success': False,
                'error': str(e),
                'error_trace': error_trace
            }
    
    def deploy_bragi_builder(self, config: Dict) -> Dict:
        """Complete deployment of Bragi Builder to Azure App Service"""
        deployment_id = f"self-deploy-{int(time.time())}"
        steps = []
        
        try:
            # Step 1: Validate configuration
            validation = self.validate_deployment_config(config)
            if not validation['valid']:
                return {
                    'success': False,
                    'deployment_id': deployment_id,
                    'error': 'Configuration validation failed',
                    'errors': validation['errors']
                }
            
            steps.append({'step': 'validation', 'status': 'completed', 'message': 'Configuration validated'})
            
            # Step 2: Check App Service name availability
            name_check = self.check_app_service_name_availability(config['app_service_name'])
            if not name_check['available']:
                return {
                    'success': False,
                    'deployment_id': deployment_id,
                    'error': name_check['message']
                }
            
            steps.append({'step': 'name_check', 'status': 'completed', 'message': name_check['message']})
            
            # Step 3: Create resource group
            print(f"Step 3: Creating resource group '{config['resource_group']}'...")
            rg_result = self.create_resource_group(config['resource_group'], config['location'])
            if not rg_result['success']:
                return {
                    'success': False,
                    'deployment_id': deployment_id,
                    'error': f"Failed to create resource group: {rg_result.get('error')}",
                    'steps': steps
                }
            
            steps.append({'step': 'resource_group', 'status': 'completed', 'message': f"Resource group '{config['resource_group']}' created"})
            
            # Step 4: Create App Service Plan
            plan_name = config.get('app_service_plan', f"{config['app_service_name']}-plan")
            print(f"Step 4: Creating App Service Plan '{plan_name}'...")
            plan_result = self.create_app_service_plan(
                plan_name,
                config['resource_group'],
                config['location'],
                config.get('sku', 'B1')
            )
            
            if not plan_result['success']:
                error_details = plan_result.get('error_details', {})
                error_msg = plan_result.get('error', 'Unknown error')
                steps.append({
                    'step': 'app_service_plan', 
                    'status': 'failed', 
                    'message': f"Failed to create App Service Plan: {error_msg}",
                    'error_details': error_details
                })
                return {
                    'success': False,
                    'deployment_id': deployment_id,
                    'error': f"Failed to create App Service Plan: {error_msg}",
                    'steps': steps,
                    'error_details': error_details
                }
            
            steps.append({
                'step': 'app_service_plan', 
                'status': 'completed', 
                'message': f"App Service Plan '{plan_name}' created",
                'plan_id': plan_result.get('plan_id')
            })
            
            # Step 5: Create App Service
            print(f"Step 5: Creating App Service '{config['app_service_name']}'...")
            app_result = self.create_app_service(
                config['app_service_name'],
                config['resource_group'],
                plan_name,
                config['location']
            )
            
            if not app_result['success']:
                error_details = app_result.get('error_details', {})
                error_msg = app_result.get('error', 'Unknown error')
                steps.append({
                    'step': 'app_service', 
                    'status': 'failed', 
                    'message': f"Failed to create App Service: {error_msg}",
                    'error_details': error_details
                })
                return {
                    'success': False,
                    'deployment_id': deployment_id,
                    'error': f"Failed to create App Service: {error_msg}",
                    'steps': steps,
                    'error_details': error_details
                }
            
            # Verify App Service was created
            verify_result = self.verify_app_service_exists(
                config['app_service_name'],
                config['resource_group']
            )
            
            if not verify_result.get('exists'):
                steps.append({
                    'step': 'app_service_verification', 
                    'status': 'warning', 
                    'message': f"App Service creation reported success but verification failed: {verify_result.get('error')}"
                })
            
            steps.append({
                'step': 'app_service', 
                'status': 'completed', 
                'message': f"App Service '{config['app_service_name']}' created successfully",
                'app_state': app_result.get('state', 'Unknown'),
                'hostname': app_result.get('default_host_name', 'N/A')
            })
            
            # Step 6: Enable Managed Identity
            print(f"Step 6: Enabling Managed Identity...")
            identity_result = self.enable_managed_identity(
                config['app_service_name'],
                config['resource_group']
            )
            
            if identity_result['success']:
                steps.append({'step': 'managed_identity', 'status': 'completed', 'message': 'Managed Identity enabled'})
            else:
                steps.append({'step': 'managed_identity', 'status': 'warning', 'message': f"Managed Identity warning: {identity_result.get('error')}"})
            
            # Step 7: Configure application settings
            print(f"Step 7: Configuring application settings...")
            app_settings = {
                'SCM_DO_BUILD_DURING_DEPLOYMENT': 'true',
                'ENABLE_ORYX_BUILD': 'true',
                'PYTHON_VERSION': '3.11',
                'WEBSITES_PORT': '8000'
            }
            
            # Add custom settings from config
            if config.get('app_settings'):
                app_settings.update(config['app_settings'])
            
            settings_result = self.configure_app_settings(
                config['app_service_name'],
                config['resource_group'],
                app_settings
            )
            
            if settings_result['success']:
                steps.append({'step': 'app_settings', 'status': 'completed', 'message': 'Application settings configured'})
            else:
                steps.append({'step': 'app_settings', 'status': 'warning', 'message': f"Settings warning: {settings_result.get('error')}"})
            
            # Step 8: Deploy application code
            print(f"Step 8: Deploying application code to App Service '{config['app_service_name']}'...")
            deploy_result = self.deploy_application(
                config['app_service_name'],
                config['resource_group'],
                config.get('source_path', '.')
            )
            
            if deploy_result['success']:
                steps.append({
                    'step': 'code_deployment', 
                    'status': 'completed', 
                    'message': 'Application code deployed successfully'
                })
            else:
                # Don't fail the entire deployment if code deployment fails
                # The infrastructure is created, user can deploy code manually
                error_msg = deploy_result.get('error', 'Unknown error')
                steps.append({
                    'step': 'code_deployment', 
                    'status': 'warning', 
                    'message': f'Code deployment had issues: {error_msg}. You can deploy manually using: az webapp up --name {config["app_service_name"]} --resource-group {config["resource_group"]}',
                    'error': error_msg
                })
                print(f"Warning: Code deployment failed: {error_msg}")
                if deploy_result.get('output'):
                    print(f"Deployment output: {deploy_result['output']}")
            
            # Construct App Service URL
            app_url = f"https://{config['app_service_name']}.azurewebsites.net"
            
            # Store deployment info
            self.deployments[deployment_id] = {
                'config': config,
                'steps': steps,
                'status': 'completed',
                'app_url': app_url,
                'app_service_name': config['app_service_name'],
                'resource_group': config['resource_group'],
                'created_at': datetime.now().isoformat()
            }
            
            return {
                'success': True,
                'deployment_id': deployment_id,
                'app_url': app_url,
                'app_service_name': config['app_service_name'],
                'resource_group': config['resource_group'],
                'steps': steps,
                'message': 'Bragi Builder infrastructure deployed successfully!',
                'next_steps': [
                    'Deploy application code using: az webapp up --name ' + config['app_service_name'] + ' --resource-group ' + config['resource_group'],
                    'Configure Azure AD authentication in App Service settings',
                    'Set environment variables (AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET, etc.)',
                    'Grant Managed Identity permissions to access Azure resources',
                    'Configure Azure Files mount for SQLite persistence (optional)'
                ]
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Deployment error: {error_trace}")
            return {
                'success': False,
                'deployment_id': deployment_id,
                'error': str(e),
                'error_trace': error_trace,
                'steps': steps
            }
