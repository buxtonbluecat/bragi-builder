#!/usr/bin/env python3
"""
Bragi Builder CLI - Command line interface for Azure ARM template management
"""
import click
import json
import os
import sys
from pathlib import Path
from src.azure_client import AzureClient
from src.template_manager import TemplateManager
from src.deployment_manager import DeploymentManager
from src.offline_review import OfflineReviewManager
from src.workload_config import WorkloadConfigManager


@click.group()
def cli():
    """Bragi Builder - Azure ARM Template Manager CLI"""
    pass


@cli.group()
def template():
    """Template management commands"""
    pass


@template.command('list')
def list_templates():
    """List all available templates"""
    tm = TemplateManager()
    templates = tm.list_templates()
    
    if not templates:
        click.echo("No templates found.")
        return
    
    click.echo("Available templates:")
    for template in templates:
        click.echo(f"  - {template}")


@template.command('show')
@click.argument('template_name')
def show_template(template_name):
    """Show template details"""
    tm = TemplateManager()
    template = tm.get_template(template_name)
    
    if not template:
        click.echo(f"Template '{template_name}' not found.", err=True)
        sys.exit(1)
    
    # Show basic info
    click.echo(f"Template: {template_name}")
    click.echo(f"Schema: {template.get('$schema', 'Not specified')}")
    click.echo(f"Version: {template.get('contentVersion', 'Not specified')}")
    
    # Show parameters
    parameters = template.get('parameters', {})
    if parameters:
        click.echo(f"\nParameters ({len(parameters)}):")
        for param_name, param_def in parameters.items():
            param_type = param_def.get('type', 'string')
            required = 'defaultValue' not in param_def
            click.echo(f"  - {param_name} ({param_type}) {'[Required]' if required else '[Optional]'}")
    
    # Show resources
    resources = template.get('resources', [])
    if resources:
        click.echo(f"\nResources ({len(resources)}):")
        for resource in resources:
            resource_type = resource.get('type', 'Unknown')
            resource_name = resource.get('name', 'Unknown')
            click.echo(f"  - {resource_type}: {resource_name}")


@template.command('validate')
@click.argument('template_name')
def validate_template(template_name):
    """Validate a template"""
    tm = TemplateManager()
    template = tm.get_template(template_name)
    
    if not template:
        click.echo(f"Template '{template_name}' not found.", err=True)
        sys.exit(1)
    
    validation = tm.validate_template(template)
    
    if validation['valid']:
        click.echo(f"✓ Template '{template_name}' is valid")
        if validation['warnings']:
            click.echo("\nWarnings:")
            for warning in validation['warnings']:
                click.echo(f"  - {warning}")
    else:
        click.echo(f"✗ Template '{template_name}' is invalid", err=True)
        click.echo("\nErrors:")
        for error in validation['errors']:
            click.echo(f"  - {error}")
        sys.exit(1)


@cli.group()
def deploy():
    """Deployment commands"""
    pass


@deploy.command('template')
@click.argument('template_name')
@click.argument('resource_group')
@click.option('--parameters', '-p', help='Parameters JSON file or JSON string')
@click.option('--location', '-l', default='East US', help='Location for new resource groups')
def deploy_template(template_name, resource_group, parameters, location):
    """Deploy a template"""
    try:
        # Initialize clients
        azure_client = AzureClient()
        tm = TemplateManager()
        dm = DeploymentManager(azure_client, tm)
        
        # Parse parameters
        param_dict = {}
        if parameters:
            if os.path.isfile(parameters):
                with open(parameters, 'r') as f:
                    param_dict = json.load(f)
            else:
                param_dict = json.loads(parameters)
        
        # Check if resource group exists, create if not
        rg = azure_client.get_resource_group(resource_group)
        if not rg:
            click.echo(f"Creating resource group '{resource_group}' in {location}...")
            # Add Bragi tags for CLI deployments
            tags = {
                "Environment": "CLI",
                "DeploymentType": "CLI Template",
                "TemplateName": template_name
            }
            azure_client.create_resource_group(resource_group, location, tags)
        
        # Deploy template
        click.echo(f"Deploying template '{template_name}' to resource group '{resource_group}'...")
        result = dm.deploy_template(template_name, resource_group, param_dict)
        
        click.echo(f"✓ Deployment started: {result['deployment_name']}")
        click.echo("Use 'bragi deploy status <deployment_name>' to check progress")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@deploy.command('environment')
