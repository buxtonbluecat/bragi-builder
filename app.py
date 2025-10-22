"""
Bragi Builder - Azure ARM Template Manager
Main Flask application
"""
import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from dotenv import load_dotenv
from src.azure_client import AzureClient
from src.template_manager import TemplateManager
from src.deployment_manager import DeploymentManager
from src.offline_review import OfflineReviewManager
from src.workload_config import WorkloadConfigManager
from src.template_wizard import TemplateWizard

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

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
    
    return render_template('deployments.html',
                         deployments=deployments,
                         resource_groups=resource_groups)


@app.route('/deploy', methods=['POST'])
def deploy():
    """Deploy a template"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        data = request.get_json()
        template_name = data.get('template_name')
        resource_group = data.get('resource_group')
        parameters = data.get('parameters', {})
        
        if not template_name or not resource_group:
            return jsonify({"success": False, "message": "Template name and resource group are required"}), 400
        
        # Check if resource group exists, create if not
        rg = azure_client.get_resource_group(resource_group)
        if not rg:
            location = data.get('location', 'East US')
            azure_client.create_resource_group(resource_group, location)
        
        # Deploy the template
        result = deployment_manager.deploy_template(
            template_name=template_name,
            resource_group_name=resource_group,
            parameters=parameters
        )
        
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


@app.route('/environments/<environment>', methods=['DELETE'])
def delete_environment(environment):
    """Delete an environment"""
    if not deployment_manager:
        return jsonify({"success": False, "message": "Azure client not configured"}), 400
    
    try:
        project_name = request.args.get('project_name', 'bragi')
        success = deployment_manager.delete_environment(environment, project_name)
        
        if success:
            return jsonify({"success": True, "message": f"Environment {environment} deletion started"})
        else:
            return jsonify({"success": False, "message": f"Environment {environment} not found"}), 404
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
