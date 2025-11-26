"""
Bragi Builder - Azure ARM Template Manager
Main Flask application
"""
import os
import json
import threading
import time
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from datetime import datetime
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: ReportLab not available. PDF export will not work.")
from src.azure_client import AzureClient
from src.template_manager import TemplateManager
from src.deployment_manager import DeploymentManager
from src.offline_review import OfflineReviewManager
from src.workload_config import WorkloadConfigManager
from src.template_wizard import TemplateWizard
from src.vnet_validator import VNetValidator
from src.deployment_store import DeploymentStore, DeploymentRecord
from src.metrics_dashboard import metrics_bp
from src.auth import auth
from src.app_deployment import AppDeploymentManager

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize authentication (will be disabled if Azure AD not configured)
auth.init_app(app)

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

# Initialize app deployment manager (after azure_client is initialized)
app_deployment_manager = None
if azure_client:
    try:
        app_deployment_manager = AppDeploymentManager(azure_client)
    except Exception as e:
        print(f"Warning: Failed to initialize app deployment manager: {e}")

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


@app.route('/login')
def login():
    """Login route - redirects to Azure AD"""
    if auth.is_authenticated():
        return redirect(url_for('index'))
    
    login_url = auth.get_login_url()
    if login_url:
        return redirect(login_url)
    else:
        # If Azure AD not configured, allow access (for development)
        flash("Azure AD authentication not configured. Running in development mode.", "info")
        session['authenticated'] = True
        session['user'] = {'displayName': 'Development User', 'mail': 'dev@localhost'}
        return redirect(url_for('index'))