@click.argument('environment')
@click.option('--project-name', '-p', default='bragi', help='Project name prefix')
@click.option('--location', '-l', default='East US', help='Azure location')
@click.option('--sql-password', '-s', required=True, help='SQL administrator password')
@click.option('--app-service-sku', default='B1', help='App Service SKU (F1, B1, S1, P1, etc.)')
@click.option('--sql-database-sku', default='Basic', help='SQL Database SKU (Basic, S0, S1, P1, etc.)')
@click.option('--storage-sku', default='Standard_LRS', help='Storage Account SKU')
@click.option('--enable-public-access', is_flag=True, help='Enable public network access for SQL Server')
def deploy_environment(environment, project_name, location, sql_password, app_service_sku, sql_database_sku, storage_sku, enable_public_access):
    """Deploy a complete environment with VNet, App Service, Storage, and SQL"""
    try:
        # Initialize clients
        azure_client = AzureClient()
        tm = TemplateManager()
        dm = DeploymentManager(azure_client, tm)
        
        click.echo(f"Deploying complete environment '{environment}' for project '{project_name}'...")
        click.echo(f"Location: {location}")
        click.echo(f"App Service SKU: {app_service_sku}")
        click.echo(f"SQL Database SKU: {sql_database_sku}")
        click.echo(f"Storage SKU: {storage_sku}")
        click.echo(f"Public Access: {'Enabled' if enable_public_access else 'Disabled'}")
        
        result = dm.create_environment_deployment(
            environment=environment,
            project_name=project_name,
            location=location,
            sql_password=sql_password,
            app_service_sku=app_service_sku,
            sql_database_sku=sql_database_sku,
            storage_sku=storage_sku,
            enable_public_access=enable_public_access
        )
        
        click.echo(f"✓ Complete environment deployment started: {result['deployment_name']}")
        click.echo("This will create:")
        click.echo("  - Resource Group")
        click.echo("  - Virtual Network with 4 subnets")
        click.echo("  - App Service Plan & App Service (HTTPS enforced)")
        click.echo("  - Storage Account (HTTPS enforced)")
        click.echo("  - SQL Server (Port 1433 configured)")
        click.echo("  - Meta & DWH Databases")
        click.echo("Use 'bragi deploy status <deployment_name>' to check progress")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@deploy.command('status')
