"""
Bragi Builder - Azure ARM Template Manager
Main Flask application
"""
import os
import json
import threading
import time
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from src.azure_client import AzureClient
from src.template_manager import TemplateManager
from src.deployment_manager import DeploymentManager
from src.offline_review import OfflineReviewManager
from src.workload_config import WorkloadConfigManager
from src.template_wizard import TemplateWizard
from src.vnet_validator import VNetValidator
from src.deployment_store import DeploymentStore, DeploymentRecord
from src.metrics_dashboard import metrics_bp

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*")

# Set Azure subscription ID for Azure CLI authentication
os.environ['AZURE_SUBSCRIPTION_ID'] = '693bb5f4-bea9-4714-b990-55d5a4032ae1'

# Initialize managers
try:
    azure_client = AzureClient()
    template_manager = TemplateManager()
    deployment_manager = DeploymentManager(azure_client, template_manager)
except Exception as e:
    print(f"Warning: Failed to initialize Azure client: {e}")
    azure_client = None
    template_manager = TemplateManager()
    deployment_manager = None

# Initialize offline review and workload config managers
offline_review = OfflineReviewManager()
workload_config = WorkloadConfigManager()
template_wizard = TemplateWizard()

# Initialize deployment store
deployment_store = DeploymentStore()

# Register blueprints
app.register_blueprint(metrics_bp)

# Deployment status tracking
deployment_statuses = {}

def record_deployment_start(deployment_name, resource_group_name, template_name, deployment_data):
    """Record deployment start in the data store"""
    try:
        # Create initial deployment record
        record = DeploymentRecord(
            deployment_name=deployment_name,
            resource_group=resource_group_name,
            template_name=template_name,
            location=deployment_data.get('location', 'unknown'),
            project=deployment_data.get('project', 'unknown'),
            environment=deployment_data.get('environment', 'unknown'),
            status='Running',
            start_time=datetime.datetime.now(),
            end_time=None,
            duration_seconds=None,
            user_initiated='system',  # Could be enhanced with actual user tracking
            parameters=deployment_data.get('parameters', {}),
            outputs=None,
            error_details=None,
            resource_count=0,  # Will be updated when deployment completes
            resource_types=None,  # Will be updated when deployment completes
            retry_count=0,
            estimated_cost=None,  # Could be enhanced with cost estimation
            validation_passed=True,  # Could be enhanced with validation tracking
            vnet_address_space=deployment_data.get('vnet_address_space'),
            sql_password_complexity=deployment_data.get('sql_password_complexity', True)
        )
        
        # Create the record
        deployment_store.create_deployment(record)
        
    except Exception as e:
        print(f"Error recording deployment start: {e}")

def record_deployment_completion(deployment_name, resource_group_name, status, duration_seconds, outputs, error_details):
    """Record deployment completion in the data store"""
    try:
        # Get deployment info from deployment manager
        deployment_info = None
        if deployment_manager and deployment_name in deployment_manager.deployments:
            deployment_info = deployment_manager.deployments[deployment_name]
        
        # Create deployment record
        record = DeploymentRecord(
            deployment_name=deployment_name,
            resource_group=resource_group_name,
            template_name=deployment_info.get('template_name', 'unknown') if deployment_info else 'unknown',
            location=deployment_info.get('location', 'unknown') if deployment_info else 'unknown',
            project=deployment_info.get('project', 'unknown') if deployment_info else 'unknown',
            environment=deployment_info.get('environment', 'unknown') if deployment_info else 'unknown',
            status=status,
            start_time=deployment_info.get('start_time') if deployment_info else None,
            end_time=datetime.datetime.now(),
            duration_seconds=duration_seconds,
            user_initiated='system',  # Could be enhanced with actual user tracking
            parameters=deployment_info.get('parameters') if deployment_info else None,
            outputs=outputs,
            error_details=error_details,
            resource_count=0,  # Could be enhanced to count actual resources
            resource_types=None,  # Could be enhanced to track resource types
            retry_count=0,  # Could be enhanced to track retries
            estimated_cost=None,  # Could be enhanced with cost estimation
            validation_passed=True,  # Could be enhanced with validation tracking
            vnet_address_space=None,  # Could be enhanced with VNet tracking
            sql_password_complexity=True  # Could be enhanced with password validation tracking
        )
        
        # Check if deployment already exists
        existing = deployment_store.get_deployment(deployment_name)
        if existing:
            # Update existing record
            updates = {
                'status': status,
                'end_time': record.end_time,
                'duration_seconds': duration_seconds,
                'outputs': outputs,
                'error_details': error_details,
                'updated_at': datetime.datetime.now()
            }
            deployment_store.update_deployment(deployment_name, updates)
        else:
            # Create new record
            deployment_store.create_deployment(record)
            
    except Exception as e:
        print(f"Error recording deployment completion: {e}")