@app.route('/login/authorized')
def authorized():
    """Callback route for Azure AD authentication"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f"Authentication error: {error}", "error")
        return redirect(url_for('login'))
    
    if not code:
        flash("No authorization code received", "error")
        return redirect(url_for('login'))
    
    # Exchange code for token
    token_result = auth.get_token_from_code(code)
    if not token_result or 'access_token' not in token_result:
        flash("Failed to acquire access token", "error")
        return redirect(url_for('login'))
    
    # Get user information
    user_info = auth.get_user_info(token_result['access_token'])
    if not user_info:
        flash("Failed to get user information", "error")
        return redirect(url_for('login'))
    
    # Store in session
    auth.login(user_info, token_result['access_token'])
    
    # Redirect to original URL or index
    next_url = session.pop('next_url', None) or url_for('index')
    return redirect(next_url)


@app.route('/logout')
def logout():
    """Logout route"""
    auth.logout()
    flash("You have been logged out successfully", "info")
    return redirect(url_for('index'))


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


@app.route('/environments/<environment>/endpoints/pdf')
def environment_endpoints_pdf(environment):
    """Generate PDF of environment endpoints with clickable URLs"""
    if not REPORTLAB_AVAILABLE:
        flash("PDF export requires ReportLab library. Please install it: pip install reportlab", "error")
        return redirect(url_for('environment_endpoints', environment=environment, 
                              project_name=request.args.get('project_name', 'bragi'),
                              resource_group=request.args.get('resource_group')))
    
    if not deployment_manager:
        return jsonify({'error': 'Azure client not configured'}), 500
    
    try:
        from io import BytesIO
        
        project_name = request.args.get('project_name', 'bragi')
        specified_rg = request.args.get('resource_group')
        
        target_rg_name = None
        
        if specified_rg:
            target_rg_name = specified_rg
        else:
            resource_groups = azure_client.list_resource_groups()
            for rg in resource_groups:
                if rg.tags and rg.tags.get('CreatedBy') == 'Bragi Builder':
                    rg_project = rg.tags.get('Project', '')
                    rg_environment = rg.tags.get('Environment', '')
                    if (rg_project.lower() == project_name.lower() and 
                        rg_environment.lower() == environment.lower()):
                        target_rg_name = rg.name
                        break
        
        if not target_rg_name:
            return jsonify({'error': f'Environment {environment} not found'}), 404
        
        endpoints = deployment_manager.get_environment_endpoints(environment, project_name, target_rg_name)
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=12,
            alignment=TA_LEFT
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=10,
            spaceBefore=12
        )
        normal_style = styles['Normal']
        url_style = ParagraphStyle(
            'URLStyle',
            parent=styles['Normal'],
            textColor=colors.HexColor('#0066cc'),
            underline=True,
            fontSize=10
        )
        
        # Title
        story.append(Paragraph("Environment Endpoints Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Header info
        header_text = f"<b>Environment:</b> {environment} | <b>Project:</b> {project_name} | <b>Resource Group:</b> {target_rg_name}<br/>"
        header_text += f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        story.append(Paragraph(header_text, normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # App Services
        if endpoints.get('app_services'):
            story.append(Paragraph(f"📱 App Services ({len(endpoints['app_services'])})", heading_style))
            for app in endpoints['app_services']:
                story.append(Paragraph(f"<b>{app['name']}</b>", normal_style))
                # Create clickable URL
                url_text = f'<link href="{app["url"]}" color="blue"><u>{app["url"]}</u></link>'
                story.append(Paragraph(f"<b>URL:</b> {url_text}", url_style))
                story.append(Paragraph(f"<b>Hostname:</b> {app['hostname']}", normal_style))
                story.append(Paragraph(f"<b>State:</b> {app['state']}", normal_style))
                story.append(Paragraph(f"<b>HTTPS Only:</b> {'Yes' if app['https_only'] else 'No'}", normal_style))
                story.append(Spacer(1, 0.15*inch))
        
        # Storage Account
        if endpoints.get('storage_account'):
            storage = endpoints['storage_account']
            story.append(Paragraph("💾 Storage Account", heading_style))
            story.append(Paragraph(f"<b>{storage['name']}</b>", normal_style))
            url_text = f'<link href="{storage["primary_endpoint"]}" color="blue"><u>{storage["primary_endpoint"]}</u></link>'
            story.append(Paragraph(f"<b>Primary Endpoint:</b> {url_text}", url_style))
            story.append(Paragraph(f"<b>Location:</b> {storage['primary_location']}", normal_style))
            story.append(Paragraph(f"<b>Status:</b> {storage['status']}", normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # SQL Server
        if endpoints.get('sql_server'):
            sql = endpoints['sql_server']
            story.append(Paragraph("🗄️ SQL Server", heading_style))
            story.append(Paragraph(f"<b>{sql['name']}</b>", normal_style))
            story.append(Paragraph(f"<b>FQDN:</b> {sql['fqdn']}", normal_style))
            story.append(Paragraph(f"<b>Version:</b> {sql['version']}", normal_style))
            story.append(Paragraph(f"<b>State:</b> {sql['state']}", normal_style))
            
            if endpoints.get('sql_databases'):
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph(f"📊 Databases ({len(endpoints['sql_databases'])})", normal_style))
                for db in endpoints['sql_databases']:
                    db_info = f"• <b>{db['name']}</b> ({db['status']})"
                    if db.get('edition'):
                        db_info += f" - {db['edition']}"
                    if db.get('service_objective'):
                        db_info += f" ({db['service_objective']})"
                    story.append(Paragraph(db_info, normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Virtual Network
        if endpoints.get('vnet'):
            vnet = endpoints['vnet']
            story.append(Paragraph("🌐 Virtual Network", heading_style))
            story.append(Paragraph(f"<b>{vnet['name']}</b>", normal_style))
            address_space = ', '.join(vnet.get('address_space', []))
            story.append(Paragraph(f"<b>Address Space:</b> {address_space}", normal_style))
            subnets = ', '.join(vnet.get('subnets', []))
            story.append(Paragraph(f"<b>Subnets:</b> {subnets}", normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Public IPs
        if endpoints.get('public_ips'):
            story.append(Paragraph("🔗 Public IP Addresses", heading_style))
            table_data = [['Name', 'IP Address', 'Allocation Method', 'State']]
            for ip in endpoints['public_ips']:
                table_data.append([ip['name'], ip['ip_address'], ip['allocation_method'], ip.get('state', 'N/A')])
            table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(table)
            story.append(Spacer(1, 0.2*inch))
        
        # All Resources
        if endpoints.get('all_resources'):
            story.append(Paragraph(f"📋 All Resources ({len(endpoints['all_resources'])})", heading_style))
            table_data = [['Resource Name', 'Resource Type', 'Location']]
            for resource in endpoints['all_resources']:
                table_data.append([resource['name'], resource['type'], resource.get('location', 'N/A')])
            table = Table(table_data, colWidths=[2.5*inch, 2.5*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(table)
        
        # Build PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Create filename
        filename = f"{project_name}-{environment}-endpoints-{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return Response(
            pdf_data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        import traceback
        return jsonify({'error': f'Error generating PDF: {str(e)}', 'traceback': traceback.format_exc()}), 500


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


@app.route('/deploy-app')
def deploy_app_page():
    """Self-deployment page for deploying Bragi Builder to Azure"""
    if not app_deployment_manager:
        flash("Azure client not configured. Cannot deploy to Azure.", "error")
        return redirect(url_for('index'))
    
    # Get available Azure regions
    regions = []
    if azure_client:
        try:
            regions = azure_client.get_available_regions()
        except Exception as e:
            print(f"Error getting regions: {e}")
    
    return render_template('deploy_app.html', regions=regions)


@app.route('/api/deploy-app/validate', methods=['POST'])
def validate_app_deployment():
    """Validate deployment configuration"""
    if not app_deployment_manager:
        return jsonify({"success": False, "message": "App deployment manager not available"}), 400
    
    try:
        data = request.get_json()
        validation = app_deployment_manager.validate_deployment_config(data)
        
        # Also check App Service name availability
        name_check = None
        if data.get('app_service_name'):
            name_check = app_deployment_manager.check_app_service_name_availability(data['app_service_name'])
        
        return jsonify({
            "success": True,
            "validation": validation,
            "name_check": name_check
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/api/deploy-app', methods=['POST'])
def deploy_app():
    """Deploy Bragi Builder to Azure App Service"""
    if not app_deployment_manager:
        return jsonify({"success": False, "message": "App deployment manager not available"}), 400
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['resource_group', 'app_service_name', 'location']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "message": f"{field} is required"}), 400
        
        # Start deployment in background thread
        def deploy_in_background():
            try:
                result = app_deployment_manager.deploy_bragi_builder(data)
                # Emit result via WebSocket
                socketio.emit('app_deployment_complete', result)
            except Exception as e:
                socketio.emit('app_deployment_error', {
                    "success": False,
                    "error": str(e)
                })
        
        # Start deployment thread
        deployment_thread = threading.Thread(target=deploy_in_background)
        deployment_thread.daemon = True
        deployment_thread.start()
        
        return jsonify({
            "success": True,
            "message": "Deployment started. You will be notified when it completes.",
            "status": "running"
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/api/deploy-app/status/<deployment_id>')
def get_app_deployment_status(deployment_id):
    """Get status of app deployment"""
    if not app_deployment_manager:
        return jsonify({"success": False, "message": "App deployment manager not available"}), 400
    
    try:
        if deployment_id in app_deployment_manager.deployments:
            deployment = app_deployment_manager.deployments[deployment_id]
            return jsonify({
                "success": True,
                "deployment": deployment
            })
        else:
            return jsonify({
                "success": False,
                "message": "Deployment not found"
            }), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/api/deploy-app/verify/<resource_group>/<app_service_name>')
def verify_app_service_deployment(resource_group, app_service_name):
    """Verify what resources were actually created in Azure"""
    if not app_deployment_manager:
        return jsonify({"success": False, "message": "App deployment manager not available"}), 400
    
    try:
        verification_results = {
            'resource_group': None,
            'app_service_plan': None,
            'app_service': None,
            'resources': []
        }
        
        # Check resource group
        try:
            rg = azure_client.get_resource_group(resource_group)
            if rg:
                verification_results['resource_group'] = {
                    'exists': True,
                    'name': rg.name,
                    'location': rg.location,
                    'tags': rg.tags if rg.tags else {}
                }
            else:
                verification_results['resource_group'] = {'exists': False}
        except Exception as e:
            verification_results['resource_group'] = {'exists': False, 'error': str(e)}
        
        # List all resources in the resource group
        try:
            resources = azure_client.list_resources_in_group(resource_group)
            verification_results['resources'] = [
                {
                    'name': r.name,
                    'type': r.type,
                    'location': r.location
                }
                for r in resources
            ]
            
            # Check for App Service Plan
            for r in resources:
                if 'Microsoft.Web/serverfarms' in r.type:
                    try:
                        plan = app_deployment_manager.web_client.app_service_plans.get(resource_group, r.name)
                        verification_results['app_service_plan'] = {
                            'exists': True,
                            'name': plan.name,
                            'sku': plan.sku.name if plan.sku else 'Unknown',
                            'tier': plan.sku.tier if plan.sku else 'Unknown',
                            'status': plan.status if hasattr(plan, 'status') else 'Unknown'
                        }
                    except Exception as e:
                        verification_results['app_service_plan'] = {'exists': True, 'error': str(e)}
            
            # Check for App Service
            for r in resources:
                if 'Microsoft.Web/sites' in r.type and '/slots' not in r.type:
                    try:
                        app = app_deployment_manager.web_client.web_apps.get(resource_group, r.name)
                        verification_results['app_service'] = {
                            'exists': True,
                            'name': app.name,
                            'state': app.state,
                            'default_host_name': app.default_host_name,
                            'enabled': app.enabled if hasattr(app, 'enabled') else None,
                            'https_only': app.https_only if hasattr(app, 'https_only') else None
                        }
                    except Exception as e:
                        verification_results['app_service'] = {'exists': True, 'error': str(e)}
            
            # If App Service not found in resources, try direct lookup
            if not verification_results['app_service']:
                try:
                    app = app_deployment_manager.web_client.web_apps.get(resource_group, app_service_name)
                    verification_results['app_service'] = {
                        'exists': True,
                        'name': app.name,
                        'state': app.state,
                        'default_host_name': app.default_host_name
                    }
                except Exception as e:
                    verification_results['app_service'] = {'exists': False, 'error': str(e)}
                    
        except Exception as e:
            verification_results['error'] = f"Failed to list resources: {str(e)}"
        
        return jsonify({
            "success": True,
            "verification": verification_results
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


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
    # Get port from environment variable (Azure App Service uses PORT, default to 8080 for local)
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8080)))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    # In production (App Service), gunicorn will handle the server
    # This is only for local development
    socketio.run(app, debug=debug, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