@click.argument('deployment_name')
def deployment_status(deployment_name):
    """Get deployment status"""
    try:
        # Initialize clients
        azure_client = AzureClient()
        tm = TemplateManager()
        dm = DeploymentManager(azure_client, tm)
        
        status = dm.get_deployment_status(deployment_name)
        
        if not status:
            click.echo(f"Deployment '{deployment_name}' not found.", err=True)
            sys.exit(1)
        
        click.echo(f"Deployment: {deployment_name}")
        click.echo(f"Status: {status['status']}")
        click.echo(f"Template: {status['template_name']}")
        click.echo(f"Resource Group: {status['resource_group']}")
        click.echo(f"Started: {status['start_time']}")
        
        if status.get('outputs'):
            click.echo("\nOutputs:")
            for key, value in status['outputs'].items():
                click.echo(f"  {key}: {value}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@deploy.command('endpoints')
@click.argument('environment')
@click.option('--project-name', '-p', default='bragi', help='Project name prefix')
def deployment_endpoints(environment, project_name):
    """Get public-facing endpoints and IP addresses for an environment"""
    try:
        # Initialize clients
        azure_client = AzureClient()
        tm = TemplateManager()
        dm = DeploymentManager(azure_client, tm)
        
        click.echo(f"Getting endpoints for environment '{environment}' in project '{project_name}'...")
        endpoints = dm.get_environment_endpoints(environment, project_name)
        
        if not endpoints:
            click.echo("No endpoints found or environment doesn't exist.", err=True)
            sys.exit(1)
        
        click.echo(f"\n🌐 Environment Endpoints for {project_name}-{environment}")
        click.echo("=" * 50)
        
        # App Service
        if endpoints.get('app_service'):
            app = endpoints['app_service']
            click.echo(f"\n📱 App Service: {app['name']}")
            click.echo(f"   URL: {app['url']}")
            click.echo(f"   Hostname: {app['hostname']}")
            click.echo(f"   State: {app['state']}")
            click.echo(f"   HTTPS Only: {app['https_only']}")
        
        # Storage Account
        if endpoints.get('storage_account'):
            storage = endpoints['storage_account']
            click.echo(f"\n💾 Storage Account: {storage['name']}")
            click.echo(f"   Blob Endpoint: {storage['primary_endpoint']}")
            click.echo(f"   Location: {storage['primary_location']}")
            click.echo(f"   Status: {storage['status']}")
        
        # SQL Server
        if endpoints.get('sql_server'):
            sql = endpoints['sql_server']
            click.echo(f"\n🗄️  SQL Server: {sql['name']}")
            click.echo(f"   FQDN: {sql['fqdn']}")
            click.echo(f"   Version: {sql['version']}")
            click.echo(f"   State: {sql['state']}")
        
        # VNet
        if endpoints.get('vnet'):
            vnet = endpoints['vnet']
            click.echo(f"\n🌐 Virtual Network: {vnet['name']}")
            click.echo(f"   Address Space: {', '.join(vnet['address_space'])}")
            click.echo(f"   Subnets: {', '.join(vnet['subnets'])}")
        
        # Public IPs
        if endpoints.get('public_ips'):
            click.echo(f"\n🔗 Public IP Addresses:")
            for ip in endpoints['public_ips']:
                click.echo(f"   {ip['name']}: {ip['ip_address']} ({ip['allocation_method']})")
        
        if not any([endpoints.get('app_service'), endpoints.get('storage_account'), 
                   endpoints.get('sql_server'), endpoints.get('vnet'), endpoints.get('public_ips')]):
            click.echo("No public endpoints found in this environment.")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@deploy.command('delete')
@click.argument('environment')
@click.option('--project-name', '-p', default='bragi', help='Project name prefix')
@click.option('--confirm', '-y', is_flag=True, help='Skip confirmation prompt')
def delete_environment(environment, project_name, confirm):
    """Delete an entire environment (resource group and all resources)"""
    resource_group_name = f"{project_name}-{environment}-rg"
    
    if not confirm:
        click.echo(f"⚠️  WARNING: This will delete the entire environment '{environment}' in project '{project_name}'")
        click.echo(f"   Resource Group: {resource_group_name}")
        click.echo("   This action cannot be undone!")
        
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Deletion cancelled.")
            return
    
    try:
        # Initialize clients
        azure_client = AzureClient()
        tm = TemplateManager()
        dm = DeploymentManager(azure_client, tm)
        
        click.echo(f"Deleting environment '{environment}' in project '{project_name}'...")
        click.echo(f"Resource Group: {resource_group_name}")
        
        success = dm.delete_environment(environment, project_name)
        
        if success:
            click.echo(f"✅ Environment '{environment}' deletion started successfully!")
            click.echo("   This may take several minutes to complete.")
            click.echo("   You can check the Azure portal to monitor progress.")
        else:
            click.echo(f"❌ Environment '{environment}' not found or already deleted.")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.group()
def resource():
    """Resource management commands"""
    pass


@resource.command('list')
@click.argument('resource_group')
def list_resources(resource_group):
    """List resources in a resource group"""
    try:
        azure_client = AzureClient()
        resources = azure_client.list_resources_in_group(resource_group)
        
        if not resources:
            click.echo(f"No resources found in '{resource_group}'")
            return
        
        click.echo(f"Resources in '{resource_group}':")
        for resource in resources:
            click.echo(f"  - {resource.name} ({resource.type})")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@resource.command('groups')
def list_resource_groups():
    """List all resource groups"""
    try:
        azure_client = AzureClient()
        resource_groups = azure_client.list_resource_groups()
        
        if not resource_groups:
            click.echo("No resource groups found")
            return
        
        click.echo("Resource Groups:")
        for rg in resource_groups:
            click.echo(f"  - {rg.name} ({rg.location})")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.group()
def review():
    """Offline review commands"""
    pass


@review.command('create')
@click.argument('session_name')
@click.option('--environment', '-e', required=True, help='Environment type (dev, sit, uat, pre-prod, prod)')
@click.option('--size', '-s', required=True, help='Workload size (small, medium, large, enterprise)')
@click.option('--dwh-environments', '-d', multiple=True, help='Additional DWH environments to include')
def create_review_session(session_name, environment, size, dwh_environments):
    """Create a new offline review session"""
    try:
        offline_review = OfflineReviewManager()
        session_id = offline_review.create_review_session(session_name, environment, size)
        
        # Add DWH environments if specified
        if dwh_environments:
            session = offline_review.get_session(session_id)
            if session:
                session['workload_config'].dwh_environments.extend(dwh_environments)
        
        click.echo(f"✓ Review session created: {session_id}")
        click.echo(f"Session name: {session_name}")
        click.echo(f"Environment: {environment}")
        click.echo(f"Size: {size}")
        if dwh_environments:
            click.echo(f"DWH environments: {', '.join(dwh_environments)}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@review.command('list')
def list_review_sessions():
    """List all review sessions"""
    try:
        offline_review = OfflineReviewManager()
        sessions = offline_review.list_sessions()
        
        if not sessions:
            click.echo("No review sessions found")
            return
        
        click.echo("Review Sessions:")
        for session in sessions:
            click.echo(f"  - {session['session_name']} ({session['session_id']})")
            click.echo(f"    Environment: {session['environment']}, Size: {session['size']}")
            click.echo(f"    Templates: {session['template_count']}, Created: {session['created_at']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@review.command('add-template')
@click.argument('session_id')
@click.argument('template_name')
@click.option('--parameters', '-p', help='Custom parameters JSON file or JSON string')
def add_template_to_session(session_id, template_name, parameters):
    """Add a template to a review session"""
    try:
        offline_review = OfflineReviewManager()
        
        # Parse parameters
        param_dict = None
        if parameters:
            if os.path.isfile(parameters):
                with open(parameters, 'r') as f:
                    param_dict = json.load(f)
            else:
                param_dict = json.loads(parameters)
        
        preview = offline_review.add_template_to_session(session_id, template_name, param_dict)
        
        click.echo(f"✓ Template '{template_name}' added to session")
        click.echo(f"Resources: {len(preview['resources'])}")
        click.echo(f"Estimated monthly cost: ${preview['estimated_costs']['monthly_estimate']:.2f}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@review.command('analyze')
@click.argument('session_id')
def analyze_review_session(session_id):
    """Analyze a review session"""
    try:
        offline_review = OfflineReviewManager()
        analysis = offline_review.analyze_session(session_id)
        
        click.echo(f"Analysis for session: {session_id}")
        click.echo(f"Templates: {analysis['total_templates']}")
        click.echo(f"Resources: {analysis['total_resources']}")
        click.echo(f"Estimated monthly cost: ${analysis['total_estimated_cost']:.2f}")
        
        if analysis['recommendations']:
            click.echo("\nRecommendations:")
            for rec in analysis['recommendations']:
                click.echo(f"  - {rec}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@review.command('export')
@click.argument('session_id')
@click.option('--output-dir', '-o', default='exports', help='Output directory for export')
def export_review_session(session_id, output_dir):
    """Export a review session"""
    try:
        offline_review = OfflineReviewManager()
        export_path = offline_review.export_session(session_id, output_dir)
        
        click.echo(f"✓ Session exported to: {export_path}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@review.command('configs')
def list_workload_configs():
    """List available workload configurations"""
    try:
        workload_config = WorkloadConfigManager()
        configs = workload_config.list_configurations()
        
        click.echo("Available Workload Configurations:")
        for config in configs:
            click.echo(f"  - {config['environment']}_{config['size']}")
            click.echo(f"    App Service: {config['app_service_sku']}")
            click.echo(f"    Storage: {config['storage_sku']}")
            click.echo(f"    SQL Databases: {len(config['sql_databases'])}")
            click.echo(f"    DWH Environments: {config['dwh_environments']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