def monitor_deployment_status(deployment_name, resource_group_name):
    """Monitor deployment status and emit updates via WebSocket"""
    try:
        start_time = time.time()
        last_status = None
        status_count = 0
        
        while True:
            if deployment_name not in deployment_statuses:
                break
                
            # Get deployment status from Azure
            status = azure_client.get_deployment_status(resource_group_name, deployment_name)
            
            if status:
                current_status = status['provisioning_state']
                current_time = status['timestamp']
                elapsed_time = int(time.time() - start_time)
                
                # Create more informative status message
                status_message = get_detailed_status_message(current_status, elapsed_time)
                
                # Update our tracking
                deployment_statuses[deployment_name]['status'] = current_status
                deployment_statuses[deployment_name]['timestamp'] = current_time.isoformat()
                deployment_statuses[deployment_name]['elapsed_time'] = elapsed_time
                deployment_statuses[deployment_name]['status_message'] = status_message
                
                # Also update deployment manager's tracking
                if deployment_name in deployment_manager.deployments:
                    deployment_manager.deployments[deployment_name]['status'] = current_status
                    deployment_manager.deployments[deployment_name]['timestamp'] = current_time.isoformat()
                    deployment_manager.deployments[deployment_name]['outputs'] = status.get('outputs', {})
                
                # Only emit if status changed or every 30 seconds
                if current_status != last_status or status_count % 6 == 0:
                    socketio.emit('deployment_update', {
                        'deployment_name': deployment_name,
                        'status': current_status,
                        'status_message': status_message,
                        'timestamp': current_time.isoformat(),
                        'elapsed_time': elapsed_time,
                        'outputs': status.get('outputs', {})
                    })
                    last_status = current_status
                
                status_count += 1
                
                # If deployment is complete (success or failed), stop monitoring
                if current_status in ['Succeeded', 'Failed', 'Canceled']:
                    deployment_statuses[deployment_name]['completed'] = True
                    
                    # Get detailed error information if failed
                    error_details = None
                    if current_status == 'Failed':
                        try:
                            error_result = deployment_manager.get_deployment_errors(deployment_name, resource_group_name)
                            if error_result.get('success'):
                                error_details = error_result.get('errors', [])
                                print(f"Deployment {deployment_name} failed with {len(error_details)} error(s)")
                        except Exception as e:
                            print(f"Could not get error details: {e}")
                    
                    # Update deployment manager's final status
                    if deployment_name in deployment_manager.deployments:
                        deployment_manager.deployments[deployment_name]['status'] = current_status
                        deployment_manager.deployments[deployment_name]['timestamp'] = current_time.isoformat()
                        deployment_manager.deployments[deployment_name]['outputs'] = status.get('outputs', {})
                        if error_details:
                            deployment_manager.deployments[deployment_name]['error_details'] = error_details
                    
                    # Record deployment completion in data store
                    try:
                        record_deployment_completion(deployment_name, resource_group_name, current_status, 
                                                   elapsed_time, status.get('outputs', {}), error_details)
                    except Exception as e:
                        print(f"Error recording deployment completion: {e}")
                    
                    # Send final status update
                    final_update = {
                        'deployment_name': deployment_name,
                        'status': current_status,
                        'status_message': get_detailed_status_message(current_status, elapsed_time, final=True),
                        'timestamp': current_time.isoformat(),
                        'elapsed_time': elapsed_time,
                        'outputs': status.get('outputs', {}),
                        'completed': True
                    }
                    
                    if error_details:
                        final_update['error_details'] = error_details
                    
                    socketio.emit('deployment_update', final_update)
                    break
            else:
                # Deployment not found, stop monitoring
                socketio.emit('deployment_error', {
                    'deployment_name': deployment_name,
                    'error': 'Deployment not found in Azure'
                })
                break
                
            time.sleep(10)  # Check every 10 seconds as requested
            
    except Exception as e:
        print(f"Error monitoring deployment {deployment_name}: {e}")
        socketio.emit('deployment_error', {
            'deployment_name': deployment_name,
            'error': str(e)
        })
    finally:
        # Clean up
        if deployment_name in deployment_statuses:
            del deployment_statuses[deployment_name]


def get_detailed_status_message(status, elapsed_time, final=False):
    """Generate detailed status messages for deployments"""
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
    
    status_messages = {
        'Accepted': f'Deployment accepted and queued ({time_str})',
        'Running': f'Deployment in progress ({time_str})',
        'Creating': f'Creating resources ({time_str})',
        'Updating': f'Updating resources ({time_str})',
        'Deleting': f'Deleting resources ({time_str})',
        'Succeeded': f'Deployment completed successfully ({time_str})' if final else f'Deployment succeeded ({time_str})',
        'Failed': f'Deployment failed ({time_str})' if final else f'Deployment failed ({time_str})',
        'Canceled': f'Deployment canceled ({time_str})' if final else f'Deployment canceled ({time_str})'
    }
    
    return status_messages.get(status, f'Status: {status} ({time_str})')


@app.route('/')
def index():
    """Main dashboard"""
    templates = template_manager.list_templates()
    deployments = deployment_manager.list_deployments() if deployment_manager else []
    
    return render_template('index.html', 
                         templates=templates, 
                         deployments=deployments)


@app.route('/templates')
def templates():
    """Template management page"""
    templates = template_manager.list_templates()
    template_details = {}
    
    for template_name in templates:
        template = template_manager.get_template(template_name)
        if template:
            template_details[template_name] = {
                "parameters": template_manager.get_template_parameters(template),
                "validation": template_manager.validate_template(template)
            }
    
    return render_template('templates.html', 
                         templates=templates, 
                         template_details=template_details)


@app.route('/templates/<template_name>')
def template_detail(template_name):
    """Template detail page"""
    template = template_manager.get_template(template_name)
    if not template:
        flash(f"Template {template_name} not found", "error")
        return redirect(url_for('templates'))
    
    parameters = template_manager.get_template_parameters(template)
    validation = template_manager.validate_template(template)
    
    return render_template('template_detail.html',
                         template_name=template_name,
                         template=template,
                         parameters=parameters,
                         validation=validation)


@app.route('/templates/<template_name>/edit', methods=['GET', 'POST'])
def edit_template(template_name):
    """Edit template page"""
    if request.method == 'POST':
        try:
            template_data = request.get_json()
            template_manager.save_template(template_name, template_data)
            return jsonify({"success": True, "message": "Template saved successfully"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400
    
    template = template_manager.get_template(template_name)
    if not template:
        flash(f"Template {template_name} not found", "error")
        return redirect(url_for('templates'))
    
    return render_template('edit_template.html',
                         template_name=template_name,
                         template=template)


@app.route('/deployments')
def deployments():
    """Deployments page"""
    if not deployment_manager:
        flash("Azure client not configured", "error")
        return redirect(url_for('index'))
    
    deployments = deployment_manager.list_deployments()
    resource_groups = []
    
    try:
        resource_groups = azure_client.list_resource_groups()
    except Exception as e:
        flash(f"Failed to load resource groups: {str(e)}", "error")
    
    # Get available templates
    templates = template_manager.list_templates()
    
    return render_template('deployments.html',
                         deployments=deployments,
                         resource_groups=resource_groups,
                         templates=templates)


@app.route('/metrics')
def metrics():
    """Metrics dashboard page"""
    return render_template('metrics.html')


@app.route('/deploy', methods=['POST'])
def deploy():
    """Deploy a template"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        data = request.get_json()
        print(f"Received deployment data: {data}")
        template_name = data.get('template_name')
        resource_group = data.get('resource_group')
        parameters = data.get('parameters', {})
        
        # Add SQL admin parameters - use defaults if not provided
        sql_admin_login = data.get('sql_admin_login') or 'sqladmin'
        sql_admin_password = data.get('sql_admin_password')
        
        parameters['sqlAdministratorLogin'] = {
            "value": sql_admin_login
        }
        
        if sql_admin_password:
            parameters['sqlAdministratorLoginPassword'] = {
                "value": sql_admin_password
            }
        
        # Handle any additional JSON parameters from the form
        if data.get('parameters'):
            additional_params = data.get('parameters')
            for key, value in additional_params.items():
                parameters[key] = {
                    "value": value
                }
        
        print(f"Parsed values - template_name: '{template_name}', resource_group: '{resource_group}'")
        print(f"SQL Admin Login: '{sql_admin_login}', Password provided: {bool(sql_admin_password)}")
        print(f"Parameters: {parameters}")
        
        if not template_name or not resource_group:
            return jsonify({"success": False, "message": "Template name and resource group are required"}), 400
        
        # Validate resource group name if it's a new resource group
        if resource_group.startswith('__new__') or not azure_client.get_resource_group(resource_group):
            # If it's a new resource group, validate the name
            if resource_group.startswith('__new__'):
                new_rg_name = data.get('new_resource_group_name', '').strip()
                if not new_rg_name:
                    return jsonify({"success": False, "message": "New resource group name is required"}), 400
                resource_group = new_rg_name
            
            # Validate the resource group name
            validation = azure_client.validate_resource_group_name(resource_group)
            if not validation["is_valid"]:
                return jsonify({
                    "success": False, 
                    "message": f"Resource group validation failed: {validation['error']}",
                    "suggestion": validation.get("suggestion", "")
                }), 400
        
        # Check if resource group exists, create if not
        rg = azure_client.get_resource_group(resource_group)
        if not rg:
            location = data.get('location', 'East US')
            # Add Bragi tags for manual deployments
            tags = {
                "Environment": "Manual",
                "DeploymentType": "Manual Template",
                "TemplateName": template_name
            }
            azure_client.create_resource_group(resource_group, location, tags)
        
        # Deploy the template
        result = deployment_manager.deploy_template(
            template_name=template_name,
            resource_group_name=resource_group,
            parameters=parameters
        )
        
        # Start monitoring the deployment
        deployment_name = result.get('deployment_name')
        if deployment_name:
            deployment_statuses[deployment_name] = {
                'status': 'Running',
                'started': True,
                'completed': False
            }
            
            # Record deployment start in data store
            try:
                record_deployment_start(deployment_name, resource_group, template_name, data)
            except Exception as e:
                print(f"Error recording deployment start: {e}")
            
            # Start monitoring in a separate thread
            monitor_thread = threading.Thread(
                target=monitor_deployment_status,
                args=(deployment_name, resource_group)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
        
        return jsonify({"success": True, "deployment": result})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/deployments/<deployment_name>/status')
def deployment_status(deployment_name):
    """Get deployment status"""
    if not deployment_manager:
        return jsonify({"error": "Azure client not configured"}), 400
    
    try:
        status = deployment_manager.get_deployment_status(deployment_name)
        if not status:
            return jsonify({"error": "Deployment not found"}), 404
        
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/deploy-environment', methods=['POST'])
def deploy_environment():
    """Deploy a complete environment"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        data = request.get_json()
        environment = data.get('environment')
        project_name = data.get('project_name', 'bragi')
        location = data.get('location', 'East US')
        sql_password = data.get('sql_password')
        
        if not environment or not sql_password:
            return jsonify({"success": False, "message": "Environment and SQL password are required"}), 400
        
        # Validate resource group name before creating
        resource_group_name = f"{project_name}-{environment}-rg"
        validation = azure_client.validate_resource_group_name(resource_group_name)
        if not validation["is_valid"]:
            return jsonify({
                "success": False, 
                "message": f"Resource group validation failed: {validation['error']}",
                "suggestion": validation.get("suggestion", "")
            }), 400
        
        result = deployment_manager.create_environment_deployment(
            environment=environment,
            project_name=project_name,
            location=location,
            sql_password=sql_password
        )
        
        return jsonify({"success": True, "deployment": result})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/environments/<environment>/resources')
def environment_resources(environment):
    """Get resources for an environment"""
    if not deployment_manager:
        return jsonify({"error": "Azure client not configured"}), 400
    
    try:
        project_name = request.args.get('project_name', 'bragi')
        resources = deployment_manager.get_environment_resources(environment, project_name)
        return jsonify(resources)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/environments/<environment>/endpoints')
def environment_endpoints(environment):
    """Get public-facing endpoints for an environment"""
    if not deployment_manager:
        flash("Azure client not configured", "error")
        return redirect(url_for('environments_page'))
    
    try:
        project_name = request.args.get('project_name', 'bragi')
        specified_rg = request.args.get('resource_group')
        
        target_rg_name = None
        
        if specified_rg:
            # Use the specified resource group if provided
            target_rg_name = specified_rg
        else:
            # Find the actual resource group name by looking for Bragi-managed resource groups
            # that match the environment and project
            resource_groups = azure_client.list_resource_groups()
            
            for rg in resource_groups:
                if rg.tags and rg.tags.get('CreatedBy') == 'Bragi Builder':
                    rg_project = rg.tags.get('Project', '')
                    rg_environment = rg.tags.get('Environment', '')
                    
                    # Match by project and environment from tags
                    if (rg_project.lower() == project_name.lower() and 
                        rg_environment.lower() == environment.lower()):
                        target_rg_name = rg.name
                        break
        
        if not target_rg_name:
            flash(f"Environment {environment} not found", "error")
            return redirect(url_for('environments_page'))
        
        endpoints = deployment_manager.get_environment_endpoints(environment, project_name, target_rg_name)
        
        return render_template('endpoints.html',
                             environment=environment,
                             project_name=project_name,
                             resource_group_name=target_rg_name,
                             endpoints=endpoints)
    except Exception as e:
        flash(f"Error loading endpoints: {str(e)}", "error")
        return redirect(url_for('environments_page'))


@app.route('/resource-groups')
def get_resource_groups():
    """Get all resource groups"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        resource_groups = azure_client.list_resource_groups()
        # Serialize ResourceGroup objects to dictionaries
        serialized_groups = []
        for rg in resource_groups:
            serialized_groups.append({
                "name": rg.name,
                "location": rg.location,
                "id": rg.id,
                "tags": rg.tags if rg.tags else {},
                "properties": {
                    "provisioning_state": rg.properties.provisioning_state if rg.properties else None
                }
            })
        return jsonify({"success": True, "resource_groups": serialized_groups})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/environments')
def environments_page():
    """Environment management page"""
    return render_template('environments.html')


@app.route('/api/regions')
def get_regions():
    """Get all available Azure regions"""
    if not azure_client:
        return jsonify({"error": "Azure client not configured"}), 400
    
    try:
        regions = azure_client.get_available_regions()
        return jsonify({"success": True, "regions": regions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/regions/<region>/validate')
def validate_region(region):
    """Validate deployment capabilities for a specific region"""
    if not azure_client:
        return jsonify({"error": "Azure client not configured"}), 400
    
    try:
        capabilities = azure_client.validate_region_capabilities(region)
        return jsonify({"success": True, "region": region, "capabilities": capabilities})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/vnet/validate')
def validate_vnet_address_space():
    """Validate VNet address space for overlaps"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        address_space = request.args.get('address_space')
        location = request.args.get('location')
        
        if not address_space:
            return jsonify({"success": False, "message": "address_space parameter is required"}), 400
        
        # Initialize VNet validator with existing Azure client
        vnet_validator = VNetValidator(azure_client)
        
        # Validate the address space
        validation_result = vnet_validator.check_address_space_overlap(address_space, location)
        
        return jsonify({
            "success": True,
            "validation": validation_result
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/api/vnet/common-spaces')
def get_common_address_spaces():
    """Get commonly used VNet address spaces"""
    try:
        vnet_validator = VNetValidator(azure_client)
        common_spaces = vnet_validator.get_common_address_spaces()
        
        return jsonify({
            "success": True,
            "common_spaces": common_spaces
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/api/resource-groups/validate')
def validate_resource_group_name():
    """Validate resource group name availability"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        name = request.args.get('name')
        if not name:
            return jsonify({"success": False, "message": "name parameter is required"}), 400
        
        validation_result = azure_client.validate_resource_group_name(name)
        
        return jsonify({
            "success": True,
            "validation": validation_result
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/environments/<environment>/delete-preview', methods=['GET'])
def get_delete_preview(environment):
    """Get deletion preview and validation information"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        project_name = request.args.get('project_name', 'bragi')
        resource_group_name = request.args.get('resource_group')
        
        # Use provided resource group name if available, otherwise try to find it
        target_rg_name = None
        
        if resource_group_name:
            # Use the provided resource group name directly
            target_rg_name = resource_group_name
        else:
            # Fallback: Find the actual resource group name by looking for Bragi-managed resource groups
            # that match the environment and project
            resource_groups = azure_client.list_resource_groups()
            
            for rg in resource_groups:
                if rg.tags and rg.tags.get('CreatedBy') == 'Bragi Builder':
                    rg_project = rg.tags.get('Project', '')
                    rg_environment = rg.tags.get('Environment', '')
                    
                    # Match by project and environment from tags
                    if (rg_project.lower() == project_name.lower() and 
                        rg_environment.lower() == environment.lower()):
                        target_rg_name = rg.name
                        break
        
        if not target_rg_name:
            return jsonify({"success": False, "message": f"Environment {environment} not found. Please provide resource_group parameter."}), 404
        
        result = deployment_manager.get_deletion_preview(environment, project_name, target_rg_name)
        
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/environments/<environment>', methods=['DELETE'])
def delete_environment(environment):
    """Delete an environment"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        project_name = request.args.get('project_name', 'bragi')
        resource_group_name = request.args.get('resource_group')
        
        # Use provided resource group name if available, otherwise try to find it
        target_rg_name = None
        
        if resource_group_name:
            # Use the provided resource group name directly
            target_rg_name = resource_group_name
        else:
            # Fallback: Find the actual resource group name by looking for Bragi-managed resource groups
            # that match the environment and project
            resource_groups = azure_client.list_resource_groups()
            
            for rg in resource_groups:
                if rg.tags and rg.tags.get('CreatedBy') == 'Bragi Builder':
                    rg_project = rg.tags.get('Project', '')
                    rg_environment = rg.tags.get('Environment', '')
                    
                    # Match by project and environment from tags
                    if (rg_project.lower() == project_name.lower() and 
                        rg_environment.lower() == environment.lower()):
                        target_rg_name = rg.name
                        break
        
        if not target_rg_name:
            return jsonify({"success": False, "message": f"Environment {environment} not found. Please provide resource_group parameter."}), 404
        
        # Verify the resource group exists
        rg = azure_client.get_resource_group(target_rg_name)
        if not rg:
            return jsonify({"success": False, "message": f"Resource group {target_rg_name} not found"}), 404
        
        result = deployment_manager.delete_environment(environment, project_name, target_rg_name)
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/api/delete-progress/<resource_group>')
def check_delete_progress(resource_group):
    """Check the progress of a resource group deletion"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        result = deployment_manager.check_delete_progress(resource_group)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/resource-groups/<resource_group>/start', methods=['POST'])
def start_resource_group(resource_group):
    """Start all resources in a resource group"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        # Get all resources in the resource group
        resources = azure_client.resource_client.resources.list_by_resource_group(resource_group)
        
        start_operations = []
        for resource in resources:
            try:
                # Check if resource supports start/stop operations
                if resource.type in ['Microsoft.Compute/virtualMachines', 'Microsoft.Web/sites', 'Microsoft.Network/applicationGateways']:
                    if resource.type == 'Microsoft.Compute/virtualMachines':
                        # Start VM
                        operation = azure_client.compute_client.virtual_machines.begin_start(
                            resource_group, resource.name
                        )
                        start_operations.append({
                            'resource_name': resource.name,
                            'resource_type': resource.type,
                            'operation': operation
                        })
                    elif resource.type == 'Microsoft.Web/sites':
                        # Start App Service
                        operation = azure_client.web_client.web_apps.start(
                            resource_group, resource.name
                        )
                        start_operations.append({
                            'resource_name': resource.name,
                            'resource_type': resource.type,
                            'operation': operation
                        })
                    elif resource.type == 'Microsoft.Network/applicationGateways':
                        # Start Application Gateway
                        operation = azure_client.network_client.application_gateways.begin_start(
                            resource_group, resource.name
                        )
                        start_operations.append({
                            'resource_name': resource.name,
                            'resource_type': resource.type,
                            'operation': operation
                        })
            except Exception as e:
                print(f"Error starting {resource.name}: {e}")
                continue
        
        return jsonify({
            "success": True,
            "message": f"Started {len(start_operations)} resources in {resource_group}",
            "operations": len(start_operations)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error starting resources: {str(e)}"
        }), 500

@app.route('/api/resource-groups/<resource_group>/stop', methods=['POST'])
def stop_resource_group(resource_group):
    """Stop all resources in a resource group"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        # Get all resources in the resource group
        resources = azure_client.resource_client.resources.list_by_resource_group(resource_group)
        
        stop_operations = []
        for resource in resources:
            try:
                # Check if resource supports start/stop operations
                if resource.type in ['Microsoft.Compute/virtualMachines', 'Microsoft.Web/sites', 'Microsoft.Network/applicationGateways']:
                    if resource.type == 'Microsoft.Compute/virtualMachines':
                        # Stop VM
                        operation = azure_client.compute_client.virtual_machines.begin_deallocate(
                            resource_group, resource.name
                        )
                        stop_operations.append({
                            'resource_name': resource.name,
                            'resource_type': resource.type,
                            'operation': operation
                        })
                    elif resource.type == 'Microsoft.Web/sites':
                        # Stop App Service
                        operation = azure_client.web_client.web_apps.stop(
                            resource_group, resource.name
                        )
                        stop_operations.append({
                            'resource_name': resource.name,
                            'resource_type': resource.type,
                            'operation': operation
                        })
                    elif resource.type == 'Microsoft.Network/applicationGateways':
                        # Stop Application Gateway
                        operation = azure_client.network_client.application_gateways.begin_stop(
                            resource_group, resource.name
                        )
                        stop_operations.append({
                            'resource_name': resource.name,
                            'resource_type': resource.type,
                            'operation': operation
                        })
            except Exception as e:
                print(f"Error stopping {resource.name}: {e}")
                continue
        
        return jsonify({
            "success": True,
            "message": f"Stopped {len(stop_operations)} resources in {resource_group}",
            "operations": len(stop_operations)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error stopping resources: {str(e)}"
        }), 500

@app.route('/api/resource-groups/<resource_group>/status')
def get_resource_group_status(resource_group):
    """Get status of all resources in a resource group"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        # Get all resources in the resource group
        resources = azure_client.resource_client.resources.list_by_resource_group(resource_group)
        
        resource_statuses = []
        for resource in resources:
            try:
                status = "Unknown"
                if resource.type == 'Microsoft.Compute/virtualMachines':
                    # Get VM status
                    vm = azure_client.compute_client.virtual_machines.get(
                        resource_group, resource.name, expand='instanceView'
                    )
                    if vm.instance_view and vm.instance_view.statuses:
                        for status_obj in vm.instance_view.statuses:
                            if status_obj.code.startswith('PowerState/'):
                                status = status_obj.code.split('/')[1]
                                break
                elif resource.type == 'Microsoft.Web/sites':
                    # Get App Service status
                    app = azure_client.web_client.web_apps.get(resource_group, resource.name)
                    status = app.state
                elif resource.type == 'Microsoft.Web/serverFarms':
                    # App Service Plan status
                    asp = azure_client.web_client.app_service_plans.get(resource_group, resource.name)
                    status = asp.status
                elif resource.type == 'Microsoft.Sql/servers':
                    # SQL Server is always running
                    status = "Running"
                elif resource.type == 'Microsoft.Sql/servers/databases':
                    # SQL Database status
                    try:
                        db_parts = resource.name.split('/')
                        if len(db_parts) == 2:
                            server_name, db_name = db_parts
                            db = azure_client.sql_client.databases.get(resource_group, server_name, db_name)
                            status = db.status
                        else:
                            status = "Running"
                    except:
                        status = "Running"
                elif resource.type == 'Microsoft.Storage/storageAccounts':
                    # Storage account is always running
                    status = "Running"
                elif resource.type == 'Microsoft.Network/virtualNetworks':
                    # VNet is always running
                    status = "Running"
                elif resource.type == 'Microsoft.Network/publicIPAddresses':
                    # Public IP is always running
                    status = "Running"
                elif resource.type == 'Microsoft.Network/networkSecurityGroups':
                    # NSG is always running
                    status = "Running"
                elif resource.type == 'Microsoft.Network/applicationGateways':
                    # Application Gateway status
                    try:
                        agw = azure_client.network_client.application_gateways.get(resource_group, resource.name)
                        status = agw.provisioning_state
                    except:
                        status = "Running"
                
                resource_statuses.append({
                    'name': resource.name,
                    'type': resource.type,
                    'status': status,
                    'location': resource.location
                })
            except Exception as e:
                print(f"Error getting status for {resource.name}: {e}")
                resource_statuses.append({
                    'name': resource.name,
                    'type': resource.type,
                    'status': 'Unknown',
                    'location': resource.location
                })
        
        return jsonify({
            "success": True,
            "resource_group": resource_group,
            "resources": resource_statuses,
            "total_resources": len(resource_statuses)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting resource status: {str(e)}"
        }), 500

@app.route('/api/deployment-resources/<deployment_name>')
def get_deployment_resources(deployment_name):
    """Get detailed resource status for a deployment"""
    if not azure_client:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        resource_group = request.args.get('resource_group')
        if not resource_group:
            return jsonify({
                "success": False,
                "message": "Resource group parameter is required"
            }), 400
        
        # Get deployment operations to see individual resource status
        operations = azure_client.resource_client.deployment_operations.list(
            resource_group, deployment_name
        )
        
        resources = []
        for operation in operations:
            if hasattr(operation.properties, 'target_resource') and operation.properties.target_resource:
                resource_info = {
                    "name": operation.properties.target_resource.resource_name,
                    "type": operation.properties.target_resource.resource_type,
                    "status": operation.properties.provisioning_state,
                    "operationId": operation.operation_id,
                    "timestamp": operation.properties.timestamp.isoformat() if operation.properties.timestamp else None
                }
                
                # Add status message if available
                if hasattr(operation.properties, 'status_message') and operation.properties.status_message:
                    # Convert StatusMessage object to string
                    status_msg = operation.properties.status_message
                    if hasattr(status_msg, 'error') and status_msg.error:
                        resource_info["message"] = str(status_msg.error)
                    elif hasattr(status_msg, 'status') and status_msg.status:
                        resource_info["message"] = str(status_msg.status)
                    else:
                        resource_info["message"] = str(status_msg)
                
                resources.append(resource_info)
        
        return jsonify({
            "success": True,
            "deployment_name": deployment_name,
            "resource_group": resource_group,
            "resources": resources,
            "total_resources": len(resources)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting deployment resources: {str(e)}"
        }), 500


# Offline Review Routes
@app.route('/offline-review')
def offline_review_page():
    """Offline review page"""
    templates = template_manager.list_templates()
    return render_template('offline_review.html', templates=templates)


@app.route('/offline-review/sessions', methods=['GET', 'POST'])
def offline_review_sessions():
    """List or create review sessions"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            session_id = offline_review.create_review_session(
                session_name=data['session_name'],
                environment=data['environment'],
                size=data['size']
            )
            
            # Add DWH environments if specified
            if data.get('dwh_environments'):
                session = offline_review.get_session(session_id)
                if session:
                    session['workload_config'].dwh_environments.extend(data['dwh_environments'])
            
            return jsonify({"success": True, "session_id": session_id})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400
    
    # GET - list sessions
    sessions = offline_review.list_sessions()
    return jsonify({"sessions": sessions})


@app.route('/offline-review/sessions/<session_id>')
def get_offline_review_session(session_id):
    """Get a specific review session"""
    try:
        session = offline_review.get_session(session_id)
        if not session:
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        return jsonify({"success": True, "session": session})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/offline-review/sessions/<session_id>', methods=['DELETE'])
def delete_offline_review_session(session_id):
    """Delete a review session"""
    try:
        if session_id in offline_review.review_sessions:
            del offline_review.review_sessions[session_id]
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Session not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/offline-review/sessions/<session_id>/templates', methods=['POST'])
def add_template_to_session(session_id):
    """Add a template to a review session"""
    try:
        data = request.get_json()
        preview = offline_review.add_template_to_session(
            session_id=session_id,
            template_name=data['template_name'],
            custom_parameters=data.get('custom_parameters')
        )
        return jsonify({"success": True, "preview": preview})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/offline-review/sessions/<session_id>/analyze', methods=['POST'])
def analyze_offline_review_session(session_id):
    """Analyze a review session"""
    try:
        analysis = offline_review.analyze_session(session_id)
        return jsonify({"success": True, "analysis": analysis})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/offline-review/sessions/<session_id>/export')
def export_offline_review_session(session_id):
    """Export a review session"""
    try:
        export_path = offline_review.export_session(session_id)
        
        # Create a zip file
        import zipfile
        import tempfile
        import os
        
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f"session_{session_id}.zip")
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(export_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, export_path)
                    zipf.write(file_path, arcname)
        
        from flask import send_file
        return send_file(zip_path, as_attachment=True, download_name=f"session_{session_id}.zip")
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/offline-review/workload-configs')
def get_workload_configs():
    """Get available workload configurations"""
    try:
        configs = workload_config.list_configurations()
        return jsonify({"configurations": configs})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


# Template Wizard Routes
@app.route('/template-wizard')
def template_wizard_page():
    """Template wizard page"""
    return render_template('template_wizard.html')


@app.route('/template-wizard/sessions', methods=['GET', 'POST'])
def template_wizard_sessions():
    """List or create wizard sessions"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            session_id = template_wizard.start_wizard_session(
                session_name=data['template_name'],
                description=data.get('description', '')
            )
            return jsonify({"success": True, "session_id": session_id})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400
    
    # GET - list sessions
    sessions = template_wizard.list_sessions()
    return jsonify({"sessions": sessions})


@app.route('/template-wizard/sessions/<session_id>')
def get_template_wizard_session(session_id):
    """Get a specific wizard session"""
    try:
        session = template_wizard.get_session(session_id)
        if not session:
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        return jsonify({"success": True, "session": session})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/template-wizard/sessions/<session_id>', methods=['DELETE'])
def delete_template_wizard_session(session_id):
    """Delete a wizard session"""
    try:
        if session_id in template_wizard.wizard_sessions:
            del template_wizard.wizard_sessions[session_id]
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Session not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/template-wizard/sessions/<session_id>/step', methods=['POST'])
def update_wizard_step(session_id):
    """Update wizard step"""
    try:
        data = request.get_json()
        step = data.get('step', 1)
        template_wizard.update_session_step(session_id, step)
        
        session = template_wizard.get_session(session_id)
        return jsonify({"success": True, "session": session})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/template-wizard/resources')
def get_available_resources():
    """Get available resource types"""
    try:
        resources = template_wizard.get_available_resources()
        return jsonify({"resources": resources})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/template-wizard/resources/<path:resource_type>/config')
def get_resource_config(resource_type):
    """Get configuration form for a resource type"""
    try:
        config = template_wizard.get_resource_configuration_form(resource_type)
        return jsonify(config)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/template-wizard/sessions/<session_id>/resources', methods=['POST'])
def add_resource_to_wizard_session(session_id):
    """Add a resource to wizard session"""
    try:
        data = request.get_json()
        result = template_wizard.add_resource_to_session(
            session_id=session_id,
            resource_type=data['resource_type'],
            resource_name=data['resource_name'],
            configuration=data['configuration']
        )
        return jsonify({"success": True, "resource": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/template-wizard/sessions/<session_id>/generate', methods=['POST'])
def generate_wizard_template(session_id):
    """Generate template from wizard session"""
    try:
        template = template_wizard.generate_template(session_id)
        
        # Save the generated template
        template_name = f"wizard-{session_id}"
        template_manager.save_template(template_name, template)
        
        return jsonify({"success": True, "template_name": template_name, "template": template})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to deployment status updates'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


@socketio.on('get_deployment_status')
def handle_get_deployment_status(data):
    """Handle request for deployment status"""
    deployment_name = data.get('deployment_name')
    if not deployment_name or deployment_name.strip() == '':
        emit('deployment_status', {'error': 'No deployment name provided'})
        return
    
    if deployment_name in deployment_statuses:
        emit('deployment_status', deployment_statuses[deployment_name])
    else:
        emit('deployment_status', {'error': 'Deployment not found'})


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
